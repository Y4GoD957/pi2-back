from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.educenso import router as educenso_router
from app.api.routes.health import router as health_router
from app.api.routes.users import router as users_router
from app.core.config import get_settings

settings = get_settings()

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router, prefix=settings.api_v1_prefix)
api_router.include_router(users_router, prefix=settings.api_v1_prefix)
api_router.include_router(educenso_router, prefix=settings.api_v1_prefix)
