from collections import defaultdict

from app.schemas.educenso import (
    AnalysisRecord,
    AnalyticalTableRow,
    DashboardIndicator,
    DashboardTrendPoint,
    EducensoAnalysisFilters,
    EducensoFilterOptions,
    IndicatorComparisonPoint,
)

MODELING_NOTICE = (
    "A analise atual depende das relacoes presentes em relatorio, pois as tabelas "
    "fato_educacao e fato_socioeconomico nao possuem chave direta de localidade "
    "na modelagem informada."
)


def format_location_label(record: AnalysisRecord) -> str:
    sector = (record.localidade.setorCensitario or "").strip()
    if sector:
        return f"{record.localidade.municipio} - {record.localidade.uf} ({sector})"
    return f"{record.localidade.municipio} - {record.localidade.uf}"


def get_report_type_label(report_type: int) -> str:
    return f"Tipo {report_type}"


def normalize_filters(
    filters: EducensoAnalysisFilters,
    forced_uf: str | None = None,
) -> EducensoAnalysisFilters:
    return EducensoAnalysisFilters(
        year=filters.year,
        uf=forced_uf or filters.uf,
        municipality=filters.municipality,
        censusSector=filters.censusSector,
        reportType=filters.reportType,
    )


def build_filters_applied_label(filters: dict[str, int | str | None]) -> str:
    parts: list[str] = []
    if filters.get("year"):
        parts.append(f"Ano: {filters['year']}")
    if filters.get("uf"):
        parts.append(f"UF: {filters['uf']}")
    if filters.get("municipality"):
        parts.append(f"Municipio: {filters['municipality']}")
    if filters.get("censusSector"):
        parts.append(f"Setor censitario: {filters['censusSector']}")
    if filters.get("reportType"):
        parts.append(f"Tipo: {filters['reportType']}")
    return " | ".join(parts) if parts else "Sem filtros adicionais."


def build_filter_options(records: list[AnalysisRecord]) -> EducensoFilterOptions:
    years = sorted({record.fatoEducacao.ano for record in records}, reverse=True)
    ufs = sorted({record.localidade.uf for record in records})
    municipalities = sorted({record.localidade.municipio for record in records})
    census_sectors = sorted(
        {
            record.localidade.setorCensitario
            for record in records
            if record.localidade.setorCensitario
        }
    )
    report_types = sorted({record.report.tipo for record in records})
    return EducensoFilterOptions(
        years=years,
        ufs=ufs,
        municipalities=municipalities,
        censusSectors=census_sectors,
        reportTypes=report_types,
    )


def dedupe_analysis_records(records: list[AnalysisRecord]) -> list[AnalysisRecord]:
    unique: dict[str, AnalysisRecord] = {}
    for record in records:
        key = (
            f"{record.localidade.idLocalidade}:"
            f"{record.fatoEducacao.idFatoEducacao}:"
            f"{record.fatoSocioeconomico.idFatoSocioeconomico}:"
            f"{record.fatoEducacao.ano}"
        )
        unique.setdefault(key, record)
    return list(unique.values())


def _average(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def build_dashboard_indicators(records: list[AnalysisRecord]) -> list[DashboardIndicator]:
    return [
        DashboardIndicator(
            id="taxaMatricula",
            label="Taxa de matricula",
            value=_average([record.fatoEducacao.taxaMatricula for record in records]),
            unit="%",
            description="Media consolidada da taxa de matricula no recorte filtrado.",
        ),
        DashboardIndicator(
            id="taxaFrequenciaEscolar",
            label="Taxa de frequencia escolar",
            value=_average([record.fatoEducacao.taxaFrequenciaEscolar for record in records]),
            unit="%",
            description="Presenca media escolar observada no conjunto selecionado.",
        ),
        DashboardIndicator(
            id="taxaAnalfabetismo",
            label="Taxa de analfabetismo",
            value=_average([record.fatoEducacao.taxaAnalfabetismo for record in records]),
            unit="%",
            description="Quanto menor esse indice, melhor a leitura educacional.",
        ),
        DashboardIndicator(
            id="rendaPerCapita",
            label="Renda per capita",
            value=_average([record.fatoSocioeconomico.rendaPerCapita for record in records]),
            unit="R$",
            description="Media de renda per capita nas observacoes filtradas.",
        ),
        DashboardIndicator(
            id="acessoInternetPerc",
            label="Acesso a internet",
            value=_average([record.fatoSocioeconomico.acessoInternetPerc for record in records]),
            unit="%",
            description="Percentual medio de acesso a internet no recorte.",
        ),
        DashboardIndicator(
            id="acessoSaneamentoPerc",
            label="Acesso a saneamento",
            value=_average([record.fatoSocioeconomico.acessoSaneamentoPerc for record in records]),
            unit="%",
            description="Percentual medio de acesso a saneamento no recorte.",
        ),
    ]


def build_trend_data(records: list[AnalysisRecord]) -> list[DashboardTrendPoint]:
    grouped: dict[int, list[AnalysisRecord]] = defaultdict(list)
    for record in records:
        grouped[record.fatoEducacao.ano].append(record)

    points: list[DashboardTrendPoint] = []
    for year in sorted(grouped):
        year_records = grouped[year]
        points.append(
            DashboardTrendPoint(
                year=year,
                taxaMatricula=_average([item.fatoEducacao.taxaMatricula for item in year_records]),
                taxaFrequenciaEscolar=_average(
                    [item.fatoEducacao.taxaFrequenciaEscolar for item in year_records]
                ),
                taxaAnalfabetismo=_average([item.fatoEducacao.taxaAnalfabetismo for item in year_records]),
                rendaPerCapita=_average([item.fatoSocioeconomico.rendaPerCapita for item in year_records]),
                acessoInternetPerc=_average(
                    [item.fatoSocioeconomico.acessoInternetPerc for item in year_records]
                ),
                acessoSaneamentoPerc=_average(
                    [item.fatoSocioeconomico.acessoSaneamentoPerc for item in year_records]
                ),
            )
        )
    return points


def build_comparison_data(records: list[AnalysisRecord]) -> list[IndicatorComparisonPoint]:
    grouped: dict[str, list[AnalysisRecord]] = defaultdict(list)
    for record in records:
        grouped[format_location_label(record)].append(record)

    items = [
        IndicatorComparisonPoint(
            id=label,
            label=label,
            taxaMatricula=_average([item.fatoEducacao.taxaMatricula for item in group]),
            taxaFrequenciaEscolar=_average(
                [item.fatoEducacao.taxaFrequenciaEscolar for item in group]
            ),
            taxaAnalfabetismo=_average([item.fatoEducacao.taxaAnalfabetismo for item in group]),
            rendaPerCapita=_average([item.fatoSocioeconomico.rendaPerCapita for item in group]),
            acessoInternetPerc=_average([item.fatoSocioeconomico.acessoInternetPerc for item in group]),
            acessoSaneamentoPerc=_average(
                [item.fatoSocioeconomico.acessoSaneamentoPerc for item in group]
            ),
        )
        for label, group in grouped.items()
    ]
    return sorted(items, key=lambda item: item.taxaMatricula or 0.0, reverse=True)[:6]


def build_analytical_table_rows(
    records: list[AnalysisRecord],
    recommendation_summary_by_key: dict[str, str],
) -> list[AnalyticalTableRow]:
    rows = [
        AnalyticalTableRow(
            id=(
                f"{record.localidade.idLocalidade}:"
                f"{record.fatoEducacao.idFatoEducacao}:"
                f"{record.fatoSocioeconomico.idFatoSocioeconomico}"
            ),
            year=record.fatoEducacao.ano,
            reportType=record.report.tipo,
            reportTypeLabel=get_report_type_label(record.report.tipo),
            locationLabel=format_location_label(record),
            uf=record.localidade.uf,
            municipality=record.localidade.municipio,
            censusSector=record.localidade.setorCensitario,
            enrollmentRate=record.fatoEducacao.taxaMatricula,
            schoolAttendanceRate=record.fatoEducacao.taxaFrequenciaEscolar,
            illiteracyRate=record.fatoEducacao.taxaAnalfabetismo,
            perCapitaIncome=record.fatoSocioeconomico.rendaPerCapita,
            internetAccess=record.fatoSocioeconomico.acessoInternetPerc,
            sanitationAccess=record.fatoSocioeconomico.acessoSaneamentoPerc,
            likertEducacao=record.report.likertEducacao,
            likertSocioeconomico=record.report.likertSocioeconomico,
            recommendationSummary=recommendation_summary_by_key.get(
                (
                    f"{record.localidade.idLocalidade}:"
                    f"{record.fatoEducacao.idFatoEducacao}:"
                    f"{record.fatoSocioeconomico.idFatoSocioeconomico}"
                ),
                "Sem recomendacao calculada.",
            ),
        )
        for record in records
    ]
    return sorted(rows, key=lambda item: item.year, reverse=True)


def build_report_filter_options(items):
    records = [
        AnalysisRecord(
            report=item.report,
            localidade=item.report.localidade,
            fatoEducacao=item.report.fatoEducacao,
            fatoSocioeconomico=item.report.fatoSocioeconomico,
        )
        for item in items
    ]
    return build_filter_options(dedupe_analysis_records(records))
