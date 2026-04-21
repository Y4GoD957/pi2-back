from collections import defaultdict

from app.schemas.educenso import AnalysisRecord, DfHeatMapArea, DfHeatMapData


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _normalize_percent(value: float | None) -> float:
    if value is None:
        return 0.0
    return _clamp01(value / 100.0)


def _normalize_income(value: float | None) -> float:
    if value is None or value <= 0:
        return 0.0
    return _clamp01(value / 3000.0)


def _build_area_label(record: AnalysisRecord) -> str:
    sector = (record.localidade.setorCensitario or "").strip()
    return sector or record.localidade.municipio


def _compute_vulnerability_score(record: AnalysisRecord) -> float:
    positive_score = (
        _normalize_percent(record.fatoEducacao.taxaMatricula) * 0.22
        + _normalize_percent(record.fatoEducacao.taxaFrequenciaEscolar) * 0.2
        + (1 - _normalize_percent(record.fatoEducacao.taxaAnalfabetismo)) * 0.18
        + _normalize_percent(record.fatoSocioeconomico.acessoInternetPerc) * 0.14
        + _normalize_percent(record.fatoSocioeconomico.acessoSaneamentoPerc) * 0.14
        + _normalize_income(record.fatoSocioeconomico.rendaPerCapita) * 0.12
    )
    return round((1 - positive_score) * 100, 1)


def build_df_heatmap_fallback(records: list[AnalysisRecord]) -> DfHeatMapData:
    grouped: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"score_total": 0.0, "report_count": 0, "latest_year": 0}
    )

    for record in records:
        if record.localidade.uf != "DF":
            continue
        label = _build_area_label(record)
        grouped[label]["score_total"] += _compute_vulnerability_score(record)
        grouped[label]["report_count"] += 1
        grouped[label]["latest_year"] = max(grouped[label]["latest_year"], record.fatoEducacao.ano)

    areas = [
        DfHeatMapArea(
            id=label,
            label=label,
            metricLabel="Indice de vulnerabilidade composta",
            metricValue=round(data["score_total"] / data["report_count"], 1),
            normalizedValue=_clamp01((data["score_total"] / data["report_count"]) / 100.0),
            reportCount=int(data["report_count"]),
            year=int(data["latest_year"]) or None,
            source="supabase",
        )
        for label, data in grouped.items()
        if data["report_count"]
    ]
    areas.sort(key=lambda item: item.metricValue, reverse=True)

    return DfHeatMapData(
        title="Heat map do DF",
        subtitle=(
            "Blocos setoriais do Distrito Federal com intensidade derivada "
            "dos indicadores reais disponiveis no recorte atual."
        ),
        areas=areas,
        sourceLabel="Supabase atual do projeto",
        geometryStatus="fallback",
        notes=[
            "Sem geometria intramunicipal consolidada no backend, o mapa usa um bloco tematico por setor/localidade do DF.",
            "Quando a API FastAPI com GeoPandas estiver disponivel, esta mesma area pode receber poligonos reais do DF.",
        ],
    )
