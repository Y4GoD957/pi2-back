from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Relatorio(Base):
    __tablename__ = "relatorio"

    id_relatorio: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[int] = mapped_column(Integer, nullable=False)
    likert_educacao: Mapped[float] = mapped_column(Float, nullable=False)
    likert_socioeconomico: Mapped[float] = mapped_column(Float, nullable=False)
    avaliacao: Mapped[str] = mapped_column(Text, nullable=False)
    filtros_aplicados: Mapped[str | None] = mapped_column(Text, nullable=True)
    politica_publica: Mapped[str] = mapped_column(Text, nullable=False)
    data_criacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario"), nullable=False)
    id_fato_educacao: Mapped[int] = mapped_column(ForeignKey("fato_educacao.id_fato_educacao"), nullable=False)
    id_fato_socioeconomico: Mapped[int] = mapped_column(
        ForeignKey("fato_socioeconomico.id_fato_socioeconomico"),
        nullable=False,
    )
    id_dim_localidade: Mapped[int] = mapped_column(ForeignKey("dim_localidade.id_localidade"), nullable=False)

    localidade = relationship("DimLocalidade")
    fato_educacao = relationship("FatoEducacao")
    fato_socioeconomico = relationship("FatoSocioeconomico")
    usuario = relationship("Usuario")
