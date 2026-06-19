from datetime import datetime, timezone

import pytest

from domain.entities import Applicator, ApplicatorState, BlockLog, Machine, MovementLog, Role, User, Zone
from domain.exceptions import CapacityExceededError, InvalidStateError
from domain.interfaces import UnitOfWork


def test_applicator_move_to_machine_success() -> None:
    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    machine = Machine(id=1, hardware_code="HW1", zone_id=1, max_capacity=2)
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=None, current_machine_id=None, state=ApplicatorState.NONE
    )

    applicator.move_to_machine(machine, zone, current_machine_applicators=0, target_zone_in_use=0)

    assert applicator.current_machine_id == machine.id
    assert applicator.current_zone_id == zone.id


def test_applicator_move_to_machine_already_bound() -> None:
    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    Machine(id=1, hardware_code="HW1", zone_id=1, max_capacity=2)
    machine2 = Machine(id=2, hardware_code="HW2", zone_id=1, max_capacity=2)

    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=1, current_machine_id=1, state=ApplicatorState.ON_RACK
    )

    with pytest.raises(InvalidStateError, match="is already bound to a machine"):
        applicator.move_to_machine(machine2, zone, current_machine_applicators=0, target_zone_in_use=0)


def test_applicator_move_to_machine_same_machine_ok() -> None:
    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    machine1 = Machine(id=1, hardware_code="HW1", zone_id=1, max_capacity=2)

    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=1, current_machine_id=1, state=ApplicatorState.ON_RACK
    )

    # Moving to same machine should not raise InvalidStateError
    applicator.move_to_machine(machine1, zone, current_machine_applicators=1, target_zone_in_use=0)
    assert applicator.current_machine_id == 1


def test_applicator_move_to_machine_capacity_exceeded() -> None:
    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    machine = Machine(id=1, hardware_code="HW1", zone_id=1, max_capacity=2)
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=None, current_machine_id=None, state=ApplicatorState.NONE
    )

    with pytest.raises(CapacityExceededError, match="reached its capacity"):
        applicator.move_to_machine(machine, zone, current_machine_applicators=2, target_zone_in_use=0)


def test_applicator_set_state_in_use_success() -> None:
    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=1, current_machine_id=1, state=ApplicatorState.ON_RACK
    )

    applicator.set_state(ApplicatorState.IN_USE, zone, target_zone_in_use_count=4)
    assert applicator.state == ApplicatorState.IN_USE


def test_applicator_set_state_in_use_capacity_exceeded() -> None:
    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=1, current_machine_id=1, state=ApplicatorState.ON_RACK
    )

    with pytest.raises(CapacityExceededError, match="reached its in_use limit"):
        applicator.set_state(ApplicatorState.IN_USE, zone, target_zone_in_use_count=5)


def test_applicator_set_state_already_in_use() -> None:
    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=1, current_machine_id=1, state=ApplicatorState.IN_USE
    )

    # Should not raise exception even if zone is full
    applicator.set_state(ApplicatorState.IN_USE, zone, target_zone_in_use_count=5)
    assert applicator.state == ApplicatorState.IN_USE


def test_applicator_unbind() -> None:
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=1, current_machine_id=1, state=ApplicatorState.IN_USE
    )
    applicator.unbind()

    assert applicator.current_machine_id is None
    assert applicator.current_zone_id is None
    assert applicator.state == ApplicatorState.NONE


def test_user_creation() -> None:
    dummy_hash = "dummy_hash"
    user = User(id=1, username="test", hashed_password=dummy_hash, role=Role.OPERATOR)
    assert user.role == Role.OPERATOR


def test_movement_log_creation() -> None:
    log = MovementLog(
        applicator_id=1,
        user_id=1,
        from_location="A",
        to_location="B",
        timestamp=datetime.now(timezone.utc)
    )
    assert log.from_location == "A"
    assert log.id is None


def test_block_log_creation() -> None:
    log = BlockLog(applicator_id=1, user_id=1, reason="Broken", timestamp=datetime.now(timezone.utc))
    assert log.reason == "Broken"
    assert log.id is None


@pytest.mark.asyncio
async def test_unit_of_work_context_manager() -> None:
    class DummyUoW(UnitOfWork):
        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

    uow = DummyUoW()
    async with uow as u:
        assert u is uow


def test_applicator_move_to_same_machine_full() -> None:
    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    machine1 = Machine(id=1, hardware_code="HW1", zone_id=1, max_capacity=1)

    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=1, current_machine_id=1, state=ApplicatorState.ON_RACK
    )

    # Moving to same machine should not raise CapacityExceededError even if full
    applicator.move_to_machine(machine1, zone, current_machine_applicators=1, target_zone_in_use=0)
    assert applicator.current_machine_id == 1


def test_applicator_move_to_machine_mismatch_zone() -> None:
    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    machine = Machine(id=1, hardware_code="HW1", zone_id=2, max_capacity=2)
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=None, current_machine_id=None, state=ApplicatorState.NONE
    )

    with pytest.raises(InvalidStateError, match=r"Target machine does not belong to the target zone\."):
        applicator.move_to_machine(machine, zone, current_machine_applicators=0, target_zone_in_use=0)

def test_user_creation_with_operator_code() -> None:
    dummy_hash = "dummy_hash"
    user = User(id=2, username="test_op", hashed_password=dummy_hash, role=Role.OPERATOR, operator_code="OP123")
    assert user.role == Role.OPERATOR
    assert user.operator_code == "OP123"
