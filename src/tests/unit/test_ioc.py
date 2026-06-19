from unittest.mock import AsyncMock

import pytest
from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handlers import (
    ChangeApplicatorStateHandler,
    CreateApplicatorHandler,
    CreateMachineHandler,
    DeleteApplicatorHandler,
    DeleteMachineHandler,
    ScanApplicatorHandler,
    UnbindApplicatorHandler,
)
from application.commands.login_handler import LoginHandler
from application.queries.handlers import GetDashboardHandler, ListMachinesHandler, ListZonesHandler
from domain.interfaces import UnitOfWork
from infrastructure.ioc import AppProvider


@pytest.mark.asyncio
async def test_dishka_container_resolves_all_dependencies() -> None:
    # Arrange
    provider = AppProvider()

    class TestDBProvider(Provider):
        @provide(scope=Scope.SESSION)
        async def get_db_session(self) -> AsyncSession:
            return AsyncMock(spec=AsyncSession)

    container = make_async_container(provider, TestDBProvider())

    async with container() as request_container:
        # Act & Assert
        uow = await request_container.get(UnitOfWork)
        assert uow is not None

        scan_handler = await request_container.get(ScanApplicatorHandler)
        assert scan_handler is not None
        assert isinstance(scan_handler, ScanApplicatorHandler)

        change_state_handler = await request_container.get(ChangeApplicatorStateHandler)
        assert change_state_handler is not None
        assert isinstance(change_state_handler, ChangeApplicatorStateHandler)

        unbind_handler = await request_container.get(UnbindApplicatorHandler)
        assert unbind_handler is not None
        assert isinstance(unbind_handler, UnbindApplicatorHandler)

        dashboard_handler = await request_container.get(GetDashboardHandler)
        assert dashboard_handler is not None
        assert isinstance(dashboard_handler, GetDashboardHandler)

        create_machine = await request_container.get(CreateMachineHandler)
        assert isinstance(create_machine, CreateMachineHandler)

        create_applicator = await request_container.get(CreateApplicatorHandler)
        assert isinstance(create_applicator, CreateApplicatorHandler)

        delete_machine = await request_container.get(DeleteMachineHandler)
        assert isinstance(delete_machine, DeleteMachineHandler)

        delete_applicator = await request_container.get(DeleteApplicatorHandler)
        assert isinstance(delete_applicator, DeleteApplicatorHandler)

        login_handler = await request_container.get(LoginHandler)
        assert isinstance(login_handler, LoginHandler)

        list_machines = await request_container.get(ListMachinesHandler)
        assert isinstance(list_machines, ListMachinesHandler)

        list_zones = await request_container.get(ListZonesHandler)
        assert isinstance(list_zones, ListZonesHandler)
