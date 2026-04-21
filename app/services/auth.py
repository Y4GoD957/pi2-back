from httpx import AsyncClient, HTTPStatusError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.repositories.user import UserRepository
from app.schemas.auth import LoginPayload, LoginResponse, RegisterPayload, RegisterResponse
from app.schemas.user import AuthUserResponse


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.user_repository = UserRepository(session)

    async def login(self, payload: LoginPayload) -> LoginResponse:
        if not self.settings.supabase_url or not self.settings.supabase_anon_key:
            raise ApiError("Supabase Auth nao configurado no backend.", 500)

        url = f"{self.settings.supabase_url}/auth/v1/token?grant_type=password"
        headers = {
            "apikey": self.settings.supabase_anon_key,
            "Content-Type": "application/json",
        }

        try:
            async with AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json={"email": payload.email, "password": payload.password},
                )
                response.raise_for_status()
        except HTTPStatusError as exc:
            raise ApiError("E-mail ou senha incorretos.", 401) from exc

        data = response.json()
        auth_user_id = data.get("user", {}).get("id")
        if not auth_user_id:
            raise ApiError("Nao foi possivel recuperar os dados do usuario.", 500)

        user = await self.user_repository.get_by_auth_user_id(auth_user_id)
        if user is None:
            raise ApiError("Nao foi possivel localizar os dados da sua conta.", 404)

        return LoginResponse(
            token=data.get("access_token"),
            user=AuthUserResponse.model_validate(user, from_attributes=True),
        )

    async def register(self, payload: RegisterPayload) -> RegisterResponse:
        if not self.settings.supabase_url or not self.settings.supabase_anon_key:
            raise ApiError("Supabase Auth nao configurado no backend.", 500)

        url = f"{self.settings.supabase_url}/auth/v1/signup"
        headers = {
            "apikey": self.settings.supabase_anon_key,
            "Content-Type": "application/json",
        }

        try:
            async with AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json={
                        "email": payload.email,
                        "password": payload.password,
                        "data": {
                            "name": payload.name,
                            "cpf": payload.cpf,
                            "birth_date": payload.birthDate,
                            "phone": payload.phone,
                            "address": payload.address,
                            "profile_id": payload.profileId,
                        },
                    },
                )
                response.raise_for_status()
        except HTTPStatusError as exc:
            raise ApiError("Nao foi possivel concluir o cadastro.", 400) from exc

        return RegisterResponse(
            message=(
                "Cadastro enviado com sucesso. Verifique seu e-mail para concluir "
                "a ativacao da conta, se necessario."
            )
        )
