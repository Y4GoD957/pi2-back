from datetime import date

from httpx import AsyncClient, HTTPStatusError, RequestError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.models.usuario import Usuario
from app.repositories.user import UserRepository
from app.schemas.auth import LoginPayload, LoginResponse, RegisterPayload, RegisterResponse
from app.schemas.user import AuthUserResponse


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.user_repository = UserRepository(session)

    @staticmethod
    def _extract_supabase_error_message(exc: HTTPStatusError, fallback_message: str) -> str:
        try:
            error_payload = exc.response.json()
        except ValueError:
            return fallback_message

        for key in ("msg", "message", "error_description", "error"):
            value = error_payload.get(key)
            if isinstance(value, str) and value.strip():
                normalized_value = value.strip()
                if normalized_value == "Database error saving new user":
                    return (
                        "O Supabase recusou o cadastro por um gatilho SQL externo. "
                        "Se este backend usa o banco configurado em DATABASE_URL, "
                        "remova ou ajuste o trigger on_auth_user_created no projeto Supabase."
                    )
                return normalized_value

        return fallback_message

    @staticmethod
    def _parse_birth_date(value: str | None) -> date | None:
        if not value:
            return None

        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ApiError("Data de nascimento invalida.", 400) from exc

    async def _ensure_profile_exists(self, profile_id: int) -> None:
        profile = await self.user_repository.get_profile_by_id(profile_id)
        if profile is None:
            raise ApiError("Perfil informado nao foi encontrado.", 400)

    async def _ensure_local_user(
        self,
        *,
        auth_user: dict,
        default_email: str,
        default_name: str,
        default_cpf: str | None = None,
        default_birth_date: str | None = None,
        default_phone: str | None = None,
        default_address: str | None = None,
        default_profile_id: int | None = None,
    ):
        auth_user_id = auth_user.get("id")
        if not auth_user_id:
            raise ApiError("Nao foi possivel recuperar o identificador do usuario autenticado.", 500)

        existing_user = await self.user_repository.get_by_auth_user_id(auth_user_id)
        if existing_user is not None:
            return existing_user

        user_metadata = auth_user.get("user_metadata") or auth_user.get("raw_user_meta_data") or {}
        profile_id = default_profile_id or user_metadata.get("profile_id") or 2
        await self._ensure_profile_exists(int(profile_id))

        user = Usuario(
            auth_user_id=auth_user_id,
            nome=str(user_metadata.get("name") or default_name),
            data_nascimento=self._parse_birth_date(user_metadata.get("birth_date") or default_birth_date),
            CPF=str(user_metadata.get("cpf") or default_cpf or "") or None,
            email=str(auth_user.get("email") or default_email),
            telefone=str(user_metadata.get("phone") or default_phone or "") or None,
            endereco=str(user_metadata.get("address") or default_address or "") or None,
            id_perfil=int(profile_id),
        )

        try:
            return await self.user_repository.create(user)
        except IntegrityError as exc:
            await self.user_repository.rollback()
            raise ApiError(
                "Nao foi possivel salvar os dados do usuario no banco local.",
                409,
            ) from exc
        except SQLAlchemyError as exc:
            await self.user_repository.rollback()
            raise ApiError(
                "Nao foi possivel salvar os dados do usuario no banco local.",
                500,
            ) from exc

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
            error_message = self._extract_supabase_error_message(exc, "E-mail ou senha incorretos.")
            raise ApiError(error_message, 401) from exc
        except RequestError as exc:
            raise ApiError(
                "Nao foi possivel comunicar com o servico de autenticacao no momento.",
                503,
            ) from exc

        data = response.json()
        auth_user = data.get("user") or {}
        user = await self._ensure_local_user(
            auth_user=auth_user,
            default_email=str(payload.email),
            default_name=str((auth_user.get("user_metadata") or {}).get("name") or payload.email.split("@", 1)[0]),
        )

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
            error_message = self._extract_supabase_error_message(
                exc,
                "Nao foi possivel concluir o cadastro.",
            )
            raise ApiError(error_message, 400) from exc
        except RequestError as exc:
            raise ApiError(
                "Nao foi possivel comunicar com o servico de autenticacao no momento.",
                503,
            ) from exc

        data = response.json()
        auth_user = data.get("user") or {}
        await self._ensure_local_user(
            auth_user=auth_user,
            default_email=str(payload.email),
            default_name=payload.name,
            default_cpf=payload.cpf,
            default_birth_date=payload.birthDate,
            default_phone=payload.phone,
            default_address=payload.address,
            default_profile_id=payload.profileId,
        )

        return RegisterResponse(
            message=(
                "Cadastro enviado com sucesso. Verifique seu e-mail para concluir "
                "a ativacao da conta, se necessario."
            )
        )
