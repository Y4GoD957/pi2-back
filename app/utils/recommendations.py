from app.schemas.educenso import AnalysisRecord, PublicPolicyRecommendation


def _build_recommendation(
    identifier: str,
    title: str,
    summary: str,
    rationale: str,
    emphasis: str,
) -> PublicPolicyRecommendation:
    return PublicPolicyRecommendation(
        id=identifier,
        title=title,
        summary=summary,
        rationale=rationale,
        emphasis=emphasis,
    )


def build_recommendations_from_records(
    records: list[AnalysisRecord],
) -> list[PublicPolicyRecommendation]:
    count = max(len(records), 1)
    average_enrollment = sum(item.fatoEducacao.taxaMatricula for item in records) / count
    average_attendance = sum(item.fatoEducacao.taxaFrequenciaEscolar for item in records) / count
    average_illiteracy = sum(item.fatoEducacao.taxaAnalfabetismo for item in records) / count
    average_income = sum((item.fatoSocioeconomico.rendaPerCapita or 0) for item in records) / count
    average_internet = sum((item.fatoSocioeconomico.acessoInternetPerc or 0) for item in records) / count
    average_sanitation = sum(
        (item.fatoSocioeconomico.acessoSaneamentoPerc or 0) for item in records
    ) / count

    recommendations: list[PublicPolicyRecommendation] = []
    if average_enrollment < 75 and average_income < 1200:
        recommendations.append(
            _build_recommendation(
                "inclusao-permanencia",
                "Incentivar inclusao e permanencia escolar",
                "Priorizar programas de busca ativa, apoio financeiro e acompanhamento da permanencia.",
                "O recorte filtrado combina baixa taxa de matricula com renda per capita reduzida.",
                "education",
            )
        )
    if average_illiteracy > 12 and average_internet < 60:
        recommendations.append(
            _build_recommendation(
                "alfabetizacao-inclusao-digital",
                "Ampliar alfabetizacao e inclusao digital",
                "Combinar reforco de alfabetizacao com acesso comunitario a conectividade e equipamentos.",
                "O conjunto analisado apresenta analfabetismo elevado e baixa conectividade.",
                "socioeconomic",
            )
        )
    if average_attendance < 80 and average_sanitation < 70:
        recommendations.append(
            _build_recommendation(
                "acao-intersetorial",
                "Promover acao intersetorial entre educacao e infraestrutura",
                "Integrar agenda escolar com saneamento, transporte e qualificacao dos equipamentos locais.",
                "A frequencia escolar esta pressionada por contexto de infraestrutura fragil.",
                "intersectoral",
            )
        )
    if not recommendations:
        recommendations.append(
            _build_recommendation(
                "monitoramento-continuo",
                "Manter monitoramento continuo dos indicadores",
                "O recorte nao aciona heuristicas criticas, mas ainda demanda acompanhamento sistematico.",
                "Os indicadores atuais nao apontam um gatilho prioritario unico.",
                "education",
            )
        )
    return recommendations


def build_recommendation_summary(record: AnalysisRecord) -> PublicPolicyRecommendation:
    return build_recommendations_from_records([record])[0]
