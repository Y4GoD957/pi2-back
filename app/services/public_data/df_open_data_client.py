from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DfOpenDataCandidate:
    nome: str
    url: str
    status: str
    motivo: str


class DfOpenDataClient:
    """
    Registro simples de fontes públicas oficiais do DF avaliadas para futuras expansões.
    Nesta fase, a integração operacional principal usa SEEDF e Geoportal/ArcGIS.
    """

    def list_candidates(self) -> list[DfOpenDataCandidate]:
        return [
            DfOpenDataCandidate(
                nome="IPEDF / Catalogo DF - Escolas Publicas e Particulares do Distrito Federal",
                url="https://catalogo.ipe.df.gov.br/",
                status="avaliado",
                motivo=(
                    "Fonte promissora para futuras expansoes, mas nesta entrega nao foi confirmado "
                    "um endpoint estavel e publico com GeoJSON/WFS equivalente ao usado no backend."
                ),
            )
        ]
