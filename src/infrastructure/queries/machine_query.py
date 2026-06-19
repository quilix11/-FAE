from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from application.queries.dtos import MachineDTO
from application.queries.interfaces import MachineQueryService
from infrastructure.models.orm import MachineORM


class SQLAlchemyMachineQueryService(MachineQueryService):
    """SQLAlchemy implementation of MachineQueryService."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[MachineDTO]:
        stmt = select(MachineORM).options(selectinload(MachineORM.zone))
        result = await self.session.execute(stmt)
        machines = result.scalars().all()
        return [
            MachineDTO(
                id=m.id,
                hardware_code=m.hardware_code,
                zone_name=m.zone.name,
            )
            for m in machines
        ]
