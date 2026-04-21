from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db_session
from app.models.usuario import Usuario

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]
