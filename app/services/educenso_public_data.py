from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from app.core.exceptions import ApiError
from app.schemas.educenso import (
    AnalyticalTableRow,
    DashboardIndicator,
    DashboardLikertSummary,
    DashboardTrendPoint,
    DfHeatMapArea,
    DfHeatMapData,
    EducensoAnalysisFilters,
    EducensoDashboardResponse,
    EducensoFilterOptions,
    IndicatorComparisonPoint,
    LikertInterpretation,
    PublicPolicyRecommendation,
)
from app.schemas.ibge import AdministrativeRegion, DfMetadataResponse
from app.schemas.public_data import (
    ChartSeriesPoint,
    DataSourceStatus,
    DataSourcesResponse,
    DfChartsResponse,
    DfHeatmapAreaResponse,
    DfHeatmapResponse,
    DfIndicatorsResponse,
    DfSummaryResponse,
    HeatmapAreaInterpretation,
    IndicatorHistoricalPoint,
    IndicatorSourceAvailability,
    NormalizedIndicatorValue,
    RecommendationHint,
    SourceMetadata,
    SummaryCard,
)
from app.services.public_data.exceptions import PublicDataError
from app.services.public_data.ibge_client import IbgeLocalitiesClient
from app.services.public_data.ibge_malhas_client import IbgeMalhasClient
from app.services.public_data.normalizers import (
    build_correlation_context,
    build_interpretation,
    score_from_thresholds,
)
from app.services.public_data.sidra_client import SidraClient


class EducensoPublicDataService:
    def __init__(self) -> None:
        self.sidra_client = SidraClient()
        self.ibge_client = IbgeLocalitiesClient()
        self.malhas_client = IbgeMalhasClient()
        self._indicator_catalog = {
            "population_resident": {
                "label": "Populacao residente",
                "theme": "demografia",
                "unit": "habitantes",
                "table_code": "1162",
                "variable_id": "93",
                "periods": "all",
                "classifications": None,
                "territorial_level": "N3[53]",
                "thresholds": (2500000.0, 3500000.0),
                "higher_is_better": True,
                "source": "sidra",
            },
            "internet_access_pct": {
                "label": "Domicilios com acesso a Internet",
                "theme": "socioeconomico",
                "unit": "%",
                "table_code": "1220",
                "variable_id": "2584",
                "periods": "-6",
                "classifications": None,
                "territorial_level": "N3[53]",
                "thresholds": (40.0, 95.0),
                "higher_is_better": True,
                "source": "sidra",
            },
            "school_attendance_rate": {
                "label": "Taxa de frequencia escolar",
                "theme": "educacao",
                "unit": "%",
                "table_code": "3836",
                "variable_id": "3795",
                "periods": "-6",
                "classifications": None,
                "territorial_level": "N3[53]",
                "thresholds": (60.0, 98.0),
                "higher_is_better": True,
                "source": "sidra",
            },
            "literacy_rate_15_plus": {
                "label": "Taxa de alfabetizacao 15+",
                "theme": "educacao",
                "unit": "%",
                "table_code": "1187",
                "variable_id": "2513",
                "periods": "-6",
                "classifications": {"2": "6794"},
                "territorial_level": "N3[53]",
                "thresholds": (75.0, 100.0),
                "higher_is_better": True,
                "source": "sidra",
            },
            "adequate_housing_pct": {
                "label": "Domicilios adequados para moradia",
                "theme": "socioeconomico",
                "unit": "%",
                "table_code": "1191",
                "variable_id": "2516",
                "periods": "-6",
                "classifications": None,
                "territorial_level": "N3[53]",
                "thresholds": (40.0, 100.0),
                "higher_is_better": True,
                "source": "sidra",
            },
        }

    async def fetch_data_sources(self) -> DataSourcesResponse:
        return DataSourcesResponse(
            fontes=[
                DataSourceStatus(
                    chave="sidra_ibge",
                    nome="SIDRA/IBGE",
                    descricao="Fonte principal de indicadores socioeconomicos, demograficos e parte dos indicadores educacionais.",
                    status="integrado",
                    cobertura="UF do Distrito Federal, com serie historica quando a tabela oficial permitir.",
                    mensagens=[
                        "Nem todas as tabelas oficiais possuem granularidade por Regiao Administrativa do DF.",
                        "Quando a tabela nao suportar o indicador esperado, o backend retorna indisponibilidade estruturada.",
                    ],
                ),
                DataSourceStatus(
                    chave="ibge_localidades",
                    nome="IBGE Localidades",
                    descricao="Metadados territoriais oficiais de UF, municipios e distritos.",
                    status="integrado",
                    cobertura="UF e municipios oficiais, incluindo Distrito Federal.",
                    mensagens=[
                        "As Regioes Administrativas do DF nao sao equivalentes a municipios oficiais do IBGE.",
                    ],
                ),
                DataSourceStatus(
                    chave="inep",
                    nome="INEP",
                    descricao="Fonte oficial preparada para futura expansao de indicadores educacionais mais detalhados.",
                    status="parcial",
                    cobertura="Preparado para integracao futura mantendo contrato estavel.",
                    mensagens=[
                        "Nesta fase, indicadores avancados de educacao podem retornar indisponiveis com fonte sugerida INEP.",
                    ],
                ),
            ],
            gerado_em=datetime.now(timezone.utc),
        )

    async def fetch_df_metadata(self) -> DfMetadataResponse:
        try:
            payload = await self.ibge_client.fetch_df_metadata()
        except PublicDataError as exc:
            raise ApiError(exc.message, 502) from exc

        return DfMetadataResponse(
            uf=payload["uf"],
            municipios=payload["municipios"],
            granularidadeOficial=payload["granularidade_oficial"],
            avisoGranularidade=payload["aviso_granularidade"],
            obtidoEm=payload["obtido_em"],
        )

    async def fetch_df_geojson(self) -> dict:
        try:
            return await self.malhas_client.fetch_df_boundary()
        except PublicDataError as exc:
            raise ApiError(exc.message, 502) from exc

    async def fetch_df_regions(self) -> list[AdministrativeRegion]:
        try:
            regions = await self.ibge_client.fetch_df_districts()
        except PublicDataError as exc:
            raise ApiError(exc.message, 502) from exc
        return [AdministrativeRegion(id=item["id"], nome=item["nome"]) for item in regions]

    async def fetch_df_indicators(
        self,
        *,
        year: int | None,
        theme: str | None,
        indicator: str | None,
        source: str | None,
    ) -> DfIndicatorsResponse:
        selected_keys = self._select_indicator_keys(theme=theme, indicator=indicator, source=source)
        indicators = [await self._build_indicator_value(key=key, year=year) for key in selected_keys]
        warnings: list[str] = []
        if not indicators:
            indicators.append(self._build_unavailable_indicator(indicator or "indicador_desconhecido", theme))
            warnings.append("Nenhum indicador oficial compativel foi encontrado para o filtro solicitado.")

        return DfIndicatorsResponse(
            ano=year,
            tema=theme,
            indicador=indicator,
            fonte=source,
            indicadores=indicators,
            avisos=warnings,
        )

    async def fetch_df_heatmap(
        self,
        *,
        year: int | None,
        indicator: str | None,
        source: str | None,
    ) -> DfHeatmapResponse:
        indicator_key = indicator or "internet_access_pct"
        normalized = await self._build_indicator_value(key=indicator_key, year=year)
        warning = (
            "Os dados oficiais consultados nesta fase nao possuem granularidade por Regiao Administrativa do DF. "
            "O heatmap representa apenas o recorte oficial disponivel para o Distrito Federal."
        )
        return DfHeatmapResponse(
            year=normalized.ano,
            indicator=indicator_key,
            source=source or "sidra",
            areas=[
                DfHeatmapAreaResponse(
                    locality_id="df",
                    locality_name="Distrito Federal",
                    ibge_code="53",
                    uf="DF",
                    year=normalized.ano,
                    indicator_key=normalized.indicador,
                    indicator_label=normalized.rotulo,
                    raw_value=normalized.valor_bruto,
                    normalized_value=normalized.valor_normalizado,
                    unit=normalized.unidade,
                    classification_level=normalized.interpretacao.nivel_severidade if normalized.interpretacao else None,
                    classification_label=normalized.interpretacao.leitura if normalized.interpretacao else None,
                    source=source or "sidra",
                    source_metadata=normalized.metadados_fonte,
                    status_dado=normalized.status_dado,
                    interpretacao=HeatmapAreaInterpretation(
                        classificacao=normalized.interpretacao.leitura if normalized.interpretacao else None,
                        severidade=normalized.interpretacao.nivel_severidade if normalized.interpretacao else "indefinido",
                        interpretacao=normalized.interpretacao.resumo if normalized.interpretacao else None,
                        direcao_tendencia=(
                            normalized.interpretacao.tendencia.direcao
                            if normalized.interpretacao and normalized.interpretacao.tendencia
                            else "indefinido"
                        ),
                        metadados_explicacao=normalized.interpretacao.explicacao if normalized.interpretacao else None,
                        confiabilidade_fonte=normalized.metadados_fonte.confiabilidade,
                    ),
                    warnings=[warning, *normalized.avisos],
                )
            ],
            warnings=[warning],
        )

    async def fetch_df_charts(
        self,
        *,
        year: int | None,
        indicator: str | None,
        source: str | None,
    ) -> DfChartsResponse:
        indicator_key = indicator or "internet_access_pct"
        normalized = await self._build_indicator_value(key=indicator_key, year=year)
        historical_series = [
            ChartSeriesPoint(
                label=str(point.ano),
                value=point.valor,
                year=point.ano,
                status_dado=point.status_dado,
            )
            for point in normalized.serie_historica
        ]
        return DfChartsResponse(
            year=normalized.ano,
            indicator=indicator_key,
            source=source or "sidra",
            bar_chart_data=[],
            historical_series=historical_series,
            table_data=[
                {
                    "localidade": "Distrito Federal",
                    "indicador": normalized.rotulo,
                    "ano": normalized.ano,
                    "valor": normalized.valor_bruto,
                    "unidade": normalized.unidade,
                    "status_dado": normalized.status_dado,
                }
            ],
            source_metadata=[normalized.metadados_fonte],
            recommendation_hints=normalized.interpretacao.dicas_recomendacao if normalized.interpretacao else [],
            warnings=[
                "Nao ha comparacao por Regiao Administrativa nesta fase porque a fonte oficial nao oferece esse nivel territorial para os indicadores integrados.",
            ],
        )

    async def fetch_df_summary(self, *, year: int | None, source: str | None) -> DfSummaryResponse:
        selected_keys = [
            "internet_access_pct",
            "school_attendance_rate",
            "illiteracy_rate_15_plus",
            "adequate_housing_pct",
        ]
        items = [await self._build_indicator_value(key=key, year=year) for key in selected_keys]
        values = [item.valor_bruto for item in items if item.valor_bruto is not None]
        return DfSummaryResponse(
            year=year,
            source=source or "sidra",
            summary_cards=[
                SummaryCard(
                    id=item.indicador,
                    label=item.rotulo,
                    valor=item.valor_bruto,
                    unidade=item.unidade,
                    descricao=item.interpretacao.leitura if item.interpretacao else None,
                    status_dado=item.status_dado,
                )
                for item in items
            ],
            total_registros=len(items),
            media=round(mean(values), 2) if values else None,
            minimo=min(values) if values else None,
            maximo=max(values) if values else None,
            source_metadata=[item.metadados_fonte for item in items],
            warnings=["Resumo consolidado no nivel oficial disponivel para o Distrito Federal."],
        )

    async def fetch_dashboard_legacy(self, filters: EducensoAnalysisFilters) -> EducensoDashboardResponse:
        summary = await self.fetch_df_summary(year=filters.year, source="sidra")
        indicators_response = await self.fetch_df_indicators(
            year=filters.year,
            theme=None,
            indicator=None,
            source="sidra",
        )
        heatmap_response = await self.fetch_df_heatmap(year=filters.year, indicator="internet_access_pct", source="sidra")

        trend_by_year: dict[int, dict[str, float | None]] = {}
        for indicator_item in indicators_response.indicadores:
            for point in indicator_item.serie_historica:
                trend_row = trend_by_year.setdefault(
                    point.ano,
                    {
                        "taxaMatricula": None,
                        "taxaFrequenciaEscolar": None,
                        "taxaAnalfabetismo": None,
                        "rendaPerCapita": None,
                        "acessoInternetPerc": None,
                        "acessoSaneamentoPerc": None,
                    },
                )
                if indicator_item.indicador == "school_attendance_rate":
                    trend_row["taxaFrequenciaEscolar"] = point.valor
                elif indicator_item.indicador == "illiteracy_rate_15_plus":
                    trend_row["taxaAnalfabetismo"] = point.valor
                elif indicator_item.indicador == "internet_access_pct":
                    trend_row["acessoInternetPerc"] = point.valor
                elif indicator_item.indicador == "adequate_housing_pct":
                    trend_row["acessoSaneamentoPerc"] = point.valor

        return EducensoDashboardResponse(
            filters=EducensoAnalysisFilters(year=filters.year, uf="DF"),
            filterOptions=EducensoFilterOptions(
                years=sorted({year for year in trend_by_year.keys()}, reverse=True),
                ufs=["DF"],
                municipalities=["Brasilia"],
                censusSectors=[],
                reportTypes=[],
            ),
            indicators=[
                DashboardIndicator(
                    id=item.indicador,
                    label=item.rotulo,
                    value=item.valor_bruto,
                    unit=item.unidade or "",
                    description=item.interpretacao.leitura if item.interpretacao else "Sem interpretacao.",
                )
                for item in indicators_response.indicadores[:6]
            ],
            trend=[DashboardTrendPoint(year=year, **values) for year, values in sorted(trend_by_year.items())],
            comparisons=[
                IndicatorComparisonPoint(
                    id="df",
                    label="Distrito Federal",
                    taxaMatricula=None,
                    taxaFrequenciaEscolar=self._extract_value(indicators_response.indicadores, "school_attendance_rate"),
                    taxaAnalfabetismo=self._extract_value(indicators_response.indicadores, "illiteracy_rate_15_plus"),
                    rendaPerCapita=None,
                    acessoInternetPerc=self._extract_value(indicators_response.indicadores, "internet_access_pct"),
                    acessoSaneamentoPerc=self._extract_value(indicators_response.indicadores, "adequate_housing_pct"),
                )
            ],
            tableRows=[
                AnalyticalTableRow(
                    id=item.indicador,
                    year=item.ano or filters.year or datetime.now(timezone.utc).year,
                    reportType=0,
                    reportTypeLabel="Leitura oficial",
                    locationLabel="Distrito Federal",
                    uf="DF",
                    municipality="Brasilia",
                    enrollmentRate=None,
                    schoolAttendanceRate=item.valor_bruto if item.indicador == "school_attendance_rate" else None,
                    illiteracyRate=item.valor_bruto if item.indicador == "illiteracy_rate_15_plus" else None,
                    perCapitaIncome=None,
                    internetAccess=item.valor_bruto if item.indicador == "internet_access_pct" else None,
                    sanitationAccess=item.valor_bruto if item.indicador == "adequate_housing_pct" else None,
                    likertEducacao=3.0,
                    likertSocioeconomico=3.0,
                    recommendationSummary=item.interpretacao.leitura if item.interpretacao else "Sem leitura.",
                )
                for item in indicators_response.indicadores
            ],
            recommendations=self._legacy_recommendations(indicators_response.indicadores),
            likertSummary=DashboardLikertSummary(
                educacao=self._legacy_likert(indicators_response.indicadores, "educacao"),
                socioeconomico=self._legacy_likert(indicators_response.indicadores, "socioeconomico"),
            ),
            heatMap=DfHeatMapData(
                title="Heat map analitico do DF",
                subtitle="Leitura oficial do recorte disponivel para o Distrito Federal.",
                areas=[
                    DfHeatMapArea(
                        id=area.locality_id,
                        label=area.locality_name,
                        metricLabel=area.indicator_label,
                        metricValue=area.raw_value or 0.0,
                        normalizedValue=area.normalized_value or 0.0,
                        reportCount=1,
                        year=area.year,
                        source="ibge-fastapi",
                        dataStatus=area.status_dado,
                        severity=area.interpretacao.severidade,
                        classificationLabel=area.classification_label,
                        trendDirection=area.interpretacao.direcao_tendencia,
                        explanation=area.interpretacao.metadados_explicacao,
                        sourceReliability=area.interpretacao.confiabilidade_fonte,
                    )
                    for area in heatmap_response.areas
                ],
                sourceLabel="Dados oficiais via backend EduCenso",
                geometryStatus="fallback",
                notes=heatmap_response.warnings,
                dataStatus="oficial",
                sourceReliability="alta",
            ),
            totalRecords=summary.total_registros,
            futureIndicators=["Indicadores INEP", "Saude/Pandemia", "Politicas publicas assistidas por IA"],
            modelNotice=(
                "Os dados desta leitura sao oficiais e integrados via backend. "
                "Quando a fonte nao oferecer granularidade por Regiao Administrativa do DF, o sistema sinaliza essa limitacao."
            ),
        )

    async def fetch_heatmap_legacy(self, filters: EducensoAnalysisFilters) -> DfHeatMapData:
        heatmap = await self.fetch_df_heatmap(year=filters.year, indicator="internet_access_pct", source="sidra")
        return DfHeatMapData(
            title="Heat map analitico do DF",
            subtitle="Leitura oficial do recorte disponivel para o Distrito Federal.",
            areas=[
                DfHeatMapArea(
                    id=area.locality_id,
                    label=area.locality_name,
                    metricLabel=area.indicator_label,
                    metricValue=area.raw_value or 0.0,
                    normalizedValue=area.normalized_value or 0.0,
                    reportCount=1,
                    year=area.year,
                    source="ibge-fastapi",
                    dataStatus=area.status_dado,
                    severity=area.interpretacao.severidade,
                    classificationLabel=area.classification_label,
                    trendDirection=area.interpretacao.direcao_tendencia,
                    explanation=area.interpretacao.metadados_explicacao,
                    sourceReliability=area.interpretacao.confiabilidade_fonte,
                )
                for area in heatmap.areas
            ],
            sourceLabel="Dados oficiais via backend EduCenso",
            geometryStatus="fallback",
            notes=heatmap.warnings,
            dataStatus="oficial",
            sourceReliability="alta",
        )

    def _select_indicator_keys(self, *, theme: str | None, indicator: str | None, source: str | None) -> list[str]:
        if indicator:
            return [indicator] if indicator == "illiteracy_rate_15_plus" or indicator in self._indicator_catalog else []

        keys = list(self._indicator_catalog.keys()) + ["illiteracy_rate_15_plus"]
        if theme:
            keys = [key for key in keys if self._indicator_theme(key) == theme]
        if source:
            keys = [key for key in keys if (self._indicator_catalog.get(key, {}).get("source") or "sidra") == source]
        return keys

    def _indicator_theme(self, key: str) -> str:
        if key == "illiteracy_rate_15_plus":
            return "educacao"
        catalog_item = self._indicator_catalog.get(key)
        return str(catalog_item["theme"]) if catalog_item else "geral"

    async def _build_indicator_value(self, *, key: str, year: int | None) -> NormalizedIndicatorValue:
        if key == "illiteracy_rate_15_plus":
            literacy = await self._build_indicator_value(key="literacy_rate_15_plus", year=year)
            raw_value = round(100 - literacy.valor_bruto, 2) if literacy.valor_bruto is not None else None
            history = [
                IndicatorHistoricalPoint(
                    ano=point.ano,
                    valor=(100 - point.valor) if point.valor is not None else None,
                    status_dado=point.status_dado,
                )
                for point in literacy.serie_historica
            ]
            score = score_from_thresholds(raw_value, (0.0, 25.0), higher_is_better=False)
            return NormalizedIndicatorValue(
                indicador=key,
                rotulo="Taxa de analfabetismo 15+",
                tema="educacao",
                ano=year or literacy.ano,
                unidade="%",
                valor_bruto=raw_value,
                valor_normalizado=score,
                status_dado=literacy.status_dado,
                interpretacao=build_interpretation(
                    indicator_key=key,
                    indicator_label="Taxa de analfabetismo 15+",
                    value=raw_value,
                    score=score,
                    higher_is_better=False,
                    points=history,
                ),
                metadados_fonte=literacy.metadados_fonte,
                avisos=list(literacy.avisos),
                disponibilidade=IndicatorSourceAvailability(
                    disponivel=raw_value is not None,
                    motivo=None if raw_value is not None else "Valor derivado nao disponivel.",
                    fonte_sugerida="SIDRA/IBGE",
                    metadados_fonte=literacy.metadados_fonte,
                ),
                contexto_correlacao=build_correlation_context(key, "educacao"),
                serie_historica=history,
            )

        config = self._indicator_catalog.get(key)
        if not config:
            return self._build_unavailable_indicator(key, None)

        try:
            payload = await self.sidra_client.fetch_historical_series_for_df(
                table_code=config["table_code"],
                variable=config["variable_id"],
                periods=config["periods"],
                classifications=config["classifications"],
                territorial_level=config["territorial_level"],
            )
        except PublicDataError as exc:
            source_metadata = SourceMetadata(
                nome="SIDRA/IBGE",
                endpoint="",
                url="https://servicodados.ibge.gov.br/api/docs/agregados?versao=3",
                codigo_tabela=config["table_code"],
                parametros={},
                obtido_em=datetime.now(timezone.utc),
                confiabilidade="desconhecida",
                granularidade="uf",
                aviso_granularidade="Falha ao consultar a fonte oficial no momento.",
            )
            return NormalizedIndicatorValue(
                indicador=key,
                rotulo=config["label"],
                tema=config["theme"],
                ano=year,
                unidade=config["unit"],
                valor_bruto=None,
                valor_normalizado=None,
                status_dado="indisponivel",
                interpretacao=build_interpretation(
                    indicator_key=key,
                    indicator_label=config["label"],
                    value=None,
                    score=None,
                    higher_is_better=bool(config["higher_is_better"]),
                    points=[],
                ),
                metadados_fonte=source_metadata,
                avisos=[exc.message],
                disponibilidade=IndicatorSourceAvailability(
                    disponivel=False,
                    motivo=exc.message,
                    fonte_sugerida="INEP" if config["theme"] == "educacao" else "SIDRA/IBGE",
                    metadados_fonte=source_metadata,
                ),
                contexto_correlacao=build_correlation_context(key, str(config["theme"])),
                serie_historica=[],
            )

        rows = payload["rows"]
        target_year = year
        if target_year is None and rows:
            years = [self._extract_year(row["periodo"]) for row in rows]
            target_year = max(year_value for year_value in years if year_value is not None)

        history = [
            IndicatorHistoricalPoint(
                ano=year_value,
                valor=row["valor"],
                status_dado="oficial",
            )
            for row in rows
            if (year_value := self._extract_year(row.get("periodo"))) is not None
        ]

        selected_row = next((row for row in rows if self._extract_year(row["periodo"]) == target_year), None) if target_year is not None else None
        if selected_row is None and rows:
            selected_row = next((row for row in reversed(rows) if row["valor"] is not None), rows[-1])

        raw_value = selected_row["valor"] if selected_row else None
        score = score_from_thresholds(raw_value, config["thresholds"], bool(config["higher_is_better"]))
        source_metadata: SourceMetadata = payload["source_metadata"]
        source_metadata = source_metadata.model_copy(
            update={
                "aviso_granularidade": (
                    "A API oficial consultada retorna dados no nivel de UF. "
                    "Nao ha detalhamento oficial por Regiao Administrativa do DF nesta integracao."
                ),
            }
        )

        return NormalizedIndicatorValue(
            indicador=key,
            rotulo=config["label"],
            tema=str(config["theme"]),
            ano=target_year,
            unidade=str(config["unit"]),
            valor_bruto=raw_value,
            valor_normalizado=score,
            status_dado="oficial" if raw_value is not None else "indisponivel",
            interpretacao=build_interpretation(
                indicator_key=key,
                indicator_label=config["label"],
                value=raw_value,
                score=score,
                higher_is_better=bool(config["higher_is_better"]),
                points=history,
            ),
            metadados_fonte=source_metadata,
            avisos=[source_metadata.aviso_granularidade] if source_metadata.aviso_granularidade else [],
            disponibilidade=IndicatorSourceAvailability(
                disponivel=raw_value is not None,
                motivo=None if raw_value is not None else "A fonte oficial nao retornou valor para o recorte.",
                fonte_sugerida=None if raw_value is not None else "INEP" if config["theme"] == "educacao" else "SIDRA/IBGE",
                metadados_fonte=source_metadata,
            ),
            contexto_correlacao=build_correlation_context(key, str(config["theme"])),
            serie_historica=history,
        )

    def _build_unavailable_indicator(self, key: str, theme: str | None) -> NormalizedIndicatorValue:
        source_metadata = SourceMetadata(
            nome="EduCenso",
            endpoint="",
            url=None,
            codigo_tabela=None,
            parametros={},
            obtido_em=datetime.now(timezone.utc),
            confiabilidade="desconhecida",
            granularidade="indefinida",
        )
        return NormalizedIndicatorValue(
            indicador=key,
            rotulo=key.replace("_", " "),
            tema=theme or "geral",
            ano=None,
            unidade=None,
            valor_bruto=None,
            valor_normalizado=None,
            status_dado="indisponivel",
            interpretacao=build_interpretation(
                indicator_key=key,
                indicator_label=key.replace("_", " "),
                value=None,
                score=None,
                higher_is_better=True,
                points=[],
            ),
            metadados_fonte=source_metadata,
            avisos=["Indicador ainda nao confirmado na camada oficial integrada."],
            disponibilidade=IndicatorSourceAvailability(
                disponivel=False,
                motivo="Indicador ainda nao confirmado nas fontes oficiais integradas nesta fase.",
                fonte_sugerida="INEP" if theme == "educacao" else "SIDRA/IBGE",
                metadados_fonte=source_metadata,
            ),
            contexto_correlacao=build_correlation_context(key, theme or "geral"),
            serie_historica=[],
        )

    def _extract_year(self, period: str | None) -> int | None:
        if not period:
            return None
        digits = "".join(character for character in str(period) if character.isdigit())
        return int(digits[:4]) if len(digits) >= 4 else None

    def _extract_value(self, items: list[NormalizedIndicatorValue], key: str) -> float | None:
        return next((item.valor_bruto for item in items if item.indicador == key), None)

    def _legacy_likert(self, items: list[NormalizedIndicatorValue], theme: str) -> LikertInterpretation:
        theme_items = [item for item in items if item.tema == theme and item.valor_normalizado is not None]
        score = 3.0 if not theme_items else 1 + sum((item.valor_normalizado or 0) * 4 for item in theme_items) / len(theme_items)

        if score >= 4:
            label = "Nivel alto"
            level = "alto"
            description = "Leitura agregada favoravel."
            color = "text-emerald-600"
        elif score >= 2.5:
            label = "Nivel moderado"
            level = "moderado"
            description = "Leitura agregada intermediaria."
            color = "text-amber-600"
        else:
            label = "Nivel baixo"
            level = "baixo"
            description = "Leitura agregada mais sensivel."
            color = "text-rose-600"

        return LikertInterpretation(
            numericValue=round(score, 2),
            label=label,
            level=level,
            description=description,
            colorClassName=color,
        )

    def _legacy_recommendations(self, items: list[NormalizedIndicatorValue]) -> list[PublicPolicyRecommendation]:
        recommendations: list[PublicPolicyRecommendation] = []
        seen_titles: set[str] = set()
        for item in items:
            hints: list[RecommendationHint] = item.interpretacao.dicas_recomendacao if item.interpretacao else []
            for hint in hints:
                if hint.titulo in seen_titles:
                    continue
                seen_titles.add(hint.titulo)
                emphasis = "intersectoral"
                if item.tema == "educacao":
                    emphasis = "education"
                elif item.tema == "socioeconomico":
                    emphasis = "socioeconomic"
                recommendations.append(
                    PublicPolicyRecommendation(
                        id=item.indicador,
                        title=hint.titulo,
                        summary=hint.descricao,
                        rationale=item.interpretacao.resumo if item.interpretacao else "Sem racional.",
                        emphasis=emphasis,
                    )
                )
        return recommendations[:6]
