from httpx import AsyncClient, HTTPStatusError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.models.usuario import Usuario
from app.repositories.user import UserRepository
from app.schemas.user import ProfileOption, UpdateUserAccountPayload


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.user_repository = UserRepository(session)

    async def fetch_profiles(self) -> list[ProfileOption]:
        profiles = await self.user_repository.list_profiles()
        return [ProfileOption(id=item.id_perfil, description=item.descricao) for item in profiles]

    async def update_current_user_account(
        self,
        current_user: Usuario,
        payload: UpdateUserAccountPayload,
    ) -> Usuario:
        if payload.email != current_user.email:
            await self._sync_supabase_email(current_user.auth_user_id, payload.email)

        current_user.nome = payload.name
        current_user.email = payload.email
        current_user.CPF = payload.cpf
        current_user.data_nascimento = payload.birthDate
        current_user.telefone = payload.phone
        current_user.endereco = payload.address
        current_user.id_perfil = payload.profileId
        return await self.user_repository.update(current_user)

    async def _sync_supabase_email(self, auth_user_id: str, email: str) -> None:
        if not self.settings.supabase_url or not self.settings.supabase_service_role_key:
            raise ApiError(
                "Alteracao de e-mail exige SUPABASE_SERVICE_ROLE_KEY configurada no backend.",
                500,
            )

        url = f"{self.settings.supabase_url}/auth/v1/admin/users/{auth_user_id}"
        headers = {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

        try:
            async with AsyncClient(timeout=15.0) as client:
                response = await client.put(url, headers=headers, json={"email": email})
                response.raise_for_status()
        except HTTPStatusError as exc:
            raise ApiError("Nao foi possivel sincronizar o e-mail no Supabase Auth.", 400) from exc
