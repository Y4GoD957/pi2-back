from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DimLocalidade(Base):
    __tablename__ = "dim_localidade"

    id_localidade: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_ibge: Mapped[int] = mapped_column(BigInteger, nullable=False)
    UF: Mapped[str] = mapped_column(String(2), nullable=False)
    municipio: Mapped[str] = mapped_column(String(255), nullable=False)
    setor_censitario: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_criacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
