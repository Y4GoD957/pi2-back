from datetime import datetime

from pydantic import BaseModel


class AdministrativeRegion(BaseModel):
    id: str
    nome: str


class UfMetadata(BaseModel):
    id: str
    sigla: str
    nome: str


class MunicipalityMetadata(BaseModel):
    id: str
    nome: str
    uf: str


class DfMetadataResponse(BaseModel):
    uf: UfMetadata | dict[str, str]
    municipios: list[MunicipalityMetadata | dict[str, str]]
    granularidadeOficial: str
    avisoGranularidade: str
    obtidoEm: datetime
