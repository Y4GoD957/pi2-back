from app.schemas.educenso import FatoEducacao, FatoSocioeconomico, LikertInterpretation

LIKERT_MIN = 1.0
LIKERT_MAX = 5.0


def _clamp_likert(value: float) -> float:
    return min(LIKERT_MAX, max(LIKERT_MIN, value))


def _normalize_percent(value: float | None) -> float:
    if value is None:
        return 0.0
    return min(100.0, max(0.0, value)) / 100.0


def _normalize_income(value: float | None) -> float:
    if value is None or value <= 0:
        return 0.0
    return min(value / 3000.0, 1.0)


def _score_to_likert(score: float) -> float:
    return _clamp_likert(round(1 + score * 4, 2))


def interpret_likert(value: float) -> LikertInterpretation:
    normalized = _clamp_likert(round(value, 2))
    if normalized < 2.5:
        return LikertInterpretation(
            numericValue=normalized,
            label="Nivel baixo",
            level="baixo",
            description="Leitura de maior vulnerabilidade no recorte analisado.",
            colorClassName="bg-rose-500",
        )
    if normalized < 3.75:
        return LikertInterpretation(
            numericValue=normalized,
            label="Nivel moderado",
            level="moderado",
            description="Situacao intermediaria, com pontos relevantes de atencao.",
            colorClassName="bg-amber-500",
        )
    return LikertInterpretation(
        numericValue=normalized,
        label="Nivel alto",
        level="alto",
        description="Leitura mais favoravel dentro do conjunto filtrado.",
        colorClassName="bg-emerald-500",
    )


def compute_education_likert(fato_educacao: FatoEducacao) -> float:
    score = (
        _normalize_percent(fato_educacao.taxaMatricula) * 0.4
        + _normalize_percent(fato_educacao.taxaFrequenciaEscolar) * 0.35
        + _normalize_percent(100 - fato_educacao.taxaAnalfabetismo) * 0.25
    )
    return _score_to_likert(score)


def compute_socioeconomic_likert(fato_socioeconomico: FatoSocioeconomico) -> float:
    score = (
        _normalize_income(fato_socioeconomico.rendaPerCapita) * 0.4
        + _normalize_percent(fato_socioeconomico.acessoInternetPerc) * 0.3
        + _normalize_percent(fato_socioeconomico.acessoSaneamentoPerc) * 0.3
    )
    return _score_to_likert(score)
