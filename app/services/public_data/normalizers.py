from __future__ import annotations

from app.schemas.public_data import (
    CorrelationContext,
    IndicatorInterpretation,
    RecommendationHint,
    SeverityLevel,
    TrendInterpretation,
    IndicatorHistoricalPoint,
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
