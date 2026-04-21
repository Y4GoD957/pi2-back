from datetime import datetime, timezone
from decimal import Decimal

from httpx import AsyncClient, HTTPStatusError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApiError
from app.models.relatorio import Relatorio as RelatorioModel
from app.repositories.educenso import EducensoRepository
from app.schemas.educenso import (
    AnalysisRecord,
    CreateReportPayload,
    DfHeatMapData,
    EducensoAnalysisFilters,
    EducensoDashboardResponse,
    FatoEducacao,
    FatoSocioeconomico,
    Localidade,
    Relatorio,
    ReportCreatedResponse,
    ReportDetailResponse,
    ReportFormOptions,
    ReportListItem,
)
from app.schemas.ibge import AdministrativeRegion
from app.utils.analytics import (
    MODELING_NOTICE,
    build_analytical_table_rows,
    build_comparison_data,
    build_dashboard_indicators,
    build_filter_options,
    build_filters_applied_label,
    build_report_filter_options,
    build_trend_data,
    dedupe_analysis_records,
    format_location_label,
    get_report_type_label,
    normalize_filters,
)
from app.utils.heatmap import build_df_heatmap_fallback
from app.utils.likert import compute_education_likert, compute_socioeconomic_likert, interpret_likert
from app.utils.recommendations import build_recommendation_summary, build_recommendations_from_records

EDUCENSO_FUTURE_INDICATORS = ["IDH", "Taxa de mortalidade", "Dados da pandemia"]


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


class EducensoService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = EducensoRepository(session)

    async def fetch_dashboard(self, filters: EducensoAnalysisFilters) -> EducensoDashboardResponse:
        records = await self._fetch_analysis_records()
        df_records = [record for record in records if record.localidade.uf == "DF"]
        normalized_filters = normalize_filters(filters, forced_uf="DF")
        filtered_records = self._apply_filters(df_records, normalized_filters)
        unique_records = dedupe_analysis_records(filtered_records)
        filter_options = build_filter_options(df_records)
        recommendations = build_recommendations_from_records(unique_records)
        recommendation_summary_by_key = {
            self._record_key(record): build_recommendation_summary(record).summary
            for record in unique_records
        }
        average_likert_education = sum(item.report.likertEducacao for item in filtered_records) / max(
            len(filtered_records),
            1,
        )
        average_likert_socio = sum(item.report.likertSocioeconomico for item in filtered_records) / max(
            len(filtered_records),
            1,
        )
        heatmap = build_df_heatmap_fallback(unique_records)

        return EducensoDashboardResponse(
            filters=normalized_filters,
            filterOptions=filter_options,
            indicators=build_dashboard_indicators(unique_records),
            trend=build_trend_data(unique_records),
            comparisons=build_comparison_data(unique_records),
            tableRows=build_analytical_table_rows(unique_records, recommendation_summary_by_key),
            recommendations=recommendations,
            likertSummary={
                "educacao": interpret_likert(average_likert_education or 1),
                "socioeconomico": interpret_likert(average_likert_socio or 1),
            },
            heatMap=heatmap,
            totalRecords=len(unique_records),
            futureIndicators=EDUCENSO_FUTURE_INDICATORS,
            modelNotice=MODELING_NOTICE,
        )

    async def fetch_df_heatmap(self, filters: EducensoAnalysisFilters) -> DfHeatMapData:
        dashboard = await self.fetch_dashboard(filters)
        return dashboard.heatMap

    async def fetch_df_regions(self) -> list[AdministrativeRegion]:
        url = (
            "https://servicodados.ibge.gov.br/api/v1/localidades/"
            "estados/DF/distritos?orderBy=nome"
        )
        try:
            async with AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers={"Accept": "application/json"})
                response.raise_for_status()
        except HTTPStatusError as exc:
            raise ApiError(
                "Nao foi possivel consultar os distritos do DF no IBGE.",
                502,
            ) from exc

        data = response.json()
        return [
            AdministrativeRegion(id=str(item["id"]), nome=item["nome"])
            for item in data
        ]

    async def fetch_user_reports(
        self,
        user_id: int,
        filters: EducensoAnalysisFilters,
    ) -> list[ReportListItem]:
        reports = await self.repository.fetch_reports(user_id=user_id)
        mapped_reports = [self._map_report(item) for item in reports]
        filtered_reports = [
            report
            for report in mapped_reports
            if self._matches_filters(self._to_analysis_record(report), filters)
        ]

        return [
            ReportListItem(
                report=report,
                reportTypeLabel=get_report_type_label(report.tipo),
                locationLabel=format_location_label(self._to_analysis_record(report)),
                recommendation=build_recommendations_from_records([self._to_analysis_record(report)])[0],
            )
            for report in filtered_reports
        ]

    async def fetch_report_by_id(self, user_id: int, report_id: int) -> ReportDetailResponse:
        items = await self.fetch_user_reports(user_id, EducensoAnalysisFilters())
        for item in items:
            if item.report.idRelatorio == report_id:
                return ReportDetailResponse(**item.model_dump())
        raise ApiError("Relatorio nao encontrado para o usuario autenticado.", 404)

    async def fetch_report_form_options(self) -> ReportFormOptions:
        years = await self.repository.fetch_available_years()
        localities = await self.repository.fetch_localities()
        return ReportFormOptions(
            years=years,
            localities=[self._map_localidade(item) for item in localities],
        )

    async def create_user_report(
        self,
        user_id: int,
        payload: CreateReportPayload,
    ) -> ReportCreatedResponse:
        localities = await self.repository.fetch_localities()
        selected_locality = next(
            (item for item in localities if item.id_localidade == payload.localidadeId),
            None,
        )
        if selected_locality is None:
            raise ApiError("Localidade invalida para criacao do relatorio.", 400)

        facts_education = await self.repository.fetch_facts_education_by_year(payload.year)
        facts_socioeconomic = await self.repository.fetch_facts_socioeconomic_by_year(payload.year)

        if not facts_education or not facts_socioeconomic:
            raise ApiError("Nao existem fatos suficientes para o ano selecionado.", 400)

        if len(facts_education) > 1 or len(facts_socioeconomic) > 1:
            raise ApiError(
                "A modelagem atual possui mais de um fato para o mesmo ano sem chave de localidade.",
                400,
            )

        education = self._map_fato_educacao(facts_education[0])
        socioeconomic = self._map_fato_socioeconomico(facts_socioeconomic[0])
        localidade = self._map_localidade(selected_locality)

        draft_report = Relatorio(
            idRelatorio=0,
            tipo=payload.tipo,
            likertEducacao=compute_education_likert(education),
            likertSocioeconomico=compute_socioeconomic_likert(socioeconomic),
            avaliacao=payload.avaliacao.strip(),
            filtrosAplicados=payload.filtrosAplicados or build_filters_applied_label({"year": payload.year}),
            politicaPublica=payload.politicaPublica or "",
            dataCriacao=datetime.now(timezone.utc),
            idUsuario=user_id,
            idFatoEducacao=education.idFatoEducacao,
            idFatoSocioeconomico=socioeconomic.idFatoSocioeconomico,
            idDimLocalidade=payload.localidadeId,
            localidade=localidade,
            fatoEducacao=education,
            fatoSocioeconomico=socioeconomic,
        )
        record = AnalysisRecord(
            report=draft_report,
            localidade=localidade,
            fatoEducacao=education,
            fatoSocioeconomico=socioeconomic,
        )
        recommendation = build_recommendations_from_records([record])[0]
        policy_text = payload.politicaPublica or f"{recommendation.title}: {recommendation.summary}"

        model = RelatorioModel(
            tipo=payload.tipo,
            likert_educacao=draft_report.likertEducacao,
            likert_socioeconomico=draft_report.likertSocioeconomico,
            avaliacao=payload.avaliacao.strip(),
            filtros_aplicados=draft_report.filtrosAplicados,
            politica_publica=policy_text,
            data_criacao=datetime.now(timezone.utc),
            id_usuario=user_id,
            id_fato_educacao=education.idFatoEducacao,
            id_fato_socioeconomico=socioeconomic.idFatoSocioeconomico,
            id_dim_localidade=payload.localidadeId,
        )
        created = await self.repository.create_report(model)
        report = self._map_report(created)
        return ReportCreatedResponse(
            report=report,
            reportTypeLabel=get_report_type_label(report.tipo),
            locationLabel=format_location_label(self._to_analysis_record(report)),
            recommendation=recommendation,
        )

    async def _fetch_analysis_records(self) -> list[AnalysisRecord]:
        reports = await self.repository.fetch_reports()
        return [self._to_analysis_record(self._map_report(report)) for report in reports]

    def _apply_filters(
        self,
        records: list[AnalysisRecord],
        filters: EducensoAnalysisFilters,
    ) -> list[AnalysisRecord]:
        return [record for record in records if self._matches_filters(record, filters)]

    def _matches_filters(self, record: AnalysisRecord, filters: EducensoAnalysisFilters) -> bool:
        if filters.year and record.fatoEducacao.ano != filters.year:
            return False
        if filters.uf and record.localidade.uf != filters.uf:
            return False
        if filters.municipality and record.localidade.municipio != filters.municipality:
            return False
        if filters.censusSector and record.localidade.setorCensitario != filters.censusSector:
            return False
        if filters.reportType and record.report.tipo != filters.reportType:
            return False
        return True

    def _record_key(self, record: AnalysisRecord) -> str:
        return (
            f"{record.localidade.idLocalidade}:"
            f"{record.fatoEducacao.idFatoEducacao}:"
            f"{record.fatoSocioeconomico.idFatoSocioeconomico}"
        )

    def _to_analysis_record(self, report: Relatorio) -> AnalysisRecord:
        if not report.localidade or not report.fatoEducacao or not report.fatoSocioeconomico:
            raise ApiError("Relatorio sem relacionamentos necessarios para analise.", 500)
        return AnalysisRecord(
            report=report,
            localidade=report.localidade,
            fatoEducacao=report.fatoEducacao,
            fatoSocioeconomico=report.fatoSocioeconomico,
        )

    def _map_localidade(self, model) -> Localidade:
        return Localidade(
            idLocalidade=model.id_localidade,
            codigoIbge=model.codigo_ibge,
            uf=model.UF,
            municipio=model.municipio,
            setorCensitario=model.setor_censitario,
            dataCriacao=model.data_criacao,
        )

    def _map_fato_educacao(self, model) -> FatoEducacao:
        return FatoEducacao(
            idFatoEducacao=model.id_fato_educacao,
            ano=model.ano,
            taxaMatricula=_to_float(model.taxa_matricula) or 0.0,
            taxaFrequenciaEscolar=_to_float(model.taxa_frequencia_escolar) or 0.0,
            taxaAnalfabetismo=_to_float(model.taxa_analfabetismo) or 0.0,
            dataCriacao=model.data_criacao,
        )

    def _map_fato_socioeconomico(self, model) -> FatoSocioeconomico:
        return FatoSocioeconomico(
            idFatoSocioeconomico=model.id_fato_socioeconomico,
            ano=model.ano,
            rendaPerCapita=_to_float(model.renda_per_capita),
            acessoInternetPerc=_to_float(model.acesso_internet_perc),
            acessoSaneamentoPerc=_to_float(model.acesso_saneamento_perc),
            dataCriacao=model.data_criacao,
        )

    def _map_report(self, model) -> Relatorio:
        return Relatorio(
            idRelatorio=model.id_relatorio,
            tipo=model.tipo,
            likertEducacao=float(model.likert_educacao),
            likertSocioeconomico=float(model.likert_socioeconomico),
            avaliacao=model.avaliacao,
            filtrosAplicados=model.filtros_aplicados,
            politicaPublica=model.politica_publica,
            dataCriacao=model.data_criacao,
            idUsuario=model.id_usuario,
            idFatoEducacao=model.id_fato_educacao,
            idFatoSocioeconomico=model.id_fato_socioeconomico,
            idDimLocalidade=model.id_dim_localidade,
            localidade=self._map_localidade(model.localidade) if model.localidade else None,
            fatoEducacao=self._map_fato_educacao(model.fato_educacao) if model.fato_educacao else None,
            fatoSocioeconomico=(
                self._map_fato_socioeconomico(model.fato_socioeconomico)
                if model.fato_socioeconomico
                else None
            ),
        )
