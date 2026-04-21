from fastapi import Depends, Header, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.db.session import get_db_session
from app.repositories.user import UserRepository


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise ApiError("Token de autenticacao ausente.", status.HTTP_401_UNAUTHORIZED)

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError("Cabecalho Authorization invalido.", status.HTTP_401_UNAUTHORIZED)

    return token


async def get_current_user(
    session: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None),
):
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise ApiError(
            "SUPABASE_JWT_SECRET nao configurado para validar tokens.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    token = _extract_bearer_token(authorization)

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise ApiError("Token invalido ou expirado.", status.HTTP_401_UNAUTHORIZED) from exc

    auth_user_id = payload.get("sub")
    if not auth_user_id:
        raise ApiError("Token sem identificador de usuario.", status.HTTP_401_UNAUTHORIZED)

    repository = UserRepository(session)
    user = await repository.get_by_auth_user_id(auth_user_id)
    if user is None:
        raise ApiError("Usuario autenticado nao encontrado.", status.HTTP_404_NOT_FOUND)

    return user
