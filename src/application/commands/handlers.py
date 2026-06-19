import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from application.queries.handlers import GetDashboardHandler
from domain.entities import Applicator, ApplicatorState, BlockLog, Machine, MovementLog, Role
from domain.exceptions import EntityNotFoundError, InvalidStateError
from domain.interfaces import UnitOfWork


class Broadcaster(ABC):
    """Abstract interface for publishing real-time updates."""

    @abstractmethod
    async def publish(self, channel: str, message: str) -> None:
        pass


async def publish_dashboard_update(
    dashboard_query: GetDashboardHandler,
    broadcaster: Broadcaster,
    hardware_code: str | None,
) -> None:
    if not hardware_code:
        return
    dto = await dashboard_query.execute(hardware_code)
    if dto:
        await broadcaster.publish(f"dashboard_updates_{hardware_code}", dto.model_dump_json())


def resolve_applicator_zone(applicator: Applicator, machine: Machine | None) -> None:
    """Ensure zone is set when applicator is bound to a machine."""
    if applicator.current_zone_id is None and machine is not None:
        applicator.current_zone_id = machine.zone_id


class ScanApplicatorHandler:
    """Handles scanning an applicator onto a machine, updating state and creating movement logs."""

    def __init__(self, uow: UnitOfWork, dashboard_query: GetDashboardHandler, broadcaster: Broadcaster) -> None:
        self.uow = uow
        self.dashboard_query = dashboard_query
        self.broadcaster = broadcaster

    async def execute(self, serial_number: str, hardware_code: str, user_id: int) -> None:
        async with self.uow:
            machine = await self.uow.machines.get_by_hardware_code(hardware_code)
            if not machine:
                raise EntityNotFoundError(f"Machine {hardware_code} not found.")

            applicator = await self.uow.applicators.get_by_serial_number(serial_number)
            if not applicator:
                raise EntityNotFoundError(f"Applicator {serial_number} not found. Must be explicitly created.")

            zone = await self.uow.zones.get_by_id(machine.zone_id)
            if not zone:
                raise EntityNotFoundError(f"Zone {machine.zone_id} not found.")

            machine_app_count = await self.uow.machines.get_applicators_count(machine.id)
            zone_in_use_count = await self.uow.zones.get_in_use_count(machine.zone_id)

            old_machine_id = applicator.current_machine_id

            # If already on this machine, just set to in_use. Else move.
            if applicator.current_machine_id != machine.id:
                applicator.move_to_machine(machine, zone, machine_app_count, zone_in_use_count)
                await self.uow.machines.save(machine)
            else:
                resolve_applicator_zone(applicator, machine)

            # Scanning means it's now in use
            if applicator.state != ApplicatorState.IN_USE:
                applicator.set_state(ApplicatorState.IN_USE, zone, zone_in_use_count)
                await self.uow.zones.save(zone)

            await self.uow.applicators.save(applicator)

            from_loc = f"Machine {old_machine_id}" if old_machine_id else "Service"
            to_loc = f"Machine {machine.id}"
            if old_machine_id != machine.id:
                log = MovementLog(
                    applicator_id=applicator.id,
                    user_id=user_id,
                    from_location=from_loc,
                    to_location=to_loc,
                    timestamp=datetime.now(timezone.utc),
                )
                await self.uow.movement_logs.add(log)

            await self.uow.commit()

        await publish_dashboard_update(self.dashboard_query, self.broadcaster, hardware_code)


class ChangeApplicatorStateHandler:
    """Handles state transitions for applicators (e.g., in_use <-> on_rack)."""

    def __init__(self, uow: UnitOfWork, dashboard_query: GetDashboardHandler, broadcaster: Broadcaster) -> None:
        self.uow = uow
        self.dashboard_query = dashboard_query
        self.broadcaster = broadcaster

    async def execute(self, applicator_id: int, new_state: ApplicatorState, user_id: int) -> None:
        async with self.uow:
            applicator = await self.uow.applicators.get_by_id(applicator_id)
            if not applicator:
                raise EntityNotFoundError(f"Applicator {applicator_id} not found.")

            if applicator.current_machine_id is None:
                raise InvalidStateError(f"Applicator {applicator_id} is not attached to any machine.")

            machine = await self.uow.machines.get_by_id(applicator.current_machine_id)
            if not machine:
                raise EntityNotFoundError(f"Machine {applicator.current_machine_id} not found.")

            resolve_applicator_zone(applicator, machine)

            if applicator.current_zone_id is None:
                raise InvalidStateError(f"Applicator {applicator_id} is not attached to any zone.")

            zone = await self.uow.zones.get_by_id(applicator.current_zone_id)
            if not zone:
                raise EntityNotFoundError(f"Zone {applicator.current_zone_id} not found.")

            zone_in_use_count = await self.uow.zones.get_in_use_count(applicator.current_zone_id)

            applicator.set_state(new_state, zone, zone_in_use_count)
            await self.uow.zones.save(zone)
            await self.uow.applicators.save(applicator)

            hardware_code = machine.hardware_code

            await self.uow.commit()

        if hardware_code:
            await publish_dashboard_update(self.dashboard_query, self.broadcaster, hardware_code)


class UnbindApplicatorHandler:
    """Handles explicit unbinding of an applicator from its current machine."""

    def __init__(self, uow: UnitOfWork, dashboard_query: GetDashboardHandler, broadcaster: Broadcaster) -> None:
        self.uow = uow
        self.dashboard_query = dashboard_query
        self.broadcaster = broadcaster

    async def execute(self, applicator_id: int, user_id: int) -> None:
        async with self.uow:
            applicator = await self.uow.applicators.get_by_id(applicator_id)
            if not applicator:
                raise EntityNotFoundError(f"Applicator {applicator_id} not found.")

            old_machine_id = applicator.current_machine_id
            if old_machine_id is None:
                raise InvalidStateError(
                    f"Applicator {applicator_id} is already unbound. Cannot unbind again.",
                )

            applicator.unbind()
            await self.uow.applicators.save(applicator)

            machine = await self.uow.machines.get_by_id(old_machine_id)
            hardware_code = machine.hardware_code if machine else None
            if machine:
                await self.uow.machines.save(machine)

            log = MovementLog(
                applicator_id=applicator.id,
                user_id=user_id,
                from_location=f"Machine {old_machine_id}",
                to_location="Service",
                timestamp=datetime.now(timezone.utc),
            )
            await self.uow.movement_logs.add(log)
            await self.uow.commit()

        if hardware_code:
            await publish_dashboard_update(self.dashboard_query, self.broadcaster, hardware_code)


BLOCKED_ZONE_NAME = "Blocked"


class BlockApplicatorHandler:
    """Blocks an applicator (e.g. defective), moving it to the Blocked zone and logging the reason."""

    def __init__(self, uow: UnitOfWork, dashboard_query: GetDashboardHandler, broadcaster: Broadcaster) -> None:
        self.uow = uow
        self.dashboard_query = dashboard_query
        self.broadcaster = broadcaster

    async def execute(self, applicator_id: int, reason: str, user_id: int) -> None:
        hardware_code: str | None = None
        async with self.uow:
            applicator = await self.uow.applicators.get_by_id(applicator_id)
            if not applicator:
                raise EntityNotFoundError(f"Applicator {applicator_id} not found.")

            blocked_zone = await self.uow.zones.get_by_name(BLOCKED_ZONE_NAME)
            if not blocked_zone:
                raise EntityNotFoundError(f"'{BLOCKED_ZONE_NAME}' zone is not configured.")

            old_machine_id = applicator.current_machine_id
            if old_machine_id is not None:
                machine = await self.uow.machines.get_by_id(old_machine_id)
                hardware_code = machine.hardware_code if machine else None

            applicator.block(blocked_zone.id)
            await self.uow.applicators.save(applicator)

            await self.uow.block_logs.add(
                BlockLog(
                    applicator_id=applicator.id,
                    user_id=user_id,
                    reason=reason,
                    timestamp=datetime.now(timezone.utc),
                )
            )
            if old_machine_id is not None:
                await self.uow.movement_logs.add(
                    MovementLog(
                        applicator_id=applicator.id,
                        user_id=user_id,
                        from_location=f"Machine {old_machine_id}",
                        to_location=BLOCKED_ZONE_NAME,
                        timestamp=datetime.now(timezone.utc),
                    )
                )
            await self.uow.commit()

        await self.broadcaster.publish(
            "global_inventory", json.dumps({"event": "applicator_blocked", "applicator_id": applicator_id})
        )
        await publish_dashboard_update(self.dashboard_query, self.broadcaster, hardware_code)


class UnblockApplicatorHandler:
    """Unblocks an applicator, returning it to Service (unbound)."""

    def __init__(self, uow: UnitOfWork, broadcaster: Broadcaster) -> None:
        self.uow = uow
        self.broadcaster = broadcaster

    async def execute(self, applicator_id: int, user_id: int) -> None:
        async with self.uow:
            applicator = await self.uow.applicators.get_by_id(applicator_id)
            if not applicator:
                raise EntityNotFoundError(f"Applicator {applicator_id} not found.")

            blocked_zone = await self.uow.zones.get_by_name(BLOCKED_ZONE_NAME)
            if not blocked_zone or applicator.current_zone_id != blocked_zone.id:
                raise InvalidStateError(f"Applicator {applicator_id} is not blocked.")

            applicator.unbind()
            await self.uow.applicators.save(applicator)
            await self.uow.movement_logs.add(
                MovementLog(
                    applicator_id=applicator.id,
                    user_id=user_id,
                    from_location=BLOCKED_ZONE_NAME,
                    to_location="Service",
                    timestamp=datetime.now(timezone.utc),
                )
            )
            await self.uow.commit()

        await self.broadcaster.publish(
            "global_inventory", json.dumps({"event": "applicator_unblocked", "applicator_id": applicator_id})
        )


class CreateMachineHandler:
    """Creates a new machine in a specified zone."""

    def __init__(self, uow: UnitOfWork, broadcaster: Broadcaster) -> None:
        self.uow = uow
        self.broadcaster = broadcaster

    async def execute(self, hardware_code: str, zone_id: int) -> None:
        async with self.uow:
            zone = await self.uow.zones.get_by_id(zone_id)
            if not zone:
                raise EntityNotFoundError(f"Zone {zone_id} not found.")
            await self.uow.machines.create(hardware_code=hardware_code, zone_id=zone_id)
            await self.uow.commit()

        await self.broadcaster.publish(
            "global_inventory", json.dumps({"event": "machine_created", "hardware_code": hardware_code})
        )


class CreateApplicatorHandler:
    """Creates a new applicator, optionally bound to a machine."""

    def __init__(self, uow: UnitOfWork, dashboard_query: GetDashboardHandler, broadcaster: Broadcaster) -> None:
        self.uow = uow
        self.dashboard_query = dashboard_query
        self.broadcaster = broadcaster

    async def execute(self, serial_number: str, machine_id: int | None, state: ApplicatorState) -> None:
        hardware_code: str | None = None
        async with self.uow:
            await self.uow.applicators.create(
                serial_number=serial_number,
                machine_id=machine_id,
                state=state,
            )
            if machine_id is not None:
                machine = await self.uow.machines.get_by_id(machine_id)
                if machine:
                    hardware_code = machine.hardware_code
            await self.uow.commit()

        await self.broadcaster.publish(
            "global_inventory", json.dumps({"event": "applicator_created", "serial_number": serial_number})
        )
        await publish_dashboard_update(self.dashboard_query, self.broadcaster, hardware_code)


class DeleteMachineHandler:
    """Deletes a machine by ID, unbinding any attached applicators first."""

    def __init__(self, uow: UnitOfWork, broadcaster: Broadcaster) -> None:
        self.uow = uow
        self.broadcaster = broadcaster

    async def execute(self, machine_id: int) -> None:
        async with self.uow:
            machine = await self.uow.machines.get_by_id(machine_id)
            if not machine:
                raise EntityNotFoundError(f"Machine {machine_id} not found.")

            attached = await self.uow.applicators.get_by_machine_id(machine_id)
            for applicator in attached:
                applicator.unbind()
                await self.uow.applicators.save(applicator)

            await self.uow.machines.delete(machine_id)
            await self.uow.commit()

        await self.broadcaster.publish(
            "global_inventory", json.dumps({"event": "machine_deleted", "machine_id": machine_id})
        )


class DeleteApplicatorHandler:
    """Deletes an applicator by ID."""

    def __init__(self, uow: UnitOfWork, dashboard_query: GetDashboardHandler, broadcaster: Broadcaster) -> None:
        self.uow = uow
        self.dashboard_query = dashboard_query
        self.broadcaster = broadcaster

    async def execute(self, applicator_id: int) -> None:
        hardware_code: str | None = None
        async with self.uow:
            applicator = await self.uow.applicators.get_by_id(applicator_id)
            if not applicator:
                raise EntityNotFoundError(f"Applicator {applicator_id} not found.")
            if applicator.current_machine_id is not None:
                machine = await self.uow.machines.get_by_id(applicator.current_machine_id)
                if machine:
                    hardware_code = machine.hardware_code
            await self.uow.applicators.delete(applicator_id)
            await self.uow.commit()

        await self.broadcaster.publish(
            "global_inventory", json.dumps({"event": "applicator_deleted", "applicator_id": applicator_id})
        )
        await publish_dashboard_update(self.dashboard_query, self.broadcaster, hardware_code)


class CreateUserHandler:
    """Creates a new user (operator/admin)."""

    def __init__(self, uow: UnitOfWork, broadcaster: Broadcaster) -> None:
        self.uow = uow
        self.broadcaster = broadcaster

    async def execute(
        self,
        username: str,
        password_hash: str,
        role: Role,
        operator_code: str | None
    ) -> None:
        async with self.uow:
            await self.uow.users.create(
                username=username,
                hashed_password=password_hash,
                role=role,
                operator_code=operator_code
            )
            await self.uow.commit()

        # Emit an event if needed
        await self.broadcaster.publish(
            "global_inventory", json.dumps({"event": "user_created", "username": username})
        )

__all__ = [
    "BlockApplicatorHandler",
    "Broadcaster",
    "ChangeApplicatorStateHandler",
    "CreateApplicatorHandler",
    "CreateMachineHandler",
    "CreateUserHandler",
    "DeleteApplicatorHandler",
    "DeleteMachineHandler",
    "ScanApplicatorHandler",
    "UnbindApplicatorHandler",
    "UnblockApplicatorHandler",
]
