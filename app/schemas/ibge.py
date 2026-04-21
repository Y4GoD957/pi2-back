from pydantic import BaseModel


class AdministrativeRegion(BaseModel):
    id: str
    nome: str
