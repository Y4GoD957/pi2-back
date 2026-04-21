from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import AuthUserResponse


class LoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class RegisterPayload(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6)
    cpf: str = Field(min_length=11, max_length=14)
    birthDate: str
    phone: str
    address: str
    profileId: int


class LoginResponse(BaseModel):
    token: str | None
    user: AuthUserResponse


class RegisterResponse(BaseModel):
    message: str
