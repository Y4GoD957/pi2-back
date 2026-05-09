from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DataStatus = Literal["oficial", "estimado", "indisponivel", "simulado"]
SeverityLevel = Literal["baixo", "moderado", "alto", "critico", "indefinido"]
TrendDirection = Literal["melhora", "piora", "estavel", "insuficiente", "indefinido"]
ReliabilityLevel = Literal["alta", "media", "baixa", "desconhecida"]
CorrelationDimension = Literal["educacao", "socioeconomico", "localidade", "saude_futura"]


class SourceMetadata(BaseModel):
    nome: str
    endpoint: str
    url: str | None = None
    codigo_tabela: str | None = None
    parametros: dict[str, str] = Field(default_factory=dict)
    obtido_em: datetime
    confiabilidade: ReliabilityLevel = "desconhecida"
    granularidade: str | None = None
    aviso_granularidade: str | None = None


class RecommendationHint(BaseModel):
    titulo: str
    descricao: str
    prioridade: SeverityLevel = "indefinido"
    relacionado_a: list[str] = Field(default_factory=list)


class TrendInterpretation(BaseModel):
    direcao: TrendDirection = "indefinido"
    descricao: str
    variacao_absoluta: float | None = None
    variacao_percentual: float | None = None


class IndicatorInterpretation(BaseModel):
    resumo: str
    nivel_severidade: SeverityLevel = "indefinido"
    score_normalizado: float | None = None
    leitura: str | None = None
    tendencia: TrendInterpretation | None = None
    dicas_recomendacao: list[RecommendationHint] = Field(default_factory=list)
    explicacao: str | None = None


class IndicatorSourceAvailability(BaseModel):
    disponivel: bool
    motivo: str | None = None
    fonte_sugerida: str | None = None
    metadados_fonte: SourceMetadata | None = None


class CorrelationContext(BaseModel):
    dimensoes: list[CorrelationDimension] = Field(default_factory=list)
    chaves_correlacao: list[str] = Field(default_factory=list)
    pronto_para_ia: bool = True


class IndicatorHistoricalPoint(BaseModel):
    ano: int
    valor: float | None = None
    status_dado: DataStatus = "oficial"


class NormalizedIndicatorValue(BaseModel):
    indicador: str
    rotulo: str
    tema: str
    ano: int | None = None
    unidade: str | None = None
    valor_bruto: float | None = None
    valor_normalizado: float | None = None
    status_dado: DataStatus = "oficial"
    interpretacao: IndicatorInterpretation | None = None
    metadados_fonte: SourceMetadata
    avisos: list[str] = Field(default_factory=list)
    disponibilidade: IndicatorSourceAvailability
    contexto_correlacao: CorrelationContext = Field(default_factory=CorrelationContext)
    serie_historica: list[IndicatorHistoricalPoint] = Field(default_factory=list)


class DataSourceStatus(BaseModel):
    chave: str
    nome: str
    descricao: str
    status: Literal["integrado", "parcial", "pendente"]
    cobertura: str
    mensagens: list[str] = Field(default_factory=list)


class DataSourcesResponse(BaseModel):
    fontes: list[DataSourceStatus]
    gerado_em: datetime


class DfIndicatorsResponse(BaseModel):
    ano: int | None = None
    tema: str | None = None
    indicador: str | None = None
    fonte: str | None = None
    indicadores: list[NormalizedIndicatorValue]
    avisos: list[str] = Field(default_factory=list)


class HeatmapAreaInterpretation(BaseModel):
    classificacao: str | None = None
    severidade: SeverityLevel = "indefinido"
    interpretacao: str | None = None
    direcao_tendencia: TrendDirection = "indefinido"
    metadados_explicacao: str | None = None
    confiabilidade_fonte: ReliabilityLevel = "desconhecida"


class DfHeatmapAreaResponse(BaseModel):
    locality_id: str
    locality_name: str
    ibge_code: str | None = None
    uf: str
    year: int | None = None
    indicator_key: str
    indicator_label: str
    raw_value: float | None = None
    normalized_value: float | None = None
    unit: str | None = None
    classification_level: str | None = None
    classification_label: str | None = None
    source: str
    source_metadata: SourceMetadata
    status_dado: DataStatus = "oficial"
    interpretacao: HeatmapAreaInterpretation
    warnings: list[str] = Field(default_factory=list)


class DfHeatmapResponse(BaseModel):
    year: int | None = None
    indicator: str | None = None
    source: str | None = None
    areas: list[DfHeatmapAreaResponse]
    warnings: list[str] = Field(default_factory=list)


class ChartSeriesPoint(BaseModel):
    label: str
    value: float | None
    year: int | None = None
    status_dado: DataStatus = "oficial"


class DfChartsResponse(BaseModel):
    year: int | None = None
    indicator: str | None = None
    source: str | None = None
    bar_chart_data: list[ChartSeriesPoint] = Field(default_factory=list)
    historical_series: list[ChartSeriesPoint] = Field(default_factory=list)
    table_data: list[dict[str, str | float | int | None]] = Field(default_factory=list)
    source_metadata: list[SourceMetadata] = Field(default_factory=list)
    recommendation_hints: list[RecommendationHint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SummaryCard(BaseModel):
    id: str
    label: str
    valor: float | None = None
    unidade: str | None = None
    descricao: str | None = None
    status_dado: DataStatus = "oficial"


class DfSummaryResponse(BaseModel):
    year: int | None = None
    source: str | None = None
    summary_cards: list[SummaryCard]
    total_registros: int
    media: float | None = None
    minimo: float | None = None
    maximo: float | None = None
    source_metadata: list[SourceMetadata] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
