from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.politica_publica import (
    PoliticaPublicaCreatePayload,
    PoliticaPublicaDeleteResponse,
    PoliticaPublicaDetalhe,
    PoliticaPublicaFormOptions,
    PoliticaPublicaListResponse,
    PoliticaPublicaUpdatePayload,
)
from app.services.politica_publica import PoliticaPublicaService

router = APIRouter(prefix="/politicas-publicas", tags=["politicas-publicas"])


@router.get("", response_model=PoliticaPublicaListResponse)
async def list_politicas_publicas(
    session: DbSession,
    _: CurrentUser,
) -> PoliticaPublicaListResponse:
    service = PoliticaPublicaService(session)
    return await service.list_policies()


@router.get("/form-options", response_model=PoliticaPublicaFormOptions)
async def get_politicas_publicas_form_options(
    session: DbSession,
    _: CurrentUser,
) -> PoliticaPublicaFormOptions:
    service = PoliticaPublicaService(session)
    return await service.fetch_form_options()


@router.get("/{policy_id}", response_model=PoliticaPublicaDetalhe)
async def get_politica_publica_by_id(
    policy_id: int,
    session: DbSession,
    _: CurrentUser,
) -> PoliticaPublicaDetalhe:
    service = PoliticaPublicaService(session)
    return await service.get_policy_by_id(policy_id)


@router.post("", response_model=PoliticaPublicaDetalhe, status_code=status.HTTP_201_CREATED)
async def create_politica_publica(
    payload: PoliticaPublicaCreatePayload,
    session: DbSession,
    current_user: CurrentUser,
) -> PoliticaPublicaDetalhe:
    service = PoliticaPublicaService(session)
    return await service.create_policy(payload, current_user)


@router.put("/{policy_id}", response_model=PoliticaPublicaDetalhe)
async def update_politica_publica(
    policy_id: int,
    payload: PoliticaPublicaUpdatePayload,
    session: DbSession,
    _: CurrentUser,
) -> PoliticaPublicaDetalhe:
    service = PoliticaPublicaService(session)
    return await service.update_policy(policy_id, payload)


@router.delete("/{policy_id}", response_model=PoliticaPublicaDeleteResponse)
async def delete_politica_publica(
    policy_id: int,
    session: DbSession,
    _: CurrentUser,
) -> PoliticaPublicaDeleteResponse:
    service = PoliticaPublicaService(session)
    return await service.delete_policy(policy_id)
