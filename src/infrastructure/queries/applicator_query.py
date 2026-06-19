from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from application.queries.dtos import ApplicatorListItemDTO, BlockedApplicatorDTO, MovementLogDTO
from application.queries.interfaces import ApplicatorQueryService
from infrastructure.models.orm import ApplicatorORM, BlockLogORM, MachineORM, MovementLogORM, UserORM, ZoneORM

BLOCKED_ZONE_NAME = "Blocked"


class SQLAlchemyApplicatorQueryService(ApplicatorQueryService):
    """SQLAlchemy implementation of ApplicatorQueryService."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[ApplicatorListItemDTO]:
        stmt = (
            select(ApplicatorORM)
            .options(
                selectinload(ApplicatorORM.machine).selectinload(MachineORM.zone),
                selectinload(ApplicatorORM.zone),
            )
            .order_by(ApplicatorORM.id)
        )
        res = await self.session.execute(stmt)
        applicators = res.scalars().all()
        return [
            ApplicatorListItemDTO(
                id=app.id,
                serial_number=app.serial_number,
                state=app.state.value,
                machine_code=app.machine.hardware_code if app.machine else None,
                zone_name=(app.machine.zone.name if app.machine and app.machine.zone else (app.zone.name if app.zone else None)),
            )
            for app in applicators
        ]

    def _movement_dto(self, log: MovementLogORM, serial: str | None, username: str | None) -> MovementLogDTO:
        return MovementLogDTO(
            id=log.id,
            applicator_id=log.applicator_id,
            serial_number=serial,
            from_location=log.from_location,
            to_location=log.to_location,
            timestamp=log.timestamp.isoformat(),
            user=username,
        )

    async def get_history(self, applicator_id: int) -> list[MovementLogDTO]:
        stmt = (
            select(MovementLogORM, ApplicatorORM.serial_number, UserORM.username)
            .outerjoin(ApplicatorORM, MovementLogORM.applicator_id == ApplicatorORM.id)
            .outerjoin(UserORM, MovementLogORM.user_id == UserORM.id)
            .where(MovementLogORM.applicator_id == applicator_id)
            .order_by(desc(MovementLogORM.timestamp), desc(MovementLogORM.id))
        )
        res = await self.session.execute(stmt)
        return [self._movement_dto(row[0], row[1], row[2]) for row in res.all()]

    async def list_recent_movements(self, limit: int) -> list[MovementLogDTO]:
        stmt = (
            select(MovementLogORM, ApplicatorORM.serial_number, UserORM.username)
            .outerjoin(ApplicatorORM, MovementLogORM.applicator_id == ApplicatorORM.id)
            .outerjoin(UserORM, MovementLogORM.user_id == UserORM.id)
            .order_by(desc(MovementLogORM.timestamp), desc(MovementLogORM.id))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [self._movement_dto(row[0], row[1], row[2]) for row in res.all()]

    async def list_blocked(self) -> list[BlockedApplicatorDTO]:
        zone_res = await self.session.execute(select(ZoneORM.id).where(ZoneORM.name == BLOCKED_ZONE_NAME))
        blocked_zone_id = zone_res.scalar_one_or_none()
        if blocked_zone_id is None:
            return []

        apps_res = await self.session.execute(
            select(ApplicatorORM).where(ApplicatorORM.current_zone_id == blocked_zone_id)
        )
        applicators = apps_res.scalars().all()

        result: list[BlockedApplicatorDTO] = []
        for app in applicators:
            log_res = await self.session.execute(
                select(BlockLogORM, UserORM.username)
                .outerjoin(UserORM, BlockLogORM.user_id == UserORM.id)
                .where(BlockLogORM.applicator_id == app.id)
                .order_by(desc(BlockLogORM.timestamp))
                .limit(1)
            )
            row = log_res.first()
            reason = row[0].reason if row else None
            blocked_at = row[0].timestamp.isoformat() if row else None
            blocked_by = row[1] if row else None

            result.append(
                BlockedApplicatorDTO(
                    id=app.id,
                    serial_number=app.serial_number,
                    reason=reason,
                    blocked_at=blocked_at,
                    blocked_by=blocked_by,
                )
            )
        return result
