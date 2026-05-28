from __future__ import annotations

import csv
import io
import math
import re
import unicodedata
from typing import Any

from app.schemas.public_data import (
    CorrelationContext,
    IndicatorInterpretation,
    IndicatorHistoricalPoint,
    RecommendationHint,
    SeverityLevel,
    TrendInterpretation,
)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_from_thresholds(value: float | None, thresholds: tuple[float, float], higher_is_better: bool) -> float | None:
    if value is None:
        return None

    lower, upper = thresholds
    if upper <= lower:
        return None

    normalized = (value - lower) / (upper - lower)
    normalized = clamp01(normalized)
    return normalized if higher_is_better else clamp01(1 - normalized)


def severity_from_score(score: float | None) -> SeverityLevel:
    if score is None:
        return "indefinido"
    if score >= 0.75:
        return "baixo"
    if score >= 0.5:
        return "moderado"
    if score >= 0.25:
        return "alto"
    return "critico"


def build_trend(points: list[IndicatorHistoricalPoint], higher_is_better: bool) -> TrendInterpretation:
    valid_points = [point for point in points if point.valor is not None]
    if len(valid_points) < 2:
        return TrendInterpretation(
            direcao="insuficiente",
            descricao="Nao ha serie historica suficiente para interpretar tendencia.",
        )

    previous = valid_points[-2].valor
    current = valid_points[-1].valor
    if previous is None or current is None:
        return TrendInterpretation(
            direcao="insuficiente",
            descricao="Nao ha serie historica suficiente para interpretar tendencia.",
        )

    delta = current - previous
    percent = (delta / previous * 100) if previous not in (0, None) else None
    if abs(delta) < 0.01:
        return TrendInterpretation(
            direcao="estavel",
            descricao="O indicador permaneceu estavel no recorte historico disponivel.",
            variacao_absoluta=round(delta, 4),
            variacao_percentual=round(percent, 2) if percent is not None else None,
        )

    improved = delta > 0 if higher_is_better else delta < 0
    return TrendInterpretation(
        direcao="melhora" if improved else "piora",
        descricao=(
            "O indicador apresentou melhora no periodo mais recente."
            if improved
            else "O indicador apresentou piora no periodo mais recente."
        ),
        variacao_absoluta=round(delta, 4),
        variacao_percentual=round(percent, 2) if percent is not None else None,
    )


def build_recommendation_hints(indicator_key: str, severity: SeverityLevel) -> list[RecommendationHint]:
    hint_map = {
        "internet_access_pct": RecommendationHint(
            titulo="Ampliar conectividade educacional",
            descricao="Priorizar infraestrutura de internet e acesso digital nas areas mais vulneraveis.",
            prioridade=severity,
            relacionado_a=["conectividade", "infraestrutura", "educacao"],
        ),
        "school_attendance_rate": RecommendationHint(
            titulo="Reforcar permanencia escolar",
            descricao="Investigar evasao, frequencia e barreiras de acesso para manter estudantes na escola.",
            prioridade=severity,
            relacionado_a=["frequencia", "evasao", "apoio escolar"],
        ),
        "illiteracy_rate_15_plus": RecommendationHint(
            titulo="Focar alfabetizacao de jovens e adultos",
            descricao="Planejar acoes territoriais para reduzir analfabetismo e ampliar oportunidades educacionais.",
            prioridade=severity,
            relacionado_a=["alfabetizacao", "eja", "inclusao"],
        ),
        "adequate_housing_pct": RecommendationHint(
            titulo="Integrar politicas urbanas e educacionais",
            descricao="Cruzar carencias habitacionais com risco educacional para orientar politicas intersetoriais.",
            prioridade=severity,
            relacionado_a=["habitacao", "saneamento", "territorio"],
        ),
    }
    hint = hint_map.get(indicator_key)
    return [hint] if hint else []


def build_interpretation(
    *,
    indicator_key: str,
    indicator_label: str,
    value: float | None,
    score: float | None,
    higher_is_better: bool,
    points: list[IndicatorHistoricalPoint],
) -> IndicatorInterpretation:
    severity = severity_from_score(score)
    trend = build_trend(points, higher_is_better)

    if value is None:
        return IndicatorInterpretation(
            resumo=f"O indicador {indicator_label} nao possui valor oficial disponivel para o recorte solicitado.",
            nivel_severidade="indefinido",
            score_normalizado=None,
            leitura="Sem leitura conclusiva.",
            tendencia=trend,
            dicas_recomendacao=[],
            explicacao="A resposta manteve o contrato analitico, mas o valor oficial nao foi encontrado.",
        )

    readings = {
        "baixo": "Situacao relativamente favoravel no recorte analisado.",
        "moderado": "Situacao intermediaria, com atencao recomendada.",
        "alto": "Situacao sensivel, recomendando monitoramento proximo.",
        "critico": "Situacao critica, com prioridade para intervencao.",
        "indefinido": "Sem leitura conclusiva.",
    }
    return IndicatorInterpretation(
        resumo=f"{indicator_label}: valor observado de {value:.2f}.",
        nivel_severidade=severity,
        score_normalizado=round(score, 4) if score is not None else None,
        leitura=readings[severity],
        tendencia=trend,
        dicas_recomendacao=build_recommendation_hints(indicator_key, severity),
        explicacao="Interpretacao calculada no backend para apoiar leitura analitica, heatmap e futuras recomendacoes.",
    )


def build_correlation_context(indicator_key: str, theme: str) -> CorrelationContext:
    dimensions = ["localidade"]
    if theme == "educacao":
        dimensions.extend(["educacao", "socioeconomico"])
    elif theme == "socioeconomico":
        dimensions.extend(["socioeconomico", "educacao"])
    else:
        dimensions.append("socioeconomico")

    return CorrelationContext(
        dimensoes=dimensions,
        chaves_correlacao=[indicator_key, theme, "df", "serie_historica"],
        pronto_para_ia=True,
    )


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def coalesce_field(payload: dict[str, Any], candidates: list[str]) -> Any:
    lowered = {normalize_text(key): key for key in payload.keys()}
    for candidate in candidates:
        direct = payload.get(candidate)
        if direct not in (None, ""):
            return direct
        mapped_key = lowered.get(normalize_text(candidate))
        if mapped_key is not None:
            value = payload.get(mapped_key)
            if value not in (None, ""):
                return value
    return None


def parse_csv_records(content: str) -> list[dict[str, str]]:
    if not content.strip():
        return []
    sample = content[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    return [{str(key): value for key, value in row.items() if key is not None} for row in reader]


def parse_float(value: Any) -> float | None:
    if value in (None, "", "-", "..."):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    numeric = parse_float(value)
    return int(round(numeric)) if numeric is not None else None


def build_join_key(*values: Any) -> str:
    return "|".join(part for part in (normalize_text(value) for value in values) if part)


def approximate_circle_geojson(latitude: float, longitude: float, radius_meters: int, *, steps: int = 32) -> dict[str, Any]:
    points: list[list[float]] = []
    earth_radius = 6378137.0
    lat_rad = math.radians(latitude)
    for step in range(steps):
        bearing = 2 * math.pi * step / steps
        delta_lat = (radius_meters / earth_radius) * math.cos(bearing)
        delta_lng = (radius_meters / (earth_radius * max(math.cos(lat_rad), 1e-9))) * math.sin(bearing)
        points.append(
            [
                longitude + math.degrees(delta_lng),
                latitude + math.degrees(delta_lat),
            ]
        )
    if points:
        points.append(points[0])
    return {
        "type": "Feature",
        "properties": {
            "radius_meters": radius_meters,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [points],
        },
    }


def point_in_feature(latitude: float, longitude: float, feature: dict[str, Any]) -> bool:
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        return False
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        return _point_in_polygon(longitude, latitude, coordinates)
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return any(_point_in_polygon(longitude, latitude, polygon) for polygon in coordinates if isinstance(polygon, list))
    return False


def _point_in_polygon(longitude: float, latitude: float, polygon: list[Any]) -> bool:
    if not polygon:
        return False
    ring = polygon[0]
    if not isinstance(ring, list) or len(ring) < 3:
        return False
    inside = False
    j = len(ring) - 1
    for i, current in enumerate(ring):
        previous = ring[j]
        if not (
            isinstance(current, list)
            and len(current) >= 2
            and isinstance(previous, list)
            and len(previous) >= 2
        ):
            j = i
            continue
        xi, yi = float(current[0]), float(current[1])
        xj, yj = float(previous[0]), float(previous[1])
        intersects = ((yi > latitude) != (yj > latitude)) and (
            longitude < (xj - xi) * (latitude - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside
