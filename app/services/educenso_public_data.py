from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

from httpx import AsyncClient

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
    AdministrativeRegionIndicator,
    AdministrativeRegionIndicatorsResponse,
    AdministrativeRegionsResponse,
    ChartSeriesPoint,
    DataSourceStatus,
    DataSourcesResponse,
    DfChartsResponse,
    DfHeatmapAreaResponse,
    DfHeatmapResponse,
    DfIndicatorsResponse,
    DfSourcesCatalogResponse,
    DfSummaryResponse,
    HeatmapAreaInterpretation,
    IndicatorHistoricalPoint,
    IndicatorSourceAvailability,
    NormalizedIndicatorValue,
    PublicDatasetSource,
    RecommendationHint,
    SchoolCoverageRecord,
    SchoolCoverageResponse,
    SchoolListResponse,
    SchoolRecord,
    SourceMetadata,
    SummaryCard,
)
from app.services.public_data.df_open_data_client import DfOpenDataClient
from app.services.public_data.exceptions import PublicDataError
from app.services.public_data.geoportal_df_client import GeoportalDfClient
from app.services.public_data.ibge_client import IbgeLocalitiesClient
from app.services.public_data.ibge_malhas_client import IbgeMalhasClient
from app.services.public_data.inep_client import InepClient
from app.services.public_data.normalizers import (
    approximate_circle_geojson,
    build_correlation_context,
    build_interpretation,
    build_join_key,
    coalesce_field,
    normalize_text,
    parse_csv_records,
    parse_float,
    parse_int,
    point_in_feature,
    score_from_thresholds,
)
from app.services.public_data.seedf_client import SeedfClient
from app.services.public_data.sidra_client import SidraClient


SCHOOL_OFFER_DATASET = "unidades-escolares-da-rede-publica-de-ensino-do-distrito-federal-por-oferta"
EARLY_CHILDHOOD_DATASET = "unidades-de-ensino-oferta-educacao-infantil-do-distrito-federal"
ENROLLMENTS_DATASET = "quantidade-de-matriculas-das-modalidades-de-ensino-abrangendo-todas-as-redes-de-ensino-do-df"
SCHOOL_CATALOG_DATASET = "relacao-de-unidades-escolares-abrangendo-todas-as-redes-de-ensino-do-distrito-federal"
INFRASTRUCTURE_DATASET = "2023_educa_escola_infraestrutura_tecnologia_alunos_turno_salas"
DF_SCHOOL_DATA_CACHE_TTL = timedelta(minutes=30)
SEEDF_CACHE_WARNING = "Fonte SEEDF temporariamente indisponível; exibindo dados em cache."
SEEDF_UNAVAILABLE_WARNING = "Fonte SEEDF temporariamente indisponível; dados escolares não disponíveis no momento."


@dataclass(slots=True)
class _DfSchoolDataCacheEntry:
    schools: list[SchoolRecord]
    metadata: list[SourceMetadata]
    warnings: list[str]
    cached_at: datetime


class EducensoPublicDataService:
    _df_school_data_cache: _DfSchoolDataCacheEntry | None = None
    _df_school_data_lock: asyncio.Lock | None = None

    def __init__(self) -> None:
        self.sidra_client = SidraClient()
        self.ibge_client = IbgeLocalitiesClient()
        self.malhas_client = IbgeMalhasClient()
        self.seedf_client = SeedfClient()
        self.geoportal_client = GeoportalDfClient()
        self.df_open_data_client = DfOpenDataClient()
        self.inep_client = InepClient()
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
                        "Os endpoints SIDRA existentes foram preservados.",
                    ],
                ),
                DataSourceStatus(
                    chave="seedf_dados_abertos",
                    nome="SEEDF Dados Abertos",
                    descricao="Fonte principal para localizacao oficial de escolas e enriquecimento escolar do DF.",
                    status="integrado",
                    cobertura="Escolas da rede publica com coordenadas oficiais em datasets geoespaciais da SEEDF.",
                    mensagens=[
                        "Campos complementares podem variar conforme o recurso anual disponivel.",
                        "Quando um atributo nao existir na fonte, o backend retorna null e um aviso estruturado.",
                    ],
                ),
                DataSourceStatus(
                    chave="geoportal_df",
                    nome="Geoportal DF / ArcGIS",
                    descricao="Poligonos oficiais das Regioes Administrativas do Distrito Federal.",
                    status="integrado",
                    cobertura="Granularidade por Regiao Administrativa do DF.",
                    mensagens=[
                        "Usado para melhorar a granularidade territorial do mapa.",
                    ],
                ),
                DataSourceStatus(
                    chave="inep",
                    nome="INEP",
                    descricao="Fonte oficial preparada para futura expansao de indicadores educacionais mais detalhados.",
                    status="parcial",
                    cobertura="Preparado para integracao futura mantendo contrato estavel.",
                    mensagens=[
                        "Nesta fase, os atributos expostos priorizam integracoes online estaveis da SEEDF.",
                    ],
                ),
            ],
            gerado_em=datetime.now(timezone.utc),
        )

    async def fetch_df_sources(self) -> DfSourcesCatalogResponse:
        school_data = await self._load_df_school_data()
        geoportal_metadata = self.geoportal_client.build_source_metadata()
        inep_status = self.inep_client.describe()
        candidates = self.df_open_data_client.list_candidates()

        return DfSourcesCatalogResponse(
            fontes=[
                PublicDatasetSource(
                    id="seedf_schools_offer",
                    nome="SEEDF Dados Abertos - Unidades Escolares da Rede Publica por oferta",
                    descricao="Localizacao oficial das escolas da rede publica com recursos GeoJSON por etapa/modalidade.",
                    status="integrado",
                    url=f"https://data.se.df.gov.br/dataset/{SCHOOL_OFFER_DATASET}",
                    formatos=["GeoJSON", "CSV", "JSON", "XML"],
                    granularidade="escola",
                    ultimo_sucesso_em=school_data["metadata"][0].obtido_em if school_data["metadata"] else None,
                    mensagens=[
                        "Coordenadas oficiais de escolas da rede publica usadas no mapa.",
                    ],
                ),
                PublicDatasetSource(
                    id="seedf_early_childhood",
                    nome="SEEDF Dados Abertos - Educacao Infantil",
                    descricao="Localizacao geoespacial de unidades com oferta de educacao infantil no DF.",
                    status="integrado",
                    url=f"https://data.se.df.gov.br/dataset/{EARLY_CHILDHOOD_DATASET}",
                    formatos=["GeoJSON", "CSV", "JSON", "XML"],
                    granularidade="escola",
                    ultimo_sucesso_em=school_data["metadata"][0].obtido_em if school_data["metadata"] else None,
                    mensagens=[
                        "Complementa a cobertura de etapas escolares no mapa.",
                    ],
                ),
                PublicDatasetSource(
                    id="seedf_enrollments",
                    nome="SEEDF Dados Abertos - Serie Historica de Matriculas",
                    descricao="Base anual de matriculas usada para enriquecimento quando o join por escola for confiavel.",
                    status="integrado",
                    url=f"https://data.se.df.gov.br/dataset/{ENROLLMENTS_DATASET}",
                    formatos=["CSV", "JSON", "GeoJSON", "XML"],
                    granularidade="escola",
                    ultimo_sucesso_em=school_data["metadata"][1].obtido_em if len(school_data["metadata"]) > 1 else None,
                    mensagens=[
                        "Join heuristico por codigo/nome da escola com avisos quando a confianca nao for total.",
                    ],
                ),
                PublicDatasetSource(
                    id="seedf_infrastructure",
                    nome="SEEDF Dados Abertos - Infraestrutura Tecnologica",
                    descricao="Campos complementares de infraestrutura escolar por unidade.",
                    status="integrado",
                    url=f"https://data.se.df.gov.br/dataset/{INFRASTRUCTURE_DATASET}",
                    formatos=["CSV", "GeoJSON", "JSON", "XML"],
                    granularidade="escola",
                    ultimo_sucesso_em=school_data["metadata"][2].obtido_em if len(school_data["metadata"]) > 2 else None,
                    mensagens=[
                        "Usado apenas quando os campos podem ser associados com seguranca suficiente.",
                    ],
                ),
                PublicDatasetSource(
                    id="geoportal_ra",
                    nome="Geoportal DF / ArcGIS - Regioes Administrativas DF 2025",
                    descricao="Poligonos oficiais das Regioes Administrativas do Distrito Federal.",
                    status="integrado",
                    url=str(geoportal_metadata.url or geoportal_metadata.endpoint),
                    formatos=["GeoJSON", "JSON"],
                    granularidade="regiao_administrativa",
                    ultimo_sucesso_em=geoportal_metadata.obtido_em,
                    mensagens=[
                        "Fonte oficial para melhorar a granularidade territorial do mapa.",
                    ],
                ),
                PublicDatasetSource(
                    id="inep_censo_escolar",
                    nome=inep_status.nome,
                    descricao="Catalogo oficial complementar do Censo Escolar.",
                    status="parcial",
                    url=inep_status.url,
                    formatos=["CSV", "XLSX", "microdados"],
                    granularidade="escola",
                    mensagens=[inep_status.motivo],
                ),
                *[
                    PublicDatasetSource(
                        id=f"candidate_{index}",
                        nome=item.nome,
                        descricao="Fonte publica oficial avaliada para futuras expansoes.",
                        status=item.status,  # type: ignore[arg-type]
                        url=item.url,
                        formatos=[],
                        granularidade=None,
                        mensagens=[item.motivo],
                    )
                    for index, item in enumerate(candidates, start=1)
                ],
            ],
            gerado_em=datetime.now(timezone.utc),
            avisos=[
                "O frontend consome apenas o backend; nenhuma chamada publica direta foi adicionada no cliente web.",
            ],
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

    async def fetch_df_administrative_regions(self) -> AdministrativeRegionsResponse:
        try:
            geojson = await self.geoportal_client.fetch_administrative_regions_geojson()
        except PublicDataError as exc:
            raise ApiError(exc.message, 502) from exc

        metadata = self.geoportal_client.build_source_metadata()
        return AdministrativeRegionsResponse(
            total=len(geojson.get("features") or []),
            geojson=geojson,
            source_metadata=metadata,
            warnings=[],
        )

    async def fetch_df_schools(
        self,
        *,
        limit: int | None = None,
        administrative_region: str | None = None,
        education_stage: str | None = None,
    ) -> SchoolListResponse:
        school_data = await self._load_df_school_data()
        schools = self._filter_schools(
            school_data["schools"],
            administrative_region=administrative_region,
            education_stage=education_stage,
        )
        sliced = schools[:limit] if limit else schools
        warnings = list(school_data["warnings"])
        if limit and len(schools) > limit:
            warnings.append(
                f"Foram retornadas {limit} escolas para manter o mapa leve; existem {len(schools)} registros compativeis com o filtro."
            )

        return SchoolListResponse(
            total=len(schools),
            returned=len(sliced),
            limit=limit,
            schools=sliced,
            warnings=warnings,
            source_metadata=school_data["metadata"],
        )

    async def fetch_df_school_map(
        self,
        *,
        limit: int | None = None,
        administrative_region: str | None = None,
        education_stage: str | None = None,
    ) -> SchoolListResponse:
        return await self.fetch_df_schools(
            limit=limit,
            administrative_region=administrative_region,
            education_stage=education_stage,
        )

    async def fetch_df_school_coverage(
        self,
        *,
        limit: int | None = None,
        administrative_region: str | None = None,
        education_stage: str | None = None,
    ) -> SchoolCoverageResponse:
        school_data = await self._load_df_school_data()
        schools = self._filter_schools(
            school_data["schools"],
            administrative_region=administrative_region,
            education_stage=education_stage,
        )
        coverages: list[SchoolCoverageRecord] = []
        for school in schools:
            if school.latitude is None or school.longitude is None:
                continue
            coverages.append(
                SchoolCoverageRecord(
                    school_id=school.id,
                    school_name=school.name,
                    center_latitude=school.latitude,
                    center_longitude=school.longitude,
                    radius_meters=1000,
                    coverage_geometry=approximate_circle_geojson(school.latitude, school.longitude, 1000),
                    source=school.source,
                    source_metadata=school.source_metadata,
                    warnings=list(school.warnings),
                )
            )

        sliced = coverages[:limit] if limit else coverages
        warnings = list(school_data["warnings"])
        if limit and len(coverages) > limit:
            warnings.append(
                f"Foram retornadas {limit} areas de cobertura de 1 km para preservar desempenho; existem {len(coverages)} escolas com coordenadas oficiais."
            )

        return SchoolCoverageResponse(
            total=len(coverages),
            returned=len(sliced),
            limit=limit,
            coverage=sliced,
            warnings=warnings,
            source_metadata=school_data["metadata"],
        )

    async def fetch_df_administrative_region_indicators(self) -> AdministrativeRegionIndicatorsResponse:
        school_data = await self._load_df_school_data()
        buckets: dict[str, AdministrativeRegionIndicator] = {}
        for school in school_data["schools"]:
            region = school.administrative_region or "Nao informado"
            item = buckets.setdefault(
                region,
                AdministrativeRegionIndicator(
                    administrative_region=region,
                    school_count=0,
                    schools_with_official_coordinates=0,
                    enrollment_total=0,
                    available_stages=[],
                    sources=[],
                    warnings=[],
                ),
            )
            item.school_count += 1
            if school.latitude is not None and school.longitude is not None:
                item.schools_with_official_coordinates += 1
            if school.enrollments is not None:
                item.enrollment_total = (item.enrollment_total or 0) + school.enrollments
            if school.education_stage and school.education_stage not in item.available_stages:
                item.available_stages.append(school.education_stage)
            if school.source not in item.sources:
                item.sources.append(school.source)
            for warning in school.warnings:
                if warning not in item.warnings:
                    item.warnings.append(warning)

        indicators = sorted(buckets.values(), key=lambda item: item.school_count, reverse=True)
        for item in indicators:
            item.available_stages.sort()
            item.sources.sort()
            if item.enrollment_total == 0:
                item.enrollment_total = None

        return AdministrativeRegionIndicatorsResponse(
            total_regions=len(indicators),
            indicators=indicators,
            source_metadata=school_data["metadata"],
            warnings=school_data["warnings"],
        )

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
            "Os indicadores socioeconomicos oficiais integrados continuam no nivel de UF. "
            "A granularidade por Regiao Administrativa agora e representada separadamente por camadas territoriais e escolares oficiais."
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
                "Nao ha comparacao oficial por Regiao Administrativa para estes indicadores SIDRA nesta fase.",
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
                subtitle="Leitura oficial agregada do DF com enriquecimento escolar e territorial em camadas separadas.",
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
                geometryStatus="real",
                notes=[
                    *heatmap_response.warnings,
                    "Camadas oficiais de escolas e Regioes Administrativas sao carregadas separadamente no mapa.",
                ],
                dataStatus="oficial",
                sourceReliability="alta",
            ),
            totalRecords=summary.total_registros,
            futureIndicators=["Indicadores INEP", "Saude/Pandemia", "Politicas publicas assistidas por IA"],
            modelNotice=(
                "Os dados desta leitura sao oficiais e integrados via backend. "
                "O mapa agora combina indicador agregado do DF com escolas georreferenciadas e Regioes Administrativas oficiais."
            ),
        )

    async def fetch_heatmap_legacy(self, filters: EducensoAnalysisFilters) -> DfHeatMapData:
        heatmap = await self.fetch_df_heatmap(year=filters.year, indicator="internet_access_pct", source="sidra")
        return DfHeatMapData(
            title="Heat map analitico do DF",
            subtitle="Leitura oficial agregada do DF.",
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
            geometryStatus="real",
            notes=heatmap.warnings,
            dataStatus="oficial",
            sourceReliability="alta",
        )

    async def _load_df_school_data(self) -> dict[str, Any]:
        service_cls = type(self)
        cached = service_cls._df_school_data_cache
        if cached and self._is_school_data_cache_fresh(cached):
            return self._build_school_data_payload(
                schools=cached.schools,
                metadata=cached.metadata,
                warnings=cached.warnings,
            )

        lock = self._get_school_data_lock()
        async with lock:
            cached = service_cls._df_school_data_cache
            if cached and self._is_school_data_cache_fresh(cached):
                return self._build_school_data_payload(
                    schools=cached.schools,
                    metadata=cached.metadata,
                    warnings=cached.warnings,
                )

            refreshed = await self._refresh_df_school_data()
            if refreshed["schools"]:
                service_cls._df_school_data_cache = _DfSchoolDataCacheEntry(
                    schools=refreshed["schools"],
                    metadata=refreshed["metadata"],
                    warnings=refreshed["warnings"],
                    cached_at=datetime.now(timezone.utc),
                )
                return refreshed

            if cached:
                return self._build_school_data_payload(
                    schools=cached.schools,
                    metadata=cached.metadata,
                    warnings=[*cached.warnings, *refreshed["warnings"], SEEDF_CACHE_WARNING],
                )

            return self._build_school_data_payload(
                schools=[],
                metadata=refreshed["metadata"],
                warnings=[*refreshed["warnings"], SEEDF_UNAVAILABLE_WARNING],
            )

    async def _refresh_df_school_data(self) -> dict[str, Any]:
        warnings: list[str] = []
        metadata: list[SourceMetadata] = []
        schools_by_id: dict[str, SchoolRecord] = {}

        async with AsyncClient(
            timeout=self.seedf_client.timeout,
            follow_redirects=True,
        ) as http_client:
            seedf_client = SeedfClient(client=http_client)
            (
                offer_package,
                early_package,
                enrollments_package,
                infrastructure_package,
                catalog_package,
            ) = await asyncio.gather(
                self._fetch_seedf_package(seedf_client, SCHOOL_OFFER_DATASET, warnings=warnings),
                self._fetch_seedf_package(seedf_client, EARLY_CHILDHOOD_DATASET, warnings=warnings),
                self._fetch_seedf_package(seedf_client, ENROLLMENTS_DATASET, warnings=warnings),
                self._fetch_seedf_package(seedf_client, INFRASTRUCTURE_DATASET, warnings=warnings),
                self._fetch_seedf_package(seedf_client, SCHOOL_CATALOG_DATASET, warnings=warnings),
            )

            location_specs = [
                (offer_package, "geojson", "Unidades EM"),
                (offer_package, "geojson", "Unidades EF Anos Iniciais"),
                (offer_package, "geojson", "Unidades EF Anos Finais"),
                (early_package, "geojson", "Mapa_Unidades"),
            ]
            location_results = await asyncio.gather(
                *[
                    self._load_school_location_resource(
                        seedf_client,
                        package_data=package_data,
                        format_name=fmt,
                        contains=contains,
                    )
                    for package_data, fmt, contains in location_specs
                    if package_data
                ]
            )

            for result in location_results:
                metadata.extend(result["metadata"])
                warnings.extend(result["warnings"])
                for school in result["schools"]:
                    existing = schools_by_id.get(school.id)
                    if existing is None:
                        schools_by_id[school.id] = school
                        continue
                    merged_stages = {item for item in [existing.education_stage, school.education_stage] if item}
                    existing.education_stage = " / ".join(sorted(merged_stages)) if merged_stages else existing.education_stage
                    existing.warnings = sorted(set([*existing.warnings, *school.warnings]))

            schools = list(schools_by_id.values())
            school_index = self._build_school_index(schools)

            catalog_result, enrollments_result, infrastructure_result = await asyncio.gather(
                self._load_school_csv_resource(
                    seedf_client,
                    package_data=catalog_package,
                    format_name="csv",
                    contains="Relatorio_Escolas_2024",
                    missing_warning="Catalogo anual de escolas da SEEDF nao foi localizado em CSV para enriquecimento complementar.",
                ),
                self._load_school_csv_resource(
                    seedf_client,
                    package_data=enrollments_package,
                    format_name="csv",
                    contains="Relatorio_Matriculas_2024",
                    missing_warning="Base anual de matriculas da SEEDF nao foi localizada em CSV para o ano mais recente esperado.",
                ),
                self._load_school_csv_resource(
                    seedf_client,
                    package_data=infrastructure_package,
                    format_name="csv",
                    contains="2024_",
                    missing_warning="Base anual de infraestrutura tecnologica da SEEDF nao foi localizada em CSV para 2024.",
                ),
            )

        for result in [catalog_result, enrollments_result, infrastructure_result]:
            metadata.extend(result["metadata"])
            warnings.extend(result["warnings"])

        if catalog_result["records"]:
            self._merge_school_catalog(schools, school_index, catalog_result["records"])
        if enrollments_result["records"]:
            self._merge_enrollments(schools, school_index, enrollments_result["records"])
        if infrastructure_result["records"]:
            self._merge_infrastructure(schools, school_index, infrastructure_result["records"])

        try:
            regions_geojson = await self.geoportal_client.fetch_administrative_regions_geojson()
        except PublicDataError:
            regions_geojson = {"type": "FeatureCollection", "features": []}
            warnings.append("Nao foi possivel cruzar escolas com Regioes Administrativas oficiais nesta consulta.")

        region_features = regions_geojson.get("features") if isinstance(regions_geojson, dict) else []
        if isinstance(region_features, list):
            for school in schools:
                if school.administrative_region or school.latitude is None or school.longitude is None:
                    continue
                matched_region = next(
                    (
                        feature
                        for feature in region_features
                        if isinstance(feature, dict) and point_in_feature(school.latitude, school.longitude, feature)
                    ),
                    None,
                )
                if matched_region:
                    properties = matched_region.get("properties") or {}
                    if isinstance(properties, dict):
                        school.administrative_region = self._string_value(
                            properties.get("name") or properties.get("ra_nome")
                        )

        for school in schools:
            if school.latitude is None or school.longitude is None:
                school.warnings.append("A escola nao possui coordenadas oficiais disponiveis na fonte integrada.")
            if school.administrative_region is None:
                school.warnings.append("A Regiao Administrativa nao foi informada de forma confiavel na fonte oficial integrada.")
            school.warnings = sorted(set(school.warnings))

        schools.sort(key=lambda item: item.name)
        return self._build_school_data_payload(
            schools=schools,
            metadata=metadata,
            warnings=warnings,
        )

    @classmethod
    def _get_school_data_lock(cls) -> asyncio.Lock:
        if cls._df_school_data_lock is None:
            cls._df_school_data_lock = asyncio.Lock()
        return cls._df_school_data_lock

    @staticmethod
    def _is_school_data_cache_fresh(cache: _DfSchoolDataCacheEntry) -> bool:
        return datetime.now(timezone.utc) - cache.cached_at <= DF_SCHOOL_DATA_CACHE_TTL

    def _build_school_data_payload(
        self,
        *,
        schools: list[SchoolRecord],
        metadata: list[SourceMetadata],
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "schools": schools,
            "metadata": metadata,
            "warnings": sorted(set(warnings)),
        }

    async def _fetch_seedf_package(
        self,
        seedf_client: SeedfClient,
        dataset_slug: str,
        *,
        warnings: list[str],
    ) -> dict[str, Any] | None:
        try:
            return await seedf_client.fetch_package(dataset_slug)
        except PublicDataError as exc:
            warnings.append(f"Falha ao consultar metadados SEEDF para {dataset_slug}: {exc.message}")
            return None

    async def _load_school_location_resource(
        self,
        seedf_client: SeedfClient,
        *,
        package_data: dict[str, Any],
        format_name: str,
        contains: str,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        metadata: list[SourceMetadata] = []
        resource = seedf_client.pick_resource(package_data, format_name=format_name, contains=contains)
        if not resource or not resource.get("url"):
            warnings.append(f"Recurso oficial nao encontrado para {contains}.")
            return {"schools": [], "metadata": metadata, "warnings": warnings}

        try:
            payload = await seedf_client.fetch_resource_json(str(resource["url"]))
        except PublicDataError as exc:
            warnings.append(f"Falha ao baixar recurso escolar da SEEDF para {contains}: {exc.message}")
            return {"schools": [], "metadata": metadata, "warnings": warnings}

        source_metadata = seedf_client.build_source_metadata(
            package_data=package_data,
            resource=resource,
            endpoint=str(resource["url"]),
            granularidade="escola",
        )
        metadata.append(source_metadata)
        return {
            "schools": self._normalize_school_geojson(payload, source_metadata=source_metadata),
            "metadata": metadata,
            "warnings": warnings,
        }

    async def _load_school_csv_resource(
        self,
        seedf_client: SeedfClient,
        *,
        package_data: dict[str, Any] | None,
        format_name: str,
        contains: str,
        missing_warning: str,
    ) -> dict[str, Any]:
        if not package_data:
            return {"records": [], "metadata": [], "warnings": [missing_warning]}

        resource = seedf_client.pick_resource(package_data, format_name=format_name, contains=contains)
        if not resource or not resource.get("url"):
            return {"records": [], "metadata": [], "warnings": [missing_warning]}

        metadata = [
            seedf_client.build_source_metadata(
                package_data=package_data,
                resource=resource,
                endpoint=str(resource["url"]),
                granularidade="escola",
            )
        ]
        try:
            payload = await seedf_client.fetch_resource_text(str(resource["url"]))
        except PublicDataError as exc:
            return {
                "records": [],
                "metadata": metadata,
                "warnings": [f"Falha ao baixar arquivo escolar complementar da SEEDF para {contains}: {exc.message}"],
            }

        return {
            "records": parse_csv_records(payload),
            "metadata": metadata,
            "warnings": [],
        }

    def _normalize_school_geojson(self, payload: Any, *, source_metadata: SourceMetadata) -> list[SchoolRecord]:
        if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
            return []
        features = payload.get("features")
        if not isinstance(features, list):
            return []

        items: list[SchoolRecord] = []
        for index, feature in enumerate(features):
            if not isinstance(feature, dict):
                continue
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
            properties = feature.get("properties") or {}
            if not isinstance(properties, dict):
                properties = {}

            longitude = None
            latitude = None
            if isinstance(coordinates, list) and len(coordinates) >= 2:
                longitude = parse_float(coordinates[0])
                latitude = parse_float(coordinates[1])

            school_name = self._string_value(
                coalesce_field(properties, ["NO_ENTIDADE", "nome", "NOME", "ESCOLA", "escola", "instituicao"])
            ) or f"Escola {index + 1}"
            school_code = self._string_value(
                coalesce_field(properties, ["CO_ENTIDADE", "co_entidade", "id_escola", "ID", "id"])
            ) or normalize_text(school_name).replace(" ", "-")

            network = self._string_value(
                coalesce_field(properties, ["REDE", "rede", "TP_REDE", "dependencia_administrativa", "DEPENDENCIA"])
            )
            region = self._string_value(
                coalesce_field(properties, ["REGIAO_ADMINISTRATIVA", "ra", "RA", "regional_ensino", "REGIONAL"])
            )
            address = self._string_value(
                coalesce_field(properties, ["ENDERECO", "endereco", "logradouro", "DS_ENDERECO", "END"])
            )
            stage = self._infer_education_stage(properties, source_metadata)

            warnings: list[str] = []
            if latitude is None or longitude is None:
                warnings.append("Coordenadas oficiais ausentes no recurso geoespacial desta escola.")

            items.append(
                SchoolRecord(
                    id=school_code,
                    name=school_name,
                    network_type=network,
                    education_stage=stage,
                    administrative_region=region,
                    address=address,
                    latitude=latitude,
                    longitude=longitude,
                    source="SEEDF Dados Abertos",
                    source_metadata=source_metadata,
                    warnings=warnings,
                    modality=self._string_value(coalesce_field(properties, ["MODALIDADE", "modalidade"])),
                    vacancies=parse_int(coalesce_field(properties, ["VAGAS", "vagas", "capacidade_atendimento"])),
                    inep_school_code=school_code,
                    attributes=self._safe_attributes(properties),
                )
            )

        return items

    def _build_school_index(self, schools: list[SchoolRecord]) -> dict[str, SchoolRecord]:
        index: dict[str, SchoolRecord] = {}
        for school in schools:
            for key in {
                build_join_key(school.id),
                build_join_key(school.inep_school_code),
                build_join_key(school.name),
                build_join_key(school.id, school.name),
            }:
                if key:
                    index[key] = school
        return index

    def _match_school(self, school_index: dict[str, SchoolRecord], record: dict[str, Any]) -> SchoolRecord | None:
        code = self._string_value(
            coalesce_field(record, ["CO_ENTIDADE", "co_entidade", "id_escola", "inep", "codigo_escola", "NO_ENTIDADE"])
        )
        name = self._string_value(coalesce_field(record, ["NO_ENTIDADE", "nome", "escola", "ESCOLA"]))
        for key in [
            build_join_key(code),
            build_join_key(name),
            build_join_key(code, name),
        ]:
            if key and key in school_index:
                return school_index[key]
        return None

    def _merge_school_catalog(self, schools: list[SchoolRecord], school_index: dict[str, SchoolRecord], records: list[dict[str, Any]]) -> None:
        for record in records:
            school = self._match_school(school_index, record)
            if school is None:
                continue
            school.network_type = school.network_type or self._string_value(
                coalesce_field(record, ["TP_DEPENDENCIA", "dependencia_administrativa", "REDE"])
            )
            school.address = school.address or self._string_value(
                coalesce_field(record, ["DS_ENDERECO", "ENDERECO", "logradouro"])
            )
            school.administrative_region = school.administrative_region or self._string_value(
                coalesce_field(record, ["NO_REGIAO", "RA", "REGIAO_ADMINISTRATIVA", "regional_ensino"])
            )
            school.inep_school_code = school.inep_school_code or self._string_value(
                coalesce_field(record, ["CO_ENTIDADE", "co_entidade"])
            )

    def _merge_enrollments(self, schools: list[SchoolRecord], school_index: dict[str, SchoolRecord], records: list[dict[str, Any]]) -> None:
        for record in records:
            school = self._match_school(school_index, record)
            if school is None:
                continue
            school.enrollments = school.enrollments or parse_int(
                coalesce_field(
                    record,
                    ["QT_MAT_BAS", "QT_MATRICULAS", "matriculas", "TOTAL_MATRICULAS", "quantidade_matriculas"],
                )
            )

    def _merge_infrastructure(self, schools: list[SchoolRecord], school_index: dict[str, SchoolRecord], records: list[dict[str, Any]]) -> None:
        for record in records:
            school = self._match_school(school_index, record)
            if school is None:
                continue
            infrastructure = school.infrastructure or {}
            for target_key, candidates in {
                "internet_banda_larga": ["INTERNET_BANDA_LARGA", "internet_banda_larga"],
                "laboratorio_informatica": ["LABORATORIO_INFORMATICA", "laboratorio_informatica"],
                "quantidade_salas": ["QT_SALAS_UTILIZADAS", "quantidade_salas", "salas_utilizadas"],
                "equipamentos_alunos": ["QT_EQUIPAMENTOS_ALUNOS", "equipamentos_alunos"],
            }.items():
                raw = coalesce_field(record, candidates)
                if raw in (None, ""):
                    continue
                infrastructure[target_key] = parse_int(raw) if parse_int(raw) is not None else self._string_value(raw)
            school.infrastructure = infrastructure or None

    def _filter_schools(
        self,
        schools: list[SchoolRecord],
        *,
        administrative_region: str | None,
        education_stage: str | None,
    ) -> list[SchoolRecord]:
        filtered = schools
        if administrative_region:
            desired_region = normalize_text(administrative_region)
            filtered = [
                school for school in filtered if normalize_text(school.administrative_region) == desired_region
            ]
        if education_stage:
            desired_stage = normalize_text(education_stage)
            filtered = [
                school for school in filtered if desired_stage in normalize_text(school.education_stage)
            ]
        return filtered

    def _infer_education_stage(self, properties: dict[str, Any], source_metadata: SourceMetadata) -> str | None:
        explicit = self._string_value(coalesce_field(properties, ["ETAPA", "etapa", "MODALIDADE", "modalidade"]))
        if explicit:
            return explicit
        resource_name = normalize_text(source_metadata.recurso)
        if "anos iniciais" in resource_name:
            return "Ensino Fundamental - Anos Iniciais"
        if "anos finais" in resource_name:
            return "Ensino Fundamental - Anos Finais"
        if "em" in resource_name or "medio" in resource_name:
            return "Ensino Medio"
        if "infantil" in resource_name:
            return "Educacao Infantil"
        return None

    def _safe_attributes(self, properties: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
        sanitized: dict[str, str | int | float | bool | None] = {}
        for key, value in properties.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                sanitized[str(key)] = value
        return sanitized

    def _string_value(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

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
