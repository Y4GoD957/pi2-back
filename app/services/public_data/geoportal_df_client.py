from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from httpx import AsyncClient, HTTPError, TimeoutException

from app.core.config import get_settings
from app.schemas.public_data import SourceMetadata
from app.services.public_data.exceptions import (
    PublicDataMalformedResponseError,
    PublicDataUnavailableError,
)


class GeoportalDfClient:
    def __init__(self, client: AsyncClient | None = None) -> None:
        settings = get_settings()
        self.base_url = settings.geoportal_df_arcgis_base_url.rstrip("/")
        self.timeout = settings.public_data_timeout_seconds
        self._client = client

    async def fetch_administrative_regions_geojson(self) -> dict[str, Any]:
        layer_url = f"{self.base_url}/Territorio/Regioes_Administrativas_DF_2025/FeatureServer/0/query"
        params = {
            "where": "1=1",
            "outFields": "ra_nome,ra_codigo,ra_cira",
            "returnGeometry": "true",
            "f": "geojson",
            "outSR": "4326",
        }
        payload = await self._get_json_from_url(layer_url, params=params)
        if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
            raise PublicDataMalformedResponseError("Resposta invalida ao consultar as Regioes Administrativas do DF.")

        features = payload.get("features")
        if not isinstance(features, list):
            raise PublicDataMalformedResponseError("GeoJSON de Regioes Administrativas sem lista de features.")

        normalized_features: list[dict[str, Any]] = []
        for index, feature in enumerate(features):
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties") or {}
            if not isinstance(properties, dict):
                properties = {}
            region_name = str(properties.get("ra_nome") or f"Regiao {index + 1}")
            region_code = str(properties.get("ra_codigo") or properties.get("ra_cira") or index + 1)
            normalized_features.append(
                {
                    "type": "Feature",
                    "properties": {
                        **properties,
                        "id": region_code,
                        "name": region_name,
                        "region_code": region_code,
                        "source": "Geoportal DF / ArcGIS",
                        "obtido_em": datetime.now(timezone.utc).isoformat(),
                    },
                    "geometry": feature.get("geometry"),
                }
            )

        return {
            "type": "FeatureCollection",
            "features": normalized_features,
        }

    def build_source_metadata(self) -> SourceMetadata:
        endpoint = f"{self.base_url}/Territorio/Regioes_Administrativas_DF_2025/FeatureServer/0/query"
        return SourceMetadata(
            nome="Geoportal DF / ArcGIS",
            endpoint=endpoint,
            url="https://onda.ibram.df.gov.br/server/rest/services/Territorio/Regioes_Administrativas_DF_2025/FeatureServer/0",
            parametros={
                "where": "1=1",
                "outFields": "ra_nome,ra_codigo,ra_cira",
                "returnGeometry": "true",
                "f": "geojson",
                "outSR": "4326",
            },
            obtido_em=datetime.now(timezone.utc),
            confiabilidade="alta",
            granularidade="regiao_administrativa",
            formato="geojson",
            status_dado="oficial",
            dataset="Regioes Administrativas DF 2025",
            recurso="Regioes Administrativas DF",
        )

    async def _get_json_from_url(self, url: str, params: dict[str, str]) -> Any:
        client = self._client or AsyncClient(timeout=self.timeout, follow_redirects=True)
        should_close = self._client is None
        try:
            response = await client.get(url, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()
        except TimeoutException as exc:
            raise PublicDataUnavailableError("Tempo esgotado ao consultar o Geoportal DF.") from exc
        except HTTPError as exc:
            raise PublicDataUnavailableError("Nao foi possivel consultar o Geoportal DF.") from exc
        finally:
            if should_close:
                await client.aclose()
