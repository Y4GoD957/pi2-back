from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class ProfileOption(BaseModel):
    id: int
    description: str


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    name: str
    cpf: str | None = None
    birthDate: date | None = None
    phone: str | None = None
    address: str | None = None
    profileId: int | None = None
    profileDescription: str | None = None

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if hasattr(obj, "id_usuario"):
            payload = {
                "id": str(obj.id_usuario),
                "email": obj.email,
                "name": obj.nome,
                "cpf": obj.CPF,
                "birthDate": obj.data_nascimento,
                "phone": obj.telefone,
                "address": obj.endereco,
                "profileId": obj.id_perfil,
                "profileDescription": getattr(getattr(obj, "perfil", None), "descricao", None),
            }
            return super().model_validate(payload, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)


class UpdateUserAccountPayload(BaseModel):
    address: str
    birthDate: date
    cpf: str
    email: EmailStr
    name: str
    phone: str
    profileId: int | None = None


class PerfilResponse(BaseModel):
    idPerfil: int
    descricao: str
    dataCriacao: datetime | None = None
