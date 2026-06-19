from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from application.commands.handlers import (
    Broadcaster,
    ChangeApplicatorStateHandler,
    CreateUserHandler,
    ScanApplicatorHandler,
    UnbindApplicatorHandler,
)
from application.commands.login_handler import LoginHandler
from application.queries.dtos import DashboardDTO
from application.queries.handlers import GetDashboardHandler
from domain.entities import Applicator, ApplicatorState, Machine, Role, User, Zone
from domain.exceptions import AuthenticationError, EntityNotFoundError, InvalidStateError
from domain.interfaces import UnitOfWork
from infrastructure.auth import get_password_hash


@pytest.fixture
def mock_uow():
    uow = AsyncMock(spec=UnitOfWork)
    uow.machines = AsyncMock()
    uow.applicators = AsyncMock()
    uow.zones = AsyncMock()
    uow.movement_logs = AsyncMock()
    uow.users = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    return uow




@pytest.fixture
def mock_dashboard_query():
    query = AsyncMock(spec=GetDashboardHandler)
    query.execute.return_value = DashboardDTO(
        machine_id=1,
        hardware_code="HW1",
        zone_name="Zone 1",
        max_capacity=2,
        current_capacity=1,
        max_in_use=5,
        current_in_use=1,
        applicators=[]
    )
    return query


@pytest.fixture
def mock_broadcaster():
    return AsyncMock(spec=Broadcaster)


@pytest.mark.asyncio
async def test_scan_applicator_handler_not_found_raises(mock_uow, mock_dashboard_query, mock_broadcaster) -> None:
    handler = ScanApplicatorHandler(mock_uow, mock_dashboard_query, mock_broadcaster)

    machine = Machine(id=1, hardware_code="HW1", zone_id=1, max_capacity=2)
    mock_uow.machines.get_by_hardware_code.return_value = machine
    mock_uow.applicators.get_by_serial_number.return_value = None

    with pytest.raises(EntityNotFoundError):
        await handler.execute(serial_number="APP1", hardware_code="HW1", user_id=1)


@pytest.mark.asyncio
async def test_scan_applicator_handler_existing_applicator_success(
    mock_uow, mock_dashboard_query, mock_broadcaster
) -> None:
    handler = ScanApplicatorHandler(mock_uow, mock_dashboard_query, mock_broadcaster)

    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    machine = Machine(id=1, hardware_code="HW1", zone_id=1, max_capacity=2)
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=None, current_machine_id=None, state=ApplicatorState.NONE
    )

    mock_uow.machines.get_by_hardware_code.return_value = machine
    mock_uow.applicators.get_by_serial_number.return_value = applicator
    mock_uow.zones.get_by_id.return_value = zone
    mock_uow.machines.get_applicators_count.return_value = 0
    mock_uow.zones.get_in_use_count.return_value = 0

    await handler.execute(serial_number="APP1", hardware_code="HW1", user_id=1)

    assert mock_uow.machines.save.call_count == 1
    assert mock_uow.zones.save.call_count == 1
    assert mock_uow.applicators.save.call_count == 1
    assert mock_uow.movement_logs.add.call_count == 1
    assert mock_uow.commit.call_count == 1
    assert mock_broadcaster.publish.call_count == 1

    assert applicator.current_machine_id == machine.id
    assert applicator.current_zone_id == zone.id
    assert applicator.state == ApplicatorState.IN_USE


@pytest.mark.asyncio
async def test_change_state_handler(mock_uow, mock_dashboard_query, mock_broadcaster) -> None:
    handler = ChangeApplicatorStateHandler(mock_uow, mock_dashboard_query, mock_broadcaster)

    zone = Zone(id=1, name="Zone 1", max_capacity=10, max_in_use=5)
    machine = Machine(id=1, hardware_code="HW1", zone_id=1, max_capacity=2)
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=1, current_machine_id=1, state=ApplicatorState.IN_USE
    )

    mock_uow.applicators.get_by_id.return_value = applicator
    mock_uow.zones.get_by_id.return_value = zone
    mock_uow.zones.get_in_use_count.return_value = 1
    mock_uow.machines.get_by_id.return_value = machine

    await handler.execute(applicator_id=1, new_state=ApplicatorState.ON_RACK, user_id=1)

    assert applicator.state == ApplicatorState.ON_RACK
    assert mock_uow.applicators.save.call_count == 1
    assert mock_uow.zones.save.call_count == 1
    assert mock_uow.commit.call_count == 1
    assert mock_broadcaster.publish.call_count == 1


@pytest.mark.asyncio
async def test_unbind_applicator_handler(mock_uow, mock_dashboard_query, mock_broadcaster) -> None:
    handler = UnbindApplicatorHandler(mock_uow, mock_dashboard_query, mock_broadcaster)

    machine = Machine(id=1, hardware_code="HW1", zone_id=1, max_capacity=2)
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=1, current_machine_id=1, state=ApplicatorState.ON_RACK
    )

    mock_uow.applicators.get_by_id.return_value = applicator
    mock_uow.machines.get_by_id.return_value = machine

    await handler.execute(applicator_id=1, user_id=1)

    assert applicator.current_machine_id is None
    assert applicator.current_zone_id is None
    assert applicator.state == ApplicatorState.NONE
    assert mock_uow.applicators.save.call_count == 1
    assert mock_uow.machines.save.call_count == 1
    assert mock_uow.movement_logs.add.call_count == 1
    assert mock_uow.commit.call_count == 1
    assert mock_broadcaster.publish.call_count == 1


@pytest.mark.asyncio
async def test_unbind_already_unbound_raises(mock_uow, mock_dashboard_query, mock_broadcaster) -> None:
    handler = UnbindApplicatorHandler(mock_uow, mock_dashboard_query, mock_broadcaster)
    applicator = Applicator(
        id=1, serial_number="APP1", current_zone_id=None, current_machine_id=None, state=ApplicatorState.NONE
    )
    mock_uow.applicators.get_by_id.return_value = applicator

    with pytest.raises(InvalidStateError, match="already unbound"):
        await handler.execute(applicator_id=1, user_id=1)

@pytest.mark.asyncio
async def test_create_user_handler_success(mock_uow, mock_broadcaster) -> None:
    handler = CreateUserHandler(mock_uow, mock_broadcaster)

    await handler.execute(
        username="new_operator",
        password_hash="hashed_pw",
        role="Operator",
        operator_code="OP123"
    )

    assert mock_uow.users.create.call_count == 1
    mock_uow.users.create.assert_called_with(
        username="new_operator",
        hashed_password="hashed_pw",
        role="Operator",
        operator_code="OP123"
    )
    assert mock_uow.commit.call_count == 1
    assert mock_broadcaster.publish.call_count == 1
@pytest.mark.asyncio
async def test_login_handler_success_admin(mock_uow) -> None:
    handler = LoginHandler(mock_uow)

    hashed_pw = get_password_hash("test_pass")
    user = User(id=1, username="admin1", hashed_password=hashed_pw, role=Role.TECH_ADMIN)
    mock_uow.users.get_by_username.return_value = user

    result = await handler.execute(identifier="admin1", password="test_pass", login_type="username")

    assert mock_uow.users.get_by_username.call_count == 1
    assert "access_token" in result

@pytest.mark.asyncio
async def test_login_handler_success_operator(mock_uow) -> None:
    handler = LoginHandler(mock_uow)

    hashed_pw = get_password_hash("test_pass")
    user = User(id=2, username="op1", hashed_password=hashed_pw, role=Role.OPERATOR)
    mock_uow.users.get_by_operator_code.return_value = user

    result = await handler.execute(identifier="777", password="test_pass", login_type="operator_code")

    assert mock_uow.users.get_by_operator_code.call_count == 1
    assert "access_token" in result

@pytest.mark.asyncio
async def test_login_handler_invalid_password(mock_uow) -> None:
    handler = LoginHandler(mock_uow)

    hashed_pw = get_password_hash("test_pass")
    user = User(id=1, username="admin1", hashed_password=hashed_pw, role=Role.TECH_ADMIN)
    mock_uow.users.get_by_username.return_value = user

    with pytest.raises(AuthenticationError):
        await handler.execute(identifier="admin1", password="wrong_password", login_type="username")


@pytest.mark.asyncio
async def test_login_handler_user_not_found(mock_uow) -> None:
    handler = LoginHandler(mock_uow)
    mock_uow.users.get_by_username.return_value = None

    with pytest.raises(AuthenticationError):
        await handler.execute(identifier="admin1", password="test_pass", login_type="username")


@pytest.mark.asyncio
async def test_login_handler_operator_not_found(mock_uow) -> None:
    handler = LoginHandler(mock_uow)
    mock_uow.users.get_by_operator_code.return_value = None

    with pytest.raises(AuthenticationError):
        await handler.execute(identifier="invalid_op", password="test_pass", login_type="operator_code")


@pytest.mark.asyncio
async def test_login_handler_operator_invalid_password(mock_uow) -> None:
    handler = LoginHandler(mock_uow)

    hashed_pw = get_password_hash("test_pass")
    user = User(id=2, username="op1", hashed_password=hashed_pw, role=Role.OPERATOR, operator_code="OP123")
    mock_uow.users.get_by_operator_code.return_value = user

    with pytest.raises(AuthenticationError):
        await handler.execute(identifier="OP123", password="wrong_password", login_type="operator_code")
