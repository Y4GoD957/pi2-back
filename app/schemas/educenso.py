from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Perfil(BaseModel):
    idPerfil: int
    descricao: str
    dataCriacao: datetime | None = None


class Usuario(BaseModel):
    idUsuario: int
    nome: str
    dataNascimento: datetime | None = None
    cpf: str | None = None
    email: str
    telefone: str | None = None
    endereco: str | None = None
    dataCriacao: datetime | None = None
    idPerfil: int | None = None


class Localidade(BaseModel):
    idLocalidade: int
    codigoIbge: int
    uf: str
    municipio: str
    setorCensitario: str | None = None
    dataCriacao: datetime | None = None


class FatoEducacao(BaseModel):
    idFatoEducacao: int
    ano: int
    taxaMatricula: float
    taxaFrequenciaEscolar: float
    taxaAnalfabetismo: float
    dataCriacao: datetime | None = None


class FatoSocioeconomico(BaseModel):
    idFatoSocioeconomico: int
    ano: int
    rendaPerCapita: float | None = None
    acessoInternetPerc: float | None = None
    acessoSaneamentoPerc: float | None = None
    dataCriacao: datetime | None = None


class Relatorio(BaseModel):
    idRelatorio: int
    tipo: int
    likertEducacao: float
    likertSocioeconomico: float
    avaliacao: str
    filtrosAplicados: str | None = None
    politicaPublica: str
    dataCriacao: datetime | None = None
    idUsuario: int
    idFatoEducacao: int
    idFatoSocioeconomico: int
    idDimLocalidade: int
    localidade: Localidade | None = None
    fatoEducacao: FatoEducacao | None = None
    fatoSocioeconomico: FatoSocioeconomico | None = None


class EducensoAnalysisFilters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    year: int | None = None
    uf: str | None = None
    municipality: str | None = None
    censusSector: str | None = None
    reportType: int | None = None


class EducensoFilterOptions(BaseModel):
    years: list[int]
    ufs: list[str]
    municipalities: list[str]
    censusSectors: list[str]
    reportTypes: list[int]


class AnalysisRecord(BaseModel):
    report: Relatorio
    localidade: Localidade
    fatoEducacao: FatoEducacao
    fatoSocioeconomico: FatoSocioeconomico


class DashboardIndicator(BaseModel):
    id: str
    label: str
    value: float | None
    unit: str
    description: str


class DashboardTrendPoint(BaseModel):
    year: int
    taxaMatricula: float | None
    taxaFrequenciaEscolar: float | None
    taxaAnalfabetismo: float | None
    rendaPerCapita: float | None
    acessoInternetPerc: float | None
    acessoSaneamentoPerc: float | None


class IndicatorComparisonPoint(BaseModel):
    id: str
    label: str
    taxaMatricula: float | None
    taxaFrequenciaEscolar: float | None
    taxaAnalfabetismo: float | None
    rendaPerCapita: float | None
    acessoInternetPerc: float | None
    acessoSaneamentoPerc: float | None


class AnalyticalTableRow(BaseModel):
    id: str
    year: int
    reportType: int
    reportTypeLabel: str
    locationLabel: str
    uf: str
    municipality: str
    censusSector: str | None = None
    enrollmentRate: float | None
    schoolAttendanceRate: float | None
    illiteracyRate: float | None
    perCapitaIncome: float | None
    internetAccess: float | None
    sanitationAccess: float | None
    likertEducacao: float
    likertSocioeconomico: float
    recommendationSummary: str


class PublicPolicyRecommendation(BaseModel):
    id: str
    title: str
    summary: str
    rationale: str
    emphasis: str


class LikertInterpretation(BaseModel):
    numericValue: float
    label: str
    level: str
    description: str
    colorClassName: str


class DashboardLikertSummary(BaseModel):
    educacao: LikertInterpretation
    socioeconomico: LikertInterpretation


class DfHeatMapArea(BaseModel):
    id: str
    label: str
    metricLabel: str
    metricValue: float
    normalizedValue: float
    reportCount: int
    year: int | None = None
    svgPath: str | None = None
    source: str


class DfHeatMapData(BaseModel):
    title: str
    subtitle: str
    areas: list[DfHeatMapArea]
    sourceLabel: str
    geometryStatus: str
    notes: list[str]


class EducensoDashboardResponse(BaseModel):
    filters: EducensoAnalysisFilters
    filterOptions: EducensoFilterOptions
    indicators: list[DashboardIndicator]
    trend: list[DashboardTrendPoint]
    comparisons: list[IndicatorComparisonPoint]
    tableRows: list[AnalyticalTableRow]
    recommendations: list[PublicPolicyRecommendation]
    likertSummary: DashboardLikertSummary
    heatMap: DfHeatMapData
    totalRecords: int
    futureIndicators: list[str]
    modelNotice: str | None = None


class ReportListItem(BaseModel):
    report: Relatorio
    reportTypeLabel: str
    locationLabel: str
    recommendation: PublicPolicyRecommendation


class ReportDetailResponse(ReportListItem):
    pass


class CreateReportPayload(BaseModel):
    year: int
    localidadeId: int
    tipo: int
    avaliacao: str
    politicaPublica: str | None = None
    filtrosAplicados: str | None = None


class ReportFormOptions(BaseModel):
    years: list[int]
    localities: list[Localidade]


class ReportCreatedResponse(ReportListItem):
    pass
