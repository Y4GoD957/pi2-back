from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InepIntegrationStatus:
    nome: str
    url: str
    status: str
    motivo: str


class InepClient:
    """
    Adaptador leve para registrar o estado atual da integracao do INEP.
    A fonte segue relevante para catalogo e atributos educacionais, mas sem API limpa confirmada
    nesta entrega o backend preserva o contrato sem inventar dados.
    """

    def describe(self) -> InepIntegrationStatus:
        return InepIntegrationStatus(
            nome="INEP / Censo Escolar",
            url="https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos",
            status="parcial",
            motivo=(
                "Mantido como fonte oficial complementar para futuras importacoes/adapters; "
                "nesta fase os dados expostos usam integracoes online mais estaveis da SEEDF e do Geoportal DF."
            ),
        )
