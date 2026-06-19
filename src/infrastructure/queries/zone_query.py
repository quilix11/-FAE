from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.dtos import ZoneDTO
from application.queries.interfaces import ZoneQueryService
from infrastructure.models.orm import ZoneORM


class SQLAlchemyZoneQueryService(ZoneQueryService):
    """SQLAlchemy implementation of ZoneQueryService."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[ZoneDTO]:
        stmt = select(ZoneORM)
        result = await self.session.execute(stmt)
        zones = result.scalars().all()
        return [ZoneDTO(id=z.id, name=z.name) for z in zones]
