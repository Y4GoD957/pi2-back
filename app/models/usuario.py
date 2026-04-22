from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True)
    auth_user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    data_nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    CPF: Mapped[str | None] = mapped_column(String(14), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    endereco: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_criacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    id_perfil: Mapped[int | None] = mapped_column(ForeignKey("perfil.id_perfil"), nullable=True)

    perfil = relationship("Perfil")
