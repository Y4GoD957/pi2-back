from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urljoin

from httpx import AsyncClient, HTTPError, TimeoutException

from app.core.config import get_settings
from app.schemas.public_data import SourceMetadata
from app.services.public_data.exceptions import (
    PublicDataMalformedResponseError,
    PublicDataUnavailableError,
)


class SeedfClient:
    def __init__(self, client: AsyncClient | None = None) -> None:
        settings = get_settings()
        self.base_url = settings.seedf_base_url.rstrip("/")
        self.timeout = settings.public_data_timeout_seconds
        self._client = client

    async def fetch_package(self, dataset_slug: str) -> dict[str, Any]:
        try:
            payload = await self._get_json(
                "/api/3/action/package_show",
                params={"id": dataset_slug},
            )
            if not isinstance(payload, dict) or not payload.get("success") or not isinstance(payload.get("result"), dict):
                raise PublicDataMalformedResponseError("Resposta invalida ao consultar os metadados da SEEDF.")
            return payload["result"]
        except PublicDataUnavailableError:
            return await self._fetch_package_from_html(dataset_slug)

    async def fetch_resource_json(self, resource_url: str) -> Any:
        return await self._get_json_from_url(resource_url)

    async def fetch_resource_text(self, resource_url: str) -> str:
        return await self._get_text_from_url(resource_url)

    def build_source_metadata(
        self,
        *,
        package_data: dict[str, Any],
        resource: dict[str, Any] | None,
        endpoint: str,
        granularidade: str,
        confiabilidade: str = "alta",
        status_dado: str = "oficial",
    ) -> SourceMetadata:
        package_title = self._coalesce(package_data, "title", "name") or "SEEDF Dados Abertos"
        resource_name = self._coalesce(resource or {}, "name")
        resource_format = self._coalesce(resource or {}, "format")
        url = self._coalesce(resource or {}, "url") or endpoint
        return SourceMetadata(
            nome="SEEDF Dados Abertos",
            endpoint=endpoint,
            url=url,
            parametros={"dataset": str(package_data.get("name") or "")},
            obtido_em=datetime.now(timezone.utc),
            confiabilidade=confiabilidade,  # type: ignore[arg-type]
            granularidade=granularidade,
            formato=resource_format,
            status_dado=status_dado,  # type: ignore[arg-type]
            dataset=package_title,
            recurso=resource_name,
            ultima_atualizacao=self._parse_datetime(
                self._coalesce(resource or {}, "last_modified", "created")
                or self._coalesce(package_data, "metadata_modified", "metadata_created")
            ),
        )

    def pick_resource(
        self,
        package_data: dict[str, Any],
        *,
        format_name: str | None = None,
        contains: str | None = None,
        year: int | None = None,
    ) -> dict[str, Any] | None:
        resources = package_data.get("resources")
        if not isinstance(resources, list):
            return None

        selected: dict[str, Any] | None = None
        normalized_contains = self._normalize_text(contains) if contains else None
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            resource_format = str(resource.get("format") or "").lower()
            resource_name = str(resource.get("name") or "")
            if format_name and resource_format != format_name.lower():
                continue
            if normalized_contains and not self._resource_matches(resource_name, normalized_contains):
                continue
            if year and str(year) not in resource_name:
                continue
            selected = resource
        return selected

    async def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        client = self._client or AsyncClient(base_url=self.base_url, timeout=self.timeout, follow_redirects=True)
        should_close = self._client is None
        try:
            response = await client.get(path, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()
        except TimeoutException as exc:
            raise PublicDataUnavailableError("Tempo esgotado ao consultar a SEEDF.") from exc
        except HTTPError as exc:
            raise PublicDataUnavailableError("Nao foi possivel consultar a SEEDF.") from exc
        finally:
            if should_close:
                await client.aclose()

    async def _get_json_from_url(self, resource_url: str) -> Any:
        client = self._client or AsyncClient(timeout=self.timeout, follow_redirects=True)
        should_close = self._client is None
        try:
            response = await client.get(resource_url, headers={"Accept": "application/json, application/geo+json"})
            response.raise_for_status()
            return response.json()
        except TimeoutException as exc:
            raise PublicDataUnavailableError("Tempo esgotado ao baixar um recurso da SEEDF.") from exc
        except HTTPError as exc:
            raise PublicDataUnavailableError("Nao foi possivel baixar um recurso da SEEDF.") from exc
        finally:
            if should_close:
                await client.aclose()

    async def _get_text_from_url(self, resource_url: str) -> str:
        client = self._client or AsyncClient(timeout=self.timeout, follow_redirects=True)
        should_close = self._client is None
        try:
            response = await client.get(resource_url, headers={"Accept": "text/csv, text/plain, application/octet-stream"})
            response.raise_for_status()
            return response.text
        except TimeoutException as exc:
            raise PublicDataUnavailableError("Tempo esgotado ao baixar um arquivo textual da SEEDF.") from exc
        except HTTPError as exc:
            raise PublicDataUnavailableError("Nao foi possivel baixar um arquivo textual da SEEDF.") from exc
        finally:
            if should_close:
                await client.aclose()

    async def _fetch_package_from_html(self, dataset_slug: str) -> dict[str, Any]:
        html = await self._get_text_from_url(f"{self.base_url}/dataset/{dataset_slug}")
        resource_matches = re.findall(
            r"/dataset/[^\"']+/resource/[^\"']+/download/[^\"']+",
            html,
            flags=re.IGNORECASE,
        )
        if not resource_matches:
            raise PublicDataMalformedResponseError("Pagina da SEEDF sem recursos publicos identificaveis.")

        resources: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for relative_url in resource_matches:
            full_url = urljoin(f"{self.base_url}/", relative_url.lstrip("/"))
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            filename = full_url.rsplit("/", 1)[-1]
            extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            resources.append(
                {
                    "name": filename,
                    "format": extension,
                    "url": full_url,
                }
            )

        return {
            "name": dataset_slug,
            "title": dataset_slug.replace("-", " ").replace("_", " ").title(),
            "resources": resources,
        }

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _coalesce(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _resource_matches(self, resource_name: str, normalized_contains: str) -> bool:
        normalized_resource_name = self._normalize_text(resource_name)
        if normalized_contains in normalized_resource_name:
            return True
        contains_tokens = normalized_contains.split()
        return bool(contains_tokens) and all(token in normalized_resource_name for token in contains_tokens)

    def _normalize_text(self, value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
