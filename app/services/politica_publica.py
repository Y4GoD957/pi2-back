from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApiError
from app.models.politica_publica import PoliticaPublica
from app.models.usuario import Usuario
from app.repositories.politica_publica import PoliticaPublicaRepository
from app.schemas.politica_publica import (
    PoliticaPublicaCreatePayload,
    PoliticaPublicaDeleteResponse,
    PoliticaPublicaDetalhe,
    PoliticaPublicaFormOptions,
    PoliticaPublicaListResponse,
    PoliticaPublicaNamedRelationResponse,
    PoliticaPublicaObjetivoEspecificoResponse,
    PoliticaPublicaResumo,
    PoliticaPublicaUpdatePayload,
)


INDICATOR_OPTIONS = [
    {"chave": "internet_access_pct", "nome": "Acesso a internet"},
    {"chave": "school_attendance_rate", "nome": "Frequencia escolar"},
    {"chave": "illiteracy_rate_15_plus", "nome": "Analfabetismo 15+"},
    {"chave": "adequate_housing_pct", "nome": "Moradia adequada"},
    {"chave": "population_resident", "nome": "Populacao residente"},
]


class PoliticaPublicaService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = PoliticaPublicaRepository(session)

    async def list_policies(self) -> PoliticaPublicaListResponse:
        items = await self.repository.list_policies()
        return PoliticaPublicaListResponse(items=[self._to_summary(item) for item in items])

    async def get_policy_by_id(self, policy_id: int) -> PoliticaPublicaDetalhe:
        policy = await self.repository.get_policy_by_id(policy_id)
        if policy is None:
            raise ApiError("Politica publica nao encontrada.", 404)
        return self._to_detail(policy)

    async def create_policy(
        self,
        payload: PoliticaPublicaCreatePayload,
        current_user: Usuario,
    ) -> PoliticaPublicaDetalhe:
        await self._validate_links(payload.id_dim_localidade, payload.id_relatorio)

        now = datetime.now(timezone.utc)
        policy = PoliticaPublica(
            titulo=payload.titulo,
            objetivo_geral=payload.objetivo_geral,
            indicador_chave=payload.indicador_chave,
            id_dim_localidade=payload.id_dim_localidade,
            id_relatorio=payload.id_relatorio,
            id_usuario_criador=current_user.id_usuario,
            data_criacao=now,
            data_atualizacao=now,
        )
        self.repository.replace_children(
            policy,
            objetivos_especificos=[item.descricao for item in payload.objetivos_especificos],
            instituicoes_responsaveis=payload.instituicoes_responsaveis,
            beneficiarios=payload.beneficiarios,
        )
        created = await self.repository.create(policy)
        return self._to_detail(created)

    async def update_policy(
        self,
        policy_id: int,
        payload: PoliticaPublicaUpdatePayload,
    ) -> PoliticaPublicaDetalhe:
        policy = await self.repository.get_policy_by_id(policy_id)
        if policy is None:
            raise ApiError("Politica publica nao encontrada.", 404)

        await self._validate_links(payload.id_dim_localidade, payload.id_relatorio)

        policy.titulo = payload.titulo
        policy.objetivo_geral = payload.objetivo_geral
        policy.indicador_chave = payload.indicador_chave
        policy.id_dim_localidade = payload.id_dim_localidade
        policy.id_relatorio = payload.id_relatorio
        policy.data_atualizacao = datetime.now(timezone.utc)

        self.repository.replace_children(
            policy,
            objetivos_especificos=[item.descricao for item in payload.objetivos_especificos],
            instituicoes_responsaveis=payload.instituicoes_responsaveis,
            beneficiarios=payload.beneficiarios,
        )
        updated = await self.repository.update(policy)
        return self._to_detail(updated)

    async def delete_policy(self, policy_id: int) -> PoliticaPublicaDeleteResponse:
        policy = await self.repository.get_policy_by_id(policy_id)
        if policy is None:
            raise ApiError("Politica publica nao encontrada.", 404)

        await self.repository.delete(policy)
        return PoliticaPublicaDeleteResponse(message="Politica publica removida com sucesso.")

    async def fetch_form_options(self) -> PoliticaPublicaFormOptions:
        localities = await self.repository.list_localities()
        reports = await self.repository.list_reports()
        return PoliticaPublicaFormOptions(
            localidades=[
                {
                    "id": item.id_localidade,
                    "nome": item.municipio,
                    "uf": item.UF,
                    "codigo_ibge": item.codigo_ibge,
                }
                for item in localities
            ],
            indicadores_disponiveis=INDICATOR_OPTIONS,
            relatorios=[
                {
                    "id": item.id_relatorio,
                    "titulo": item.avaliacao[:120],
                    "data_criacao": item.data_criacao.isoformat() if item.data_criacao else None,
                }
                for item in reports
            ],
        )

    async def _validate_links(self, locality_id: int | None, report_id: int | None) -> None:
        if locality_id is not None:
            locality = await self.repository.get_locality_by_id(locality_id)
            if locality is None:
                raise ApiError("Localidade vinculada nao encontrada.", 400)

        if report_id is not None:
            report = await self.repository.get_report_by_id(report_id)
            if report is None:
                raise ApiError("Relatorio vinculado nao encontrado.", 400)

    def _to_summary(self, policy: PoliticaPublica) -> PoliticaPublicaResumo:
        return PoliticaPublicaResumo(
            id=policy.id_politica_publica,
            titulo=policy.titulo,
            objetivo_geral=policy.objetivo_geral,
            indicador_chave=policy.indicador_chave,
            id_dim_localidade=policy.id_dim_localidade,
            id_relatorio=policy.id_relatorio,
            data_criacao=policy.data_criacao,
            data_atualizacao=policy.data_atualizacao,
            instituicoes_responsaveis=[
                PoliticaPublicaNamedRelationResponse(
                    id=item.id_politica_publica_instituicao,
                    nome=item.nome,
                )
                for item in policy.instituicoes_responsaveis
            ],
            beneficiarios=[
                PoliticaPublicaNamedRelationResponse(
                    id=item.id_politica_publica_beneficiario,
                    nome=item.nome,
                )
                for item in policy.beneficiarios
            ],
            objetivos_especificos=[
                PoliticaPublicaObjetivoEspecificoResponse(
                    id=item.id_objetivo_especifico,
                    ordem=item.ordem,
                    descricao=item.descricao,
                )
                for item in policy.objetivos_especificos
            ],
        )

    def _to_detail(self, policy: PoliticaPublica) -> PoliticaPublicaDetalhe:
        summary = self._to_summary(policy)
        return PoliticaPublicaDetalhe(
            **summary.model_dump(),
            id_usuario_criador=policy.id_usuario_criador,
            localidade_nome=policy.localidade.municipio if policy.localidade else None,
            localidade_uf=policy.localidade.UF if policy.localidade else None,
            relatorio_resumo=policy.relatorio.avaliacao[:160] if policy.relatorio else None,
        )
