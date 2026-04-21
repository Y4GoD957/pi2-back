from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FatoSocioeconomico(Base):
    __tablename__ = "fato_socioeconomico"

    id_fato_socioeconomico: Mapped[int] = mapped_column(Integer, primary_key=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    renda_per_capita: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    acesso_internet_perc: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    acesso_saneamento_perc: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    data_criacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
