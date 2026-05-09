from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.dim_localidade import DimLocalidade
from app.models.politica_publica import (
    PoliticaPublica,
    PoliticaPublicaBeneficiario,
    PoliticaPublicaInstituicao,
    PoliticaPublicaObjetivoEspecifico,
)
from app.models.relatorio import Relatorio


class PoliticaPublicaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_statement(self):
        return (
            select(PoliticaPublica)
            .options(
                selectinload(PoliticaPublica.objetivos_especificos),
                selectinload(PoliticaPublica.instituicoes_responsaveis),
                selectinload(PoliticaPublica.beneficiarios),
                selectinload(PoliticaPublica.localidade),
                selectinload(PoliticaPublica.relatorio),
            )
            .order_by(PoliticaPublica.data_criacao.desc(), PoliticaPublica.id_politica_publica.desc())
        )

    async def list_policies(self) -> list[PoliticaPublica]:
        result = await self.session.execute(self._base_statement())
        return list(result.scalars().all())

    async def get_policy_by_id(self, policy_id: int) -> PoliticaPublica | None:
        statement = self._base_statement().where(PoliticaPublica.id_politica_publica == policy_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_locality_by_id(self, locality_id: int) -> DimLocalidade | None:
        result = await self.session.execute(
            select(DimLocalidade).where(DimLocalidade.id_localidade == locality_id)
        )
        return result.scalar_one_or_none()

    async def get_report_by_id(self, report_id: int) -> Relatorio | None:
        result = await self.session.execute(
            select(Relatorio).where(Relatorio.id_relatorio == report_id)
        )
        return result.scalar_one_or_none()

    async def list_localities(self) -> list[DimLocalidade]:
        result = await self.session.execute(
            select(DimLocalidade).order_by(DimLocalidade.UF.asc(), DimLocalidade.municipio.asc())
        )
        return list(result.scalars().all())

    async def list_reports(self) -> list[Relatorio]:
        result = await self.session.execute(
            select(Relatorio).order_by(Relatorio.data_criacao.desc(), Relatorio.id_relatorio.desc())
        )
        return list(result.scalars().all())

    async def create(self, policy: PoliticaPublica) -> PoliticaPublica:
        self.session.add(policy)
        await self.session.commit()
        return await self.get_policy_by_id(policy.id_politica_publica)  # type: ignore[return-value]

    async def update(self, policy: PoliticaPublica) -> PoliticaPublica:
        self.session.add(policy)
        await self.session.commit()
        return await self.get_policy_by_id(policy.id_politica_publica)  # type: ignore[return-value]

    async def delete(self, policy: PoliticaPublica) -> None:
        await self.session.delete(policy)
        await self.session.commit()

    def replace_children(
        self,
        policy: PoliticaPublica,
        *,
        objetivos_especificos: list[str],
        instituicoes_responsaveis: list[str],
        beneficiarios: list[str],
    ) -> None:
        policy.objetivos_especificos = [
            PoliticaPublicaObjetivoEspecifico(ordem=index + 1, descricao=descricao)
            for index, descricao in enumerate(objetivos_especificos)
        ]
        policy.instituicoes_responsaveis = [
            PoliticaPublicaInstituicao(nome=nome) for nome in instituicoes_responsaveis
        ]
        policy.beneficiarios = [
            PoliticaPublicaBeneficiario(nome=nome) for nome in beneficiarios
        ]
