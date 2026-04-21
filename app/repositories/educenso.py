from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.dim_localidade import DimLocalidade
from app.models.fato_educacao import FatoEducacao
from app.models.fato_socioeconomico import FatoSocioeconomico
from app.models.relatorio import Relatorio


class EducensoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def fetch_reports(self, user_id: int | None = None) -> list[Relatorio]:
        statement = (
            select(Relatorio)
            .options(
                joinedload(Relatorio.localidade),
                joinedload(Relatorio.fato_educacao),
                joinedload(Relatorio.fato_socioeconomico),
            )
            .order_by(Relatorio.data_criacao.desc())
        )
        if user_id is not None:
            statement = statement.where(Relatorio.id_usuario == user_id)

        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def fetch_localities(self) -> list[DimLocalidade]:
        statement = select(DimLocalidade).order_by(DimLocalidade.UF.asc(), DimLocalidade.municipio.asc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def fetch_facts_education_by_year(self, year: int) -> list[FatoEducacao]:
        statement = (
            select(FatoEducacao)
            .where(FatoEducacao.ano == year)
            .order_by(FatoEducacao.id_fato_educacao.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def fetch_facts_socioeconomic_by_year(self, year: int) -> list[FatoSocioeconomico]:
        statement = (
            select(FatoSocioeconomico)
            .where(FatoSocioeconomico.ano == year)
            .order_by(FatoSocioeconomico.id_fato_socioeconomico.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def fetch_available_years(self) -> list[int]:
        education_statement = select(FatoEducacao.ano).order_by(FatoEducacao.ano.desc())
        socioeconomic_statement = select(FatoSocioeconomico.ano).order_by(FatoSocioeconomico.ano.desc())

        education_result = await self.session.execute(education_statement)
        socioeconomic_result = await self.session.execute(socioeconomic_statement)

        education_years = set(education_result.scalars().all())
        socioeconomic_years = set(socioeconomic_result.scalars().all())
        return sorted(education_years.intersection(socioeconomic_years), reverse=True)

    async def create_report(self, report: Relatorio) -> Relatorio:
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(
            report,
            attribute_names=["localidade", "fato_educacao", "fato_socioeconomico"],
        )
        return report
