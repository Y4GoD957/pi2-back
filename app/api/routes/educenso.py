from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.educenso import (
    CreateReportPayload,
    DfHeatMapData,
    EducensoAnalysisFilters,
    EducensoDashboardResponse,
    ReportCreatedResponse,
    ReportDetailResponse,
    ReportFormOptions,
    ReportListItem,
)
from app.schemas.ibge import AdministrativeRegion
from app.services.educenso import EducensoService

router = APIRouter(prefix="/educenso", tags=["educenso"])


def build_filters(
    year: int | None = Query(default=None),
    uf: str | None = Query(default=None),
    municipality: str | None = Query(default=None),
    census_sector: str | None = Query(default=None),
    report_type: int | None = Query(default=None),
) -> EducensoAnalysisFilters:
    return EducensoAnalysisFilters(
        year=year,
        uf=uf,
        municipality=municipality,
        censusSector=census_sector,
        reportType=report_type,
    )


@router.get("/dashboard", response_model=EducensoDashboardResponse)
async def get_dashboard(
    session: DbSession,
    filters: Annotated[EducensoAnalysisFilters, Depends(build_filters)],
) -> EducensoDashboardResponse:
    service = EducensoService(session)
    return await service.fetch_dashboard(filters)


@router.get("/reports", response_model=list[ReportListItem])
async def list_user_reports(
    session: DbSession,
    current_user: CurrentUser,
    filters: Annotated[EducensoAnalysisFilters, Depends(build_filters)],
) -> list[ReportListItem]:
    service = EducensoService(session)
    return await service.fetch_user_reports(current_user.id_usuario, filters)


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
async def get_report_by_id(
    report_id: int,
    session: DbSession,
    current_user: CurrentUser,
) -> ReportDetailResponse:
    service = EducensoService(session)
    return await service.fetch_report_by_id(current_user.id_usuario, report_id)


@router.get("/report-form-options", response_model=ReportFormOptions)
async def get_report_form_options(session: DbSession) -> ReportFormOptions:
    service = EducensoService(session)
    return await service.fetch_report_form_options()


@router.post("/reports", response_model=ReportCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: CreateReportPayload,
    session: DbSession,
    current_user: CurrentUser,
) -> ReportCreatedResponse:
    service = EducensoService(session)
    return await service.create_user_report(current_user.id_usuario, payload)


@router.get("/df/heatmap", response_model=DfHeatMapData)
async def get_df_heatmap(
    session: DbSession,
    filters: Annotated[EducensoAnalysisFilters, Depends(build_filters)],
) -> DfHeatMapData:
    service = EducensoService(session)
    return await service.fetch_df_heatmap(filters)


@router.get("/df/regions", response_model=list[AdministrativeRegion])
async def get_df_regions(session: DbSession) -> list[AdministrativeRegion]:
    service = EducensoService(session)
    return await service.fetch_df_regions()
