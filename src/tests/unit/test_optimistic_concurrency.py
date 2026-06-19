import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from domain.exceptions import ConcurrencyError
from infrastructure.models.orm import Base, MachineORM, ZoneORM
from infrastructure.repositories.repositories import SQLAlchemyUnitOfWork


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_optimistic_concurrency_zone_update(session_factory) -> None:
    async with session_factory() as session:
        zone = ZoneORM(name="Zone 1", max_capacity=10, max_in_use=5)
        session.add(zone)
        await session.commit()
        zone_id = zone.id

    # Simulate two concurrent sessions reading the same zone
    async with session_factory() as s1, session_factory() as s2:
        uow1 = SQLAlchemyUnitOfWork(s1)
        uow2 = SQLAlchemyUnitOfWork(s2)

        zone1 = await uow1.zones.get_by_id(zone_id)
        zone2 = await uow2.zones.get_by_id(zone_id)

        assert zone1.version == 1
        assert zone2.version == 1

        # User 1 updates
        zone1.max_capacity += 1
        await uow1.zones.save(zone1)
        await uow1.commit()

        # User 2 updates (should fail)
        zone2.max_capacity += 1
        with pytest.raises(ConcurrencyError):
            await uow2.zones.save(zone2)


@pytest.mark.asyncio
async def test_optimistic_concurrency_machine_update(session_factory) -> None:
    async with session_factory() as session:
        zone = ZoneORM(name="Zone 1", max_capacity=10, max_in_use=5)
        session.add(zone)
        await session.flush()
        machine = MachineORM(hardware_code="HW1", zone_id=zone.id, max_capacity=5)
        session.add(machine)
        await session.commit()
        machine_id = machine.id

    # Simulate two concurrent sessions reading the same machine
    async with session_factory() as s1, session_factory() as s2:
        uow1 = SQLAlchemyUnitOfWork(s1)
        uow2 = SQLAlchemyUnitOfWork(s2)

        machine1 = await uow1.machines.get_by_id(machine_id)
        machine2 = await uow2.machines.get_by_id(machine_id)

        assert machine1.version == 1
        assert machine2.version == 1

        # User 1 updates
        machine1.max_capacity += 1
        await uow1.machines.save(machine1)
        await uow1.commit()

        # User 2 updates (should fail)
        machine2.max_capacity += 1
        with pytest.raises(ConcurrencyError):
            await uow2.machines.save(machine2)
