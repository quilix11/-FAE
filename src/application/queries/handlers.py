from application.queries.dtos import (
    ApplicatorListItemDTO,
    BlockedApplicatorDTO,
    DashboardDTO,
    MachineDTO,
    MovementLogDTO,
    ZoneDTO,
)
from application.queries.interfaces import (
    ApplicatorQueryService,
    DashboardQueryService,
    MachineQueryService,
    ZoneQueryService,
)


class GetDashboardHandler:
    """Retrieves the dashboard data for a specific machine by hardware code."""

    def __init__(self, query_service: DashboardQueryService) -> None:
        self.query_service = query_service

    async def execute(self, hardware_code: str) -> DashboardDTO | None:
        return await self.query_service.get_dashboard(hardware_code)


class ListMachinesHandler:
    """Retrieves all machines with their zone names."""

    def __init__(self, query_service: MachineQueryService) -> None:
        self.query_service = query_service

    async def execute(self) -> list[MachineDTO]:
        return await self.query_service.list_all()


class ListZonesHandler:
    """Retrieves all zones."""

    def __init__(self, query_service: ZoneQueryService) -> None:
        self.query_service = query_service

    async def execute(self) -> list[ZoneDTO]:
        return await self.query_service.list_all()


class ListApplicatorsHandler:
    """Retrieves the full applicator inventory, including unattached and blocked ones."""

    def __init__(self, query_service: ApplicatorQueryService) -> None:
        self.query_service = query_service

    async def execute(self) -> list[ApplicatorListItemDTO]:
        return await self.query_service.list_all()


class ListBlockedApplicatorsHandler:
    """Retrieves all currently blocked applicators with their latest block reason."""

    def __init__(self, query_service: ApplicatorQueryService) -> None:
        self.query_service = query_service

    async def execute(self) -> list[BlockedApplicatorDTO]:
        return await self.query_service.list_blocked()


class GetApplicatorHistoryHandler:
    """Retrieves the movement history of a single applicator."""

    def __init__(self, query_service: ApplicatorQueryService) -> None:
        self.query_service = query_service

    async def execute(self, applicator_id: int) -> list[MovementLogDTO]:
        return await self.query_service.get_history(applicator_id)


class ListMovementsHandler:
    """Retrieves the most recent movement-history entries across all applicators."""

    def __init__(self, query_service: ApplicatorQueryService) -> None:
        self.query_service = query_service

    async def execute(self, limit: int = 100) -> list[MovementLogDTO]:
        return await self.query_service.list_recent_movements(limit)


__all__ = [
    "GetApplicatorHistoryHandler",
    "GetDashboardHandler",
    "ListApplicatorsHandler",
    "ListBlockedApplicatorsHandler",
    "ListMachinesHandler",
    "ListMovementsHandler",
    "ListZonesHandler",
]
