from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_non_empty_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Este campo e obrigatorio.")
    return normalized


def _normalize_name_list(values: list[str], *, field_label: str) -> list[str]:
    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = value.strip()
        if not normalized:
            continue

        key = normalized.casefold()
        if key in seen:
            continue

        seen.add(key)
        normalized_values.append(normalized)

    if not normalized_values:
        raise ValueError(f"Informe ao menos um item em {field_label}.")

    return normalized_values


class PoliticaPublicaObjetivoEspecificoPayload(BaseModel):
    descricao: str

    @field_validator("descricao")
    @classmethod
    def validate_descricao(cls, value: str) -> str:
        return _normalize_non_empty_text(value)


class PoliticaPublicaBasePayload(BaseModel):
    titulo: str
    objetivo_geral: str
    objetivos_especificos: list[PoliticaPublicaObjetivoEspecificoPayload] = Field(default_factory=list)
    instituicoes_responsaveis: list[str] = Field(default_factory=list)
    beneficiarios: list[str] = Field(default_factory=list)
    id_dim_localidade: int | None = None
    indicador_chave: str | None = None
    id_relatorio: int | None = None

    @field_validator("titulo")
    @classmethod
    def validate_titulo(cls, value: str) -> str:
        return _normalize_non_empty_text(value)

    @field_validator("objetivo_geral")
    @classmethod
    def validate_objetivo_geral(cls, value: str) -> str:
        return _normalize_non_empty_text(value)

    @field_validator("indicador_chave")
    @classmethod
    def validate_indicador_chave(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @field_validator("instituicoes_responsaveis")
    @classmethod
    def validate_instituicoes(cls, values: list[str]) -> list[str]:
        return _normalize_name_list(values, field_label="instituicoes responsaveis")

    @field_validator("beneficiarios")
    @classmethod
    def validate_beneficiarios(cls, values: list[str]) -> list[str]:
        return _normalize_name_list(values, field_label="beneficiarios")

    @model_validator(mode="after")
    def validate_objetivos(self):
        total = len(self.objetivos_especificos)

        if total < 1:
            raise ValueError("Informe pelo menos um objetivo especifico.")

        if total > 3:
            raise ValueError("Informe no maximo tres objetivos especificos.")

        return self


class PoliticaPublicaCreatePayload(PoliticaPublicaBasePayload):
    pass


class PoliticaPublicaUpdatePayload(PoliticaPublicaBasePayload):
    pass


class PoliticaPublicaObjetivoEspecificoResponse(BaseModel):
    id: int
    ordem: int
    descricao: str


class PoliticaPublicaNamedRelationResponse(BaseModel):
    id: int
    nome: str


class PoliticaPublicaResumo(BaseModel):
    id: int
    titulo: str
    objetivo_geral: str
    indicador_chave: str | None = None
    id_dim_localidade: int | None = None
    id_relatorio: int | None = None
    data_criacao: datetime | None = None
    data_atualizacao: datetime | None = None
    instituicoes_responsaveis: list[PoliticaPublicaNamedRelationResponse]
    beneficiarios: list[PoliticaPublicaNamedRelationResponse]
    objetivos_especificos: list[PoliticaPublicaObjetivoEspecificoResponse]


class PoliticaPublicaDetalhe(PoliticaPublicaResumo):
    id_usuario_criador: int
    localidade_nome: str | None = None
    localidade_uf: str | None = None
    relatorio_resumo: str | None = None


class PoliticaPublicaListResponse(BaseModel):
    items: list[PoliticaPublicaResumo]


class PoliticaPublicaDeleteResponse(BaseModel):
    message: str


class PoliticaPublicaFormOptions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    localidades: list[dict[str, str | int | None]]
    indicadores_disponiveis: list[dict[str, str]]
    relatorios: list[dict[str, str | int | None]]
