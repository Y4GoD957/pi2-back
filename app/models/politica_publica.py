from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PoliticaPublica(Base):
    __tablename__ = "politica_publica"

    id_politica_publica: Mapped[int] = mapped_column(Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    objetivo_geral: Mapped[str] = mapped_column(Text, nullable=False)
    indicador_chave: Mapped[str | None] = mapped_column(String(120), nullable=True)
    id_dim_localidade: Mapped[int | None] = mapped_column(
        ForeignKey("dim_localidade.id_localidade"),
        nullable=True,
    )
    id_relatorio: Mapped[int | None] = mapped_column(ForeignKey("relatorio.id_relatorio"), nullable=True)
    id_usuario_criador: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario"), nullable=False)
    data_criacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_atualizacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    localidade = relationship("DimLocalidade")
    relatorio = relationship("Relatorio")
    usuario_criador = relationship("Usuario")
    objetivos_especificos = relationship(
        "PoliticaPublicaObjetivoEspecifico",
        back_populates="politica_publica",
        cascade="all, delete-orphan",
        order_by="PoliticaPublicaObjetivoEspecifico.ordem.asc()",
    )
    instituicoes_responsaveis = relationship(
        "PoliticaPublicaInstituicao",
        back_populates="politica_publica",
        cascade="all, delete-orphan",
        order_by="PoliticaPublicaInstituicao.id_politica_publica_instituicao.asc()",
    )
    beneficiarios = relationship(
        "PoliticaPublicaBeneficiario",
        back_populates="politica_publica",
        cascade="all, delete-orphan",
        order_by="PoliticaPublicaBeneficiario.id_politica_publica_beneficiario.asc()",
    )


class PoliticaPublicaObjetivoEspecifico(Base):
    __tablename__ = "politica_publica_objetivo_especifico"

    id_objetivo_especifico: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_politica_publica: Mapped[int] = mapped_column(
        ForeignKey("politica_publica.id_politica_publica", ondelete="CASCADE"),
        nullable=False,
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)

    politica_publica = relationship("PoliticaPublica", back_populates="objetivos_especificos")


class PoliticaPublicaInstituicao(Base):
    __tablename__ = "politica_publica_instituicao"

    id_politica_publica_instituicao: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_politica_publica: Mapped[int] = mapped_column(
        ForeignKey("politica_publica.id_politica_publica", ondelete="CASCADE"),
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)

    politica_publica = relationship("PoliticaPublica", back_populates="instituicoes_responsaveis")


class PoliticaPublicaBeneficiario(Base):
    __tablename__ = "politica_publica_beneficiario"

    id_politica_publica_beneficiario: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_politica_publica: Mapped[int] = mapped_column(
        ForeignKey("politica_publica.id_politica_publica", ondelete="CASCADE"),
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)

    politica_publica = relationship("PoliticaPublica", back_populates="beneficiarios")
