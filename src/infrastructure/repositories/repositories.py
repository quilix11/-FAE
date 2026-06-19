from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.entities import Applicator, ApplicatorState, BlockLog, Machine, MovementLog, Role, User, Zone
from domain.exceptions import ConcurrencyError, DuplicateEntityError
from domain.interfaces import (
    ApplicatorRepository,
    BlockLogRepository,
    MachineRepository,
    MovementLogRepository,
    UnitOfWork,
    UserRepository,
    ZoneRepository,
)
from infrastructure.models.orm import ApplicatorORM, BlockLogORM, MachineORM, MovementLogORM, UserORM, ZoneORM


class SQLAlchemyUserRepository(UserRepository):
    """SQLAlchemy implementation of UserRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_domain(self, orm: UserORM) -> User:
        return User(
            id=orm.id,
            username=orm.username,
            hashed_password=orm.hashed_password,
            role=orm.role,
            operator_code=orm.operator_code,
        )

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(UserORM).where(UserORM.id == user_id)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(UserORM).where(UserORM.username == username)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_by_operator_code(self, operator_code: str) -> User | None:
        stmt = select(UserORM).where(UserORM.operator_code == operator_code)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def create(self, username: str, hashed_password: str, role: Role, operator_code: str | None) -> User:
        new_user = UserORM(
            username=username,
            hashed_password=hashed_password,
            role=role,
            operator_code=operator_code
        )
        self.session.add(new_user)
        try:
            await self.session.flush()
        except IntegrityError as e:
            raise DuplicateEntityError(
                f"User with username '{username}' or operator_code '{operator_code}' already exists."
            ) from e
        return self._to_domain(new_user)


class SQLAlchemyZoneRepository(ZoneRepository):
    """SQLAlchemy implementation of ZoneRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_domain(self, orm: ZoneORM) -> Zone:
        return Zone(
            id=orm.id, name=orm.name, max_capacity=orm.max_capacity, max_in_use=orm.max_in_use, version=orm.version_id
        )

    async def get_by_id(self, zone_id: int) -> Zone | None:
        stmt = select(ZoneORM).where(ZoneORM.id == zone_id)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_by_name(self, name: str) -> Zone | None:
        stmt = select(ZoneORM).where(ZoneORM.name == name)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_in_use_count(self, zone_id: int) -> int:
        stmt = select(func.count(ApplicatorORM.id)).where(
            ApplicatorORM.current_zone_id == zone_id,
            ApplicatorORM.state == ApplicatorState.IN_USE,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one()

    async def save(self, zone: Zone) -> None:
        stmt = select(ZoneORM).where(ZoneORM.id == zone.id)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        if orm:
            if orm.version_id != zone.version:
                raise ConcurrencyError("Version mismatch — the data has been modified by another request.")
            orm.name = zone.name
            orm.max_capacity = zone.max_capacity
            orm.max_in_use = zone.max_in_use
        await self.session.flush()

    async def get_all(self) -> list[Zone]:
        stmt = select(ZoneORM)
        res = await self.session.execute(stmt)
        return [self._to_domain(orm) for orm in res.scalars().all()]


class SQLAlchemyMachineRepository(MachineRepository):
    """SQLAlchemy implementation of MachineRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_domain(self, orm: MachineORM) -> Machine:
        return Machine(
            id=orm.id,
            hardware_code=orm.hardware_code,
            zone_id=orm.zone_id,
            max_capacity=orm.max_capacity,
            version=orm.version_id,
        )

    async def get_by_id(self, machine_id: int) -> Machine | None:
        stmt = select(MachineORM).where(MachineORM.id == machine_id)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_by_hardware_code(self, hardware_code: str) -> Machine | None:
        stmt = select(MachineORM).where(MachineORM.hardware_code == hardware_code)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_applicators_count(self, machine_id: int) -> int:
        stmt = select(func.count(ApplicatorORM.id)).where(ApplicatorORM.current_machine_id == machine_id)
        res = await self.session.execute(stmt)
        return res.scalar_one()

    async def save(self, machine: Machine) -> None:
        stmt = select(MachineORM).where(MachineORM.id == machine.id)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        if orm:
            if orm.version_id != machine.version:
                raise ConcurrencyError("Version mismatch — the data has been modified by another request.")
            orm.hardware_code = machine.hardware_code
            orm.zone_id = machine.zone_id
            orm.max_capacity = machine.max_capacity
        await self.session.flush()

    async def create(self, hardware_code: str, zone_id: int) -> Machine:
        """Create a new machine in the database."""
        new_machine = MachineORM(hardware_code=hardware_code, zone_id=zone_id)
        self.session.add(new_machine)
        try:
            await self.session.flush()
        except IntegrityError as e:
            raise DuplicateEntityError(f"Machine with hardware code '{hardware_code}' already exists.") from e
        return self._to_domain(new_machine)

    async def delete(self, machine_id: int) -> None:
        """Delete a machine by ID."""
        stmt = select(MachineORM).where(MachineORM.id == machine_id)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        if orm:
            await self.session.delete(orm)
            await self.session.flush()

    async def get_all(self) -> list[Machine]:
        """Retrieve all machines."""
        stmt = select(MachineORM).options(selectinload(MachineORM.zone))
        res = await self.session.execute(stmt)
        return [self._to_domain(orm) for orm in res.scalars().all()]


class SQLAlchemyApplicatorRepository(ApplicatorRepository):
    """SQLAlchemy implementation of ApplicatorRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_domain(self, orm: ApplicatorORM) -> Applicator:
        return Applicator(
            id=orm.id,
            serial_number=orm.serial_number,
            current_zone_id=orm.current_zone_id,
            current_machine_id=orm.current_machine_id,
            state=orm.state,
        )

    async def get_by_id(self, applicator_id: int) -> Applicator | None:
        stmt = select(ApplicatorORM).where(ApplicatorORM.id == applicator_id)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_by_serial_number(self, serial_number: str) -> Applicator | None:
        stmt = select(ApplicatorORM).where(ApplicatorORM.serial_number == serial_number)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_by_machine_id(self, machine_id: int) -> list[Applicator]:
        stmt = select(ApplicatorORM).where(ApplicatorORM.current_machine_id == machine_id)
        res = await self.session.execute(stmt)
        return [self._to_domain(orm) for orm in res.scalars().all()]

    async def save(self, applicator: Applicator) -> None:
        """Update an existing applicator or create a new one."""
        if applicator.id is not None:
            stmt = select(ApplicatorORM).where(ApplicatorORM.id == applicator.id)
            res = await self.session.execute(stmt)
            orm = res.scalar_one_or_none()
            if orm:
                orm.current_zone_id = applicator.current_zone_id
                orm.current_machine_id = applicator.current_machine_id
                orm.state = applicator.state
        else:
            new_app = ApplicatorORM(
                serial_number=applicator.serial_number,
                current_zone_id=applicator.current_zone_id,
                current_machine_id=applicator.current_machine_id,
                state=applicator.state,
            )
            self.session.add(new_app)
            await self.session.flush()
            applicator.id = new_app.id

    async def create(self, serial_number: str, machine_id: int | None, state: ApplicatorState) -> Applicator:
        """Create a new applicator in the database."""
        zone_id: int | None = None
        if machine_id is not None:
            stmt = select(MachineORM).where(MachineORM.id == machine_id)
            res = await self.session.execute(stmt)
            machine_orm = res.scalar_one_or_none()
            if machine_orm:
                zone_id = machine_orm.zone_id

        new_app = ApplicatorORM(
            serial_number=serial_number,
            current_zone_id=zone_id,
            current_machine_id=machine_id,
            state=state,
        )
        self.session.add(new_app)
        try:
            await self.session.flush()
        except IntegrityError as e:
            raise DuplicateEntityError(f"Applicator with serial number '{serial_number}' already exists.") from e
        return self._to_domain(new_app)

    async def delete(self, applicator_id: int) -> None:
        """Delete an applicator by ID."""
        stmt = select(ApplicatorORM).where(ApplicatorORM.id == applicator_id)
        res = await self.session.execute(stmt)
        orm = res.scalar_one_or_none()
        if orm:
            await self.session.delete(orm)
            await self.session.flush()


class SQLAlchemyMovementLogRepository(MovementLogRepository):
    """SQLAlchemy implementation of MovementLogRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, log: MovementLog) -> None:
        orm = MovementLogORM(
            applicator_id=log.applicator_id,
            user_id=log.user_id,
            from_location=log.from_location,
            to_location=log.to_location,
            timestamp=log.timestamp,
        )
        self.session.add(orm)
        await self.session.flush()
        log.id = orm.id


class SQLAlchemyBlockLogRepository(BlockLogRepository):
    """SQLAlchemy implementation of BlockLogRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, log: BlockLog) -> None:
        orm = BlockLogORM(
            applicator_id=log.applicator_id,
            user_id=log.user_id,
            reason=log.reason,
            timestamp=log.timestamp,
        )
        self.session.add(orm)
        await self.session.flush()
        log.id = orm.id


class SQLAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of UnitOfWork."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = SQLAlchemyUserRepository(session)
        self.zones = SQLAlchemyZoneRepository(session)
        self.machines = SQLAlchemyMachineRepository(session)
        self.applicators = SQLAlchemyApplicatorRepository(session)
        self.movement_logs = SQLAlchemyMovementLogRepository(session)
        self.block_logs = SQLAlchemyBlockLogRepository(session)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
