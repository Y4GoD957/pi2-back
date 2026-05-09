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


class SidraClient:
    def __init__(self, client: AsyncClient | None = None) -> None:
        settings = get_settings()
        self.base_url = settings.sidra_base_url.rstrip("/")
        self.timeout = settings.public_data_timeout_seconds
        self._client = client

    async def fetch_table(
        self,
        *,
        table_code: str,
        periods: str,
        localities: str,
        variable: str | None = None,
        classifications: dict[str, str] | None = None,
        view: str = "flat",
    ) -> dict[str, Any]:
        metadata = await self._fetch_metadata(table_code)
        if not variable:
            raise PublicDataMalformedResponseError(
                "A consulta SIDRA exige variavel explicita para evitar mapeamentos ambiguos."
            )
        resolved_variable = variable

        classification_query = ""
        if classifications:
            classification_query = "|".join(f"{key}[{value}]" for key, value in classifications.items())

        params = {
            "localidades": localities,
            "view": view,
        }
        if classification_query:
            params["classificacao"] = classification_query

        path = f"/agregados/{table_code}/periodos/{periods}/variaveis/{resolved_variable}"
        data = await self._get_json(path, params=params)
        if not isinstance(data, list):
            raise PublicDataMalformedResponseError("Resposta invalida ao consultar tabela SIDRA/IBGE.")

        rows = self._normalize_variable_response(data, view=view)
        return {
            "table_code": table_code,
            "variable": resolved_variable,
            "metadata": metadata,
            "rows": rows,
            "source_metadata": SourceMetadata(
                nome="SIDRA/IBGE",
                endpoint=f"{self.base_url}{path}",
                url="https://servicodados.ibge.gov.br/api/docs/agregados?versao=3",
                codigo_tabela=table_code,
                parametros={key: str(value) for key, value in params.items()},
                obtido_em=datetime.now(timezone.utc),
                confiabilidade="alta",
                granularidade="uf",
            ),
        }

    async def fetch_df_indicators(
        self,
        *,
        table_code: str,
        variable: str,
        periods: str = "-6",
        classifications: dict[str, str] | None = None,
        territorial_level: str = "N3[53]",
    ) -> dict[str, Any]:
        return await self.fetch_table(
            table_code=table_code,
            periods=periods,
            localities=territorial_level,
            variable=variable,
            classifications=classifications,
        )

    async def fetch_socioeconomic_indicators_for_df(
        self,
        *,
        table_code: str,
        variable: str,
        periods: str = "-6",
        classifications: dict[str, str] | None = None,
        territorial_level: str = "N3[53]",
    ) -> dict[str, Any]:
        return await self.fetch_df_indicators(
            table_code=table_code,
            variable=variable,
            periods=periods,
            classifications=classifications,
            territorial_level=territorial_level,
        )

    async def fetch_historical_series_for_df(
        self,
        *,
        table_code: str,
        variable: str,
        periods: str = "-6",
        classifications: dict[str, str] | None = None,
        territorial_level: str = "N3[53]",
    ) -> dict[str, Any]:
        return await self.fetch_table(
            table_code=table_code,
            periods=periods,
            localities=territorial_level,
            variable=variable,
            classifications=classifications,
        )

    async def _fetch_metadata(self, table_code: str) -> dict[str, Any]:
        data = await self._get_json(f"/agregados/{table_code}/metadados")
        if not isinstance(data, dict):
            raise PublicDataMalformedResponseError("Metadados invalidos ao consultar o SIDRA/IBGE.")
        return data

    def _normalize_variable_response(self, payload: list[dict[str, Any]], *, view: str) -> list[dict[str, Any]]:
        if view == "flat":
            return self._normalize_flat_response(payload)

        rows: list[dict[str, Any]] = []
        for variable_item in payload:
            results = variable_item.get("resultados")
            if not isinstance(results, list):
                continue
            for result in results:
                classifications = result.get("classificacoes", [])
                normalized_classifications = []
                if isinstance(classifications, list):
                    for classification in classifications:
                        if not isinstance(classification, dict):
                            continue
                        categoria = classification.get("categoria")
                        normalized_classifications.append(
                            {
                                "id": str(classification.get("id")) if classification.get("id") is not None else None,
                                "nome": classification.get("nome"),
                                "categoria": categoria,
                            }
                        )

                series = result.get("series")
                if not isinstance(series, list):
                    continue

                for serie in series:
                    if not isinstance(serie, dict):
                        continue
                    localidade = serie.get("localidade", {})
                    serie_valores = serie.get("serie", {})
                    if not isinstance(localidade, dict) or not isinstance(serie_valores, dict):
                        continue

                    for period, raw_value in serie_valores.items():
                        rows.append(
                            {
                                "localidade_id": str(localidade.get("id")) if localidade.get("id") is not None else None,
                                "localidade_nome": localidade.get("nome"),
                                "periodo": str(period),
                                "valor": self._parse_numeric_value(raw_value),
                                "classificacoes": normalized_classifications,
                            }
                        )

        return rows

    def _normalize_flat_response(self, payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in payload[1:]:
            if not isinstance(item, dict):
                continue

            normalized_classifications = []
            for key, value in item.items():
                if not key.endswith("N") or not key.startswith("D"):
                    continue
                code_key = f"{key[:-1]}C"
                if code_key not in item:
                    continue
                if key in {"D1N", "D2N", "D3N"}:
                    continue

                normalized_classifications.append(
                    {
                        "id": str(item.get(code_key)) if item.get(code_key) is not None else None,
                        "nome": str(value) if value is not None else None,
                        "categoria": str(value) if value is not None else None,
                    }
                )

            rows.append(
                {
                    "localidade_id": str(item.get("D1C")) if item.get("D1C") is not None else None,
                    "localidade_nome": item.get("D1N"),
                    "periodo": str(item.get("D2C")) if item.get("D2C") is not None else None,
                    "periodo_label": item.get("D2N"),
                    "valor": self._parse_numeric_value(item.get("V")),
                    "unidade": item.get("MN"),
                    "variavel_id": str(item.get("D3C")) if item.get("D3C") is not None else None,
                    "variavel_nome": item.get("D3N"),
                    "classificacoes": normalized_classifications,
                }
            )

        return rows

    def _parse_numeric_value(self, value: Any) -> float | None:
        if value in (None, "...", "-", "X"):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = value.strip()
            if "," in normalized and "." in normalized:
                normalized = normalized.replace(".", "").replace(",", ".")
            elif "," in normalized:
                normalized = normalized.replace(",", ".")
            try:
                return float(normalized)
            except ValueError:
                return None
        return None

    async def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        client = self._client or AsyncClient(base_url=self.base_url, timeout=self.timeout)
        should_close = self._client is None
        try:
            response = await client.get(path, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()
        except TimeoutException as exc:
            raise PublicDataUnavailableError("Tempo esgotado ao consultar o SIDRA/IBGE.") from exc
        except HTTPError as exc:
            raise PublicDataUnavailableError("Nao foi possivel consultar o SIDRA/IBGE.") from exc
        finally:
            if should_close:
                await client.aclose()
