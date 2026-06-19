from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from application.queries.dtos import ApplicatorDTO, DashboardDTO
from application.queries.interfaces import DashboardQueryService
from domain.entities import ApplicatorState
from infrastructure.models.orm import MachineORM


class SQLAlchemyDashboardQueryService(DashboardQueryService):
    """SQLAlchemy implementation of DashboardQueryService."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_dashboard(self, hardware_code: str) -> DashboardDTO | None:
        stmt = (
            select(MachineORM)
            .where(MachineORM.hardware_code == hardware_code)
            .options(selectinload(MachineORM.zone), selectinload(MachineORM.applicators))
        )
        result = await self.session.execute(stmt)
        machine_orm = result.scalar_one_or_none()

        if not machine_orm:
            return None

        current_capacity = len(machine_orm.applicators)
        current_in_use = sum(1 for app in machine_orm.applicators if app.state == ApplicatorState.IN_USE)

        applicators_dto = [
            ApplicatorDTO(
                id=app.id,
                serial_number=app.serial_number,
                state=app.state.value,
            )
            for app in machine_orm.applicators
        ]

        return DashboardDTO(
            machine_id=machine_orm.id,
            hardware_code=machine_orm.hardware_code,
            zone_name=machine_orm.zone.name,
            max_capacity=machine_orm.max_capacity,
            current_capacity=current_capacity,
            max_in_use=machine_orm.zone.max_in_use,
            current_in_use=current_in_use,
            applicators=applicators_dto,
        )
