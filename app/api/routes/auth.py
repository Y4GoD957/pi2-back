from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.auth import LoginPayload, LoginResponse, RegisterPayload, RegisterResponse
from app.schemas.user import AuthUserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginPayload, session: DbSession) -> LoginResponse:
    service = AuthService(session)
    return await service.login(payload)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterPayload, session: DbSession) -> RegisterResponse:
    service = AuthService(session)
    return await service.register(payload)


@router.get("/me", response_model=AuthUserResponse)
async def get_authenticated_user(current_user: CurrentUser) -> AuthUserResponse:
    return AuthUserResponse.model_validate(current_user, from_attributes=True)
