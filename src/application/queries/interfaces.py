from abc import ABC, abstractmethod

from application.queries.dtos import (
    ApplicatorListItemDTO,
    BlockedApplicatorDTO,
    DashboardDTO,
    MachineDTO,
    MovementLogDTO,
    ZoneDTO,
)


class DashboardQueryService(ABC):
    """Abstract query service for dashboard data."""

    @abstractmethod
    async def get_dashboard(self, hardware_code: str) -> DashboardDTO | None:
        pass


class ApplicatorQueryService(ABC):
    """Abstract query service for applicator listings."""

    @abstractmethod
    async def list_all(self) -> list[ApplicatorListItemDTO]:
        pass

    @abstractmethod
    async def list_blocked(self) -> list[BlockedApplicatorDTO]:
        pass

    @abstractmethod
    async def get_history(self, applicator_id: int) -> list[MovementLogDTO]:
        pass

    @abstractmethod
    async def list_recent_movements(self, limit: int) -> list[MovementLogDTO]:
        pass


class MachineQueryService(ABC):
    """Abstract query service for machine listings."""

    @abstractmethod
    async def list_all(self) -> list[MachineDTO]:
        pass


class ZoneQueryService(ABC):
    """Abstract query service for zone listings."""

    @abstractmethod
    async def list_all(self) -> list[ZoneDTO]:
        pass


__all__ = [
    "ApplicatorQueryService",
    "DashboardQueryService",
    "MachineQueryService",
    "ZoneQueryService",
]
