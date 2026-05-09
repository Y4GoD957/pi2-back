from sqlalchemy.ext.asyncio import AsyncEngine

from app.models.politica_publica import (
    PoliticaPublica,
    PoliticaPublicaBeneficiario,
    PoliticaPublicaInstituicao,
    PoliticaPublicaObjetivoEspecifico,
)


async def ensure_public_policy_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(PoliticaPublica.__table__.create, checkfirst=True)
        await connection.run_sync(PoliticaPublicaObjetivoEspecifico.__table__.create, checkfirst=True)
        await connection.run_sync(PoliticaPublicaInstituicao.__table__.create, checkfirst=True)
        await connection.run_sync(PoliticaPublicaBeneficiario.__table__.create, checkfirst=True)
