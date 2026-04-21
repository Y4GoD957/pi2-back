from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.user import AuthUserResponse, ProfileOption, UpdateUserAccountPayload
from app.services.user import UserService

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=AuthUserResponse)
async def get_current_user_account(current_user: CurrentUser) -> AuthUserResponse:
    return AuthUserResponse.model_validate(current_user, from_attributes=True)


@router.put("/users/me", response_model=AuthUserResponse)
async def update_current_user_account(
    payload: UpdateUserAccountPayload,
    session: DbSession,
    current_user: CurrentUser,
) -> AuthUserResponse:
    service = UserService(session)
    updated_user = await service.update_current_user_account(current_user, payload)
    return AuthUserResponse.model_validate(updated_user, from_attributes=True)


@router.get("/profiles", response_model=list[ProfileOption])
async def list_profiles(session: DbSession) -> list[ProfileOption]:
    service = UserService(session)
    return await service.fetch_profiles()
