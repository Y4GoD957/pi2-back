from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.perfil import Perfil
from app.models.usuario import Usuario


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_auth_user_id(self, auth_user_id: str) -> Usuario | None:
        statement = (
            select(Usuario)
            .options(joinedload(Usuario.perfil))
            .where(Usuario.auth_user_id == auth_user_id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_profiles(self) -> list[Perfil]:
        statement = select(Perfil).order_by(Perfil.descricao.asc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_profile_by_id(self, profile_id: int) -> Perfil | None:
        statement = select(Perfil).where(Perfil.id_perfil == profile_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create(self, user: Usuario) -> Usuario:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user, attribute_names=["perfil"])
        return user

    async def rollback(self) -> None:
        await self.session.rollback()

    async def update(self, user: Usuario) -> Usuario:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user, attribute_names=["perfil"])
        return user
