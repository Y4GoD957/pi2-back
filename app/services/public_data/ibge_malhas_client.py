from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from httpx import AsyncClient, HTTPError, TimeoutException

from app.core.config import get_settings
from app.services.public_data.exceptions import (
    PublicDataMalformedResponseError,
    PublicDataUnavailableError,
)

_geojson_cache: dict[str, Any] | None = None

DF_IBGE_CODE = "53"


class IbgeMalhasClient:
    def __init__(self, client: AsyncClient | None = None) -> None:
        settings = get_settings()
        self.base_url = settings.ibge_malhas_base_url.rstrip("/")
        self.timeout = settings.public_data_timeout_seconds
        self._client = client

    async def fetch_df_boundary(self) -> dict[str, Any]:
        global _geojson_cache
        if _geojson_cache is not None:
            return _geojson_cache
        result = await self._fetch_and_normalize()
        _geojson_cache = result
        return result

    async def _fetch_and_normalize(self) -> dict[str, Any]:
        path = f"/{DF_IBGE_CODE}"
        params = {"resolucao": "5", "formato": "application/vnd.geo+json"}
        client = self._client or AsyncClient(base_url=self.base_url, timeout=self.timeout)
        should_close = self._client is None
        try:
            response = await client.get(path, params=params)
            response.raise_for_status()
            data: Any = response.json()
        except TimeoutException as exc:
            raise PublicDataUnavailableError("Tempo esgotado ao consultar a API de malhas do IBGE.") from exc
        except HTTPError as exc:
            raise PublicDataUnavailableError("Nao foi possivel consultar a API de malhas do IBGE.") from exc
        finally:
            if should_close:
                await client.aclose()

        return self._normalize(data)

    def _normalize(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            raise PublicDataMalformedResponseError("GeoJSON invalido recebido da API de malhas do IBGE.")

        features: list[dict[str, Any]] = data.get("features") or []
        normalized: list[dict[str, Any]] = []
        for i, feature in enumerate(features):
            if not isinstance(feature, dict):
                continue
            props: dict[str, Any] = feature.get("properties") or {}
            normalized.append(
                {
                    "type": "Feature",
                    "properties": {
                        **props,
                        "id": "df" if len(features) == 1 else f"df_{i}",
                        "name": "Distrito Federal",
                        "uf": "DF",
                        "ibge_code": DF_IBGE_CODE,
                        "obtido_em": datetime.now(timezone.utc).isoformat(),
                    },
                    "geometry": feature.get("geometry"),
                }
            )

        return {
            "type": "FeatureCollection",
            "features": normalized,
            "meta": {
                "source": "IBGE Malhas v2",
                "url": f"{self.base_url}/{DF_IBGE_CODE}",
                "granularidade": "uf",
                "aviso": (
                    "GeoJSON oficial no nivel de UF. "
                    "Regioes Administrativas do DF nao estao disponiveis como poligonos oficiais nesta integracao."
                ),
            },
        }
