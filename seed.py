import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.infrastructure.models.orm import Base, ZoneORM, MachineORM, ApplicatorORM, ApplicatorState

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://applicator_user:secretpassword@localhost:5432/applicator_db")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

async def seed():
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    async with session_maker() as session:
        # ------------------------------------------------------------------
        # Seed Zones
        # ------------------------------------------------------------------
        zone_service = ZoneORM(name="Service", max_capacity=100, max_in_use=0)
        zone_cutting = ZoneORM(name="Cutting", max_capacity=5, max_in_use=2)
        zone_crimping = ZoneORM(name="Crimping", max_capacity=3, max_in_use=1)
        zone_applicator_room = ZoneORM(name="Applicator Room", max_capacity=300, max_in_use=0)
        zone_blocked = ZoneORM(name="Blocked", max_capacity=50, max_in_use=0)
        zone_unused = ZoneORM(name="Unused", max_capacity=200, max_in_use=0)
        
        session.add_all([
            zone_service, zone_cutting, zone_crimping,
            zone_applicator_room, zone_blocked, zone_unused,
        ])
        await session.commit()
        
        # ------------------------------------------------------------------
        # Seed Machines
        # ------------------------------------------------------------------
        # Cutting zone machines (G-prefix)
        machine_g05 = MachineORM(hardware_code="G05", zone_id=zone_cutting.id)
        machine_g06 = MachineORM(hardware_code="G06", zone_id=zone_cutting.id)
        machine_g07 = MachineORM(hardware_code="G07", zone_id=zone_cutting.id)

        # Crimping zone machines (A-prefix)
        machine_a01 = MachineORM(hardware_code="A01", zone_id=zone_crimping.id)
        machine_a02 = MachineORM(hardware_code="A02", zone_id=zone_crimping.id)
        machine_a03 = MachineORM(hardware_code="A03", zone_id=zone_crimping.id)

        # Crimping zone machines (S-prefix)
        machine_s04 = MachineORM(hardware_code="S04", zone_id=zone_crimping.id)
        machine_s05 = MachineORM(hardware_code="S05", zone_id=zone_crimping.id)

        # Service zone machine
        machine_srv = MachineORM(hardware_code="SRV_01", zone_id=zone_service.id)

        # Applicator room machine (storage / staging)
        machine_ar01 = MachineORM(hardware_code="AR_01", zone_id=zone_applicator_room.id)

        session.add_all([
            machine_g05, machine_g06, machine_g07,
            machine_a01, machine_a02, machine_a03,
            machine_s04, machine_s05,
            machine_srv, machine_ar01,
        ])
        await session.commit()
        
        # ------------------------------------------------------------------
        # Seed Applicators
        # ------------------------------------------------------------------
        applicators = [
            # G05 – cutting
            ApplicatorORM(serial_number="APP-1001", current_machine_id=machine_g05.id, state=ApplicatorState.IN_USE),
            ApplicatorORM(serial_number="APP-1002", current_machine_id=machine_g05.id, state=ApplicatorState.ON_RACK),
            # G06 – cutting
            ApplicatorORM(serial_number="APP-1003", current_machine_id=machine_g06.id, state=ApplicatorState.IN_USE),
            ApplicatorORM(serial_number="APP-1004", current_machine_id=machine_g06.id, state=ApplicatorState.ON_RACK),
            # G07 – cutting
            ApplicatorORM(serial_number="APP-1005", current_machine_id=machine_g07.id, state=ApplicatorState.IN_USE),
            ApplicatorORM(serial_number="APP-1006", current_machine_id=machine_g07.id, state=ApplicatorState.ON_RACK),
            # A01 – crimping
            ApplicatorORM(serial_number="APP-3001", current_machine_id=machine_a01.id, state=ApplicatorState.IN_USE),
            # A02 – crimping
            ApplicatorORM(serial_number="APP-3002", current_machine_id=machine_a02.id, state=ApplicatorState.ON_RACK),
            # A03 – crimping
            ApplicatorORM(serial_number="APP-3003", current_machine_id=machine_a03.id, state=ApplicatorState.IN_USE),
            # S04 – crimping
            ApplicatorORM(serial_number="APP-2001", current_machine_id=machine_s04.id, state=ApplicatorState.IN_USE),
            ApplicatorORM(serial_number="APP-2002", current_machine_id=machine_s04.id, state=ApplicatorState.ON_RACK),
            # S05 – crimping
            ApplicatorORM(serial_number="APP-2003", current_machine_id=machine_s05.id, state=ApplicatorState.ON_RACK),
            # SRV_01 – service (state = none, not active)
            ApplicatorORM(serial_number="APP-9001", current_machine_id=machine_srv.id, state=ApplicatorState.NONE),
            ApplicatorORM(serial_number="APP-9002", current_machine_id=machine_srv.id, state=ApplicatorState.NONE),
            # AR_01 – applicator room (stored)
            ApplicatorORM(serial_number="APP-8001", current_machine_id=machine_ar01.id, state=ApplicatorState.NONE),
            ApplicatorORM(serial_number="APP-8002", current_machine_id=machine_ar01.id, state=ApplicatorState.NONE),
            ApplicatorORM(serial_number="APP-8003", current_machine_id=machine_ar01.id, state=ApplicatorState.NONE),
            # Unattached applicators (no machine)
            ApplicatorORM(serial_number="APP-0001", current_machine_id=None, state=ApplicatorState.NONE),
            ApplicatorORM(serial_number="APP-0002", current_machine_id=None, state=ApplicatorState.NONE),
        ]
        
        session.add_all(applicators)
        await session.commit()
        
        # ------------------------------------------------------------------
        # Seed default TECH_ADMIN User
        # ------------------------------------------------------------------
        from sqlalchemy import select
        from src.infrastructure.models.orm import UserORM
        from src.domain.entities import Role
        from src.infrastructure.auth import get_password_hash
        
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin")
        
        stmt = select(UserORM).where(UserORM.username == admin_username)
        result = await session.execute(stmt)
        admin_user = result.scalar_one_or_none()
        
        if not admin_user:
            admin_user = UserORM(
                username=admin_username,
                hashed_password=get_password_hash(admin_password),
                role=Role.TECH_ADMIN
            )
            session.add(admin_user)
            await session.commit()
            print(f"Created default admin user: {admin_username}")
        else:
            print(f"Admin user '{admin_username}' already exists.")

        operator_code = os.getenv("OPERATOR_CODE", "OP_001")
        operator_password = os.getenv("OPERATOR_PASSWORD", "operator")

        stmt_op = select(UserORM).where(UserORM.operator_code == operator_code)
        operator_user = (await session.execute(stmt_op)).scalar_one_or_none()

        if not operator_user:
            operator_user = UserORM(
                username="operator",
                hashed_password=get_password_hash(operator_password),
                role=Role.OPERATOR,
                operator_code=operator_code,
            )
            session.add(operator_user)
            await session.commit()
            print(f"Created default operator: code={operator_code}")
        else:
            print(f"Operator '{operator_code}' already exists.")
        
    print("Database seeded successfully!")
    print(f"  Zones:        6")
    print(f"  Machines:    10")
    print(f"  Applicators: {len(applicators)}")

    # Fix legacy rows: applicators on a machine but missing zone
    from sqlalchemy import text
    async with session_maker() as fix_session:
        await fix_session.execute(text("""
            UPDATE applicators SET current_zone_id = machines.zone_id
            FROM machines
            WHERE applicators.current_machine_id = machines.id
              AND applicators.current_zone_id IS NULL
        """))
        await fix_session.commit()
        print("Fixed applicators missing zone assignment.")

if __name__ == "__main__":
    asyncio.run(seed())
