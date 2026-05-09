from datetime import datetime, timezone
from typing import Any

from httpx import AsyncClient, HTTPError, TimeoutException

from app.core.config import get_settings
from app.services.public_data.exceptions import (
    PublicDataMalformedResponseError,
    PublicDataUnavailableError,
)


class IbgeLocalitiesClient:
    def __init__(self, client: AsyncClient | None = None) -> None:
        settings = get_settings()
        self.base_url = settings.ibge_localidades_base_url.rstrip("/")
        self.timeout = settings.public_data_timeout_seconds
        self._client = client

    async def fetch_ufs(self) -> list[dict[str, Any]]:
        data = await self._get_json("/estados?orderBy=nome")
        if not isinstance(data, list):
            raise PublicDataMalformedResponseError("Resposta invalida ao consultar UFs do IBGE.")

        return [
            {
                "id": str(item["id"]),
                "sigla": item["sigla"],
                "nome": item["nome"],
            }
            for item in data
            if isinstance(item, dict) and item.get("id") and item.get("sigla") and item.get("nome")
        ]

    async def fetch_municipalities_by_uf(self, uf: str) -> list[dict[str, Any]]:
        data = await self._get_json(f"/estados/{uf}/municipios?orderBy=nome")
        if not isinstance(data, list):
            raise PublicDataMalformedResponseError("Resposta invalida ao consultar municipios do IBGE.")

        return [
            {
                "id": str(item["id"]),
                "nome": item["nome"],
                "uf": uf,
            }
            for item in data
            if isinstance(item, dict) and item.get("id") and item.get("nome")
        ]

    async def fetch_df_metadata(self) -> dict[str, Any]:
        ufs = await self.fetch_ufs()
        df = next((item for item in ufs if item["sigla"] == "DF"), None)
        if df is None:
            raise PublicDataUnavailableError("Distrito Federal nao encontrado na API de localidades do IBGE.")

        municipalities = await self.fetch_municipalities_by_uf("DF")
        return {
            "uf": df,
            "municipios": municipalities,
            "granularidade_oficial": "uf/municipio",
            "aviso_granularidade": (
                "As Regioes Administrativas do DF nao sao expostas como municipios oficiais do IBGE. "
                "Nesta versao, os dados oficiais ficam limitados a UF e, quando aplicavel, ao municipio Brasilia."
            ),
            "obtido_em": datetime.now(timezone.utc),
        }

    async def fetch_df_districts(self) -> list[dict[str, Any]]:
        data = await self._get_json("/estados/DF/distritos?orderBy=nome")
        if not isinstance(data, list):
            raise PublicDataMalformedResponseError("Resposta invalida ao consultar distritos do DF no IBGE.")

        return [
            {"id": str(item["id"]), "nome": item["nome"]}
            for item in data
            if isinstance(item, dict) and item.get("id") and item.get("nome")
        ]

    async def _get_json(self, path: str) -> Any:
        client = self._client or AsyncClient(base_url=self.base_url, timeout=self.timeout)
        should_close = self._client is None
        try:
            response = await client.get(path, headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()
        except TimeoutException as exc:
            raise PublicDataUnavailableError("Tempo esgotado ao consultar a API de localidades do IBGE.") from exc
        except HTTPError as exc:
            raise PublicDataUnavailableError("Nao foi possivel consultar a API de localidades do IBGE.") from exc
        finally:
            if should_close:
                await client.aclose()
