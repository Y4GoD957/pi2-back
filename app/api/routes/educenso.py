from typing import Annotated, Any

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
from app.schemas.ibge import AdministrativeRegion, DfMetadataResponse
from app.schemas.public_data import (
    DataSourcesResponse,
    DfChartsResponse,
    DfHeatmapResponse,
    DfIndicatorsResponse,
    DfSummaryResponse,
)
from app.services.educenso import EducensoService
from app.services.educenso_public_data import EducensoPublicDataService

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


@router.get("/df/heatmap-legacy", response_model=DfHeatMapData)
async def get_df_heatmap_legacy(
    session: DbSession,
    filters: Annotated[EducensoAnalysisFilters, Depends(build_filters)],
) -> DfHeatMapData:
    service = EducensoService(session)
    return await service.fetch_df_heatmap(filters)


@router.get("/df/geojson")
async def get_df_geojson() -> Any:
    service = EducensoPublicDataService()
    return await service.fetch_df_geojson()


@router.get("/df/regions", response_model=list[AdministrativeRegion])
async def get_df_regions() -> list[AdministrativeRegion]:
    service = EducensoPublicDataService()
    return await service.fetch_df_regions()


@router.get("/data-sources", response_model=DataSourcesResponse)
async def get_data_sources() -> DataSourcesResponse:
    service = EducensoPublicDataService()
    return await service.fetch_data_sources()


@router.get("/df/metadata", response_model=DfMetadataResponse)
async def get_df_metadata() -> DfMetadataResponse:
    service = EducensoPublicDataService()
    return await service.fetch_df_metadata()


@router.get("/df/indicators", response_model=DfIndicatorsResponse)
async def get_df_indicators(
    year: int | None = Query(default=None),
    theme: str | None = Query(default=None),
    indicator: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> DfIndicatorsResponse:
    service = EducensoPublicDataService()
    return await service.fetch_df_indicators(
        year=year,
        theme=theme,
        indicator=indicator,
        source=source,
    )


@router.get("/df/heatmap", response_model=DfHeatmapResponse)
async def get_df_heatmap(
    year: int | None = Query(default=None),
    indicator: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> DfHeatmapResponse:
    service = EducensoPublicDataService()
    return await service.fetch_df_heatmap(
        year=year,
        indicator=indicator,
        source=source,
    )


@router.get("/df/charts", response_model=DfChartsResponse)
async def get_df_charts(
    year: int | None = Query(default=None),
    indicator: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> DfChartsResponse:
    service = EducensoPublicDataService()
    return await service.fetch_df_charts(
        year=year,
        indicator=indicator,
        source=source,
    )


@router.get("/df/summary", response_model=DfSummaryResponse)
async def get_df_summary(
    year: int | None = Query(default=None),
    source: str | None = Query(default=None),
) -> DfSummaryResponse:
    service = EducensoPublicDataService()
    return await service.fetch_df_summary(
        year=year,
        source=source,
    )
