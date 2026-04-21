from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FatoEducacao(Base):
    __tablename__ = "fato_educacao"

    id_fato_educacao: Mapped[int] = mapped_column(Integer, primary_key=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    taxa_matricula: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    taxa_frequencia_escolar: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    taxa_analfabetismo: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    data_criacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
