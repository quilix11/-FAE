import typing
from collections.abc import AsyncGenerator

from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handlers import (
    BlockApplicatorHandler,
    Broadcaster,
    ChangeApplicatorStateHandler,
    CreateApplicatorHandler,
    CreateMachineHandler,
    CreateUserHandler,
    DeleteApplicatorHandler,
    DeleteMachineHandler,
    ScanApplicatorHandler,
    UnbindApplicatorHandler,
    UnblockApplicatorHandler,
)
from application.commands.login_handler import LoginHandler
from application.queries.handlers import (
    GetApplicatorHistoryHandler,
    GetDashboardHandler,
    ListApplicatorsHandler,
    ListBlockedApplicatorsHandler,
    ListMachinesHandler,
    ListMovementsHandler,
    ListZonesHandler,
)
from application.queries.interfaces import (
    ApplicatorQueryService,
    DashboardQueryService,
    MachineQueryService,
    ZoneQueryService,
)
from domain.interfaces import UnitOfWork
from infrastructure.database.session import get_session
from infrastructure.pubsub import broadcast
from infrastructure.queries.applicator_query import SQLAlchemyApplicatorQueryService
from infrastructure.queries.dashboard_query import SQLAlchemyDashboardQueryService
from infrastructure.queries.machine_query import SQLAlchemyMachineQueryService
from infrastructure.queries.zone_query import SQLAlchemyZoneQueryService
from infrastructure.repositories.repositories import SQLAlchemyUnitOfWork


class BroadcastAdapter(Broadcaster):
    """Adapter that wraps the broadcaster singleton behind the Broadcaster interface."""

    async def publish(self, channel: str, message: str) -> None:
        await broadcast.publish(channel, message)


class AppProvider(Provider):
    @provide(scope=Scope.SESSION)
    async def get_db_session(self) -> AsyncGenerator[AsyncSession, None]:
        async for session in get_session():
            yield session

    @provide(scope=Scope.REQUEST)
    async def get_uow(self, session: AsyncSession) -> UnitOfWork:
        return SQLAlchemyUnitOfWork(session)

    @provide(scope=Scope.REQUEST)
    async def get_broadcaster(self) -> Broadcaster:
        return BroadcastAdapter()

    @provide(scope=Scope.SESSION)
    async def get_dashboard_query_service(self, session: AsyncSession) -> DashboardQueryService:
        return SQLAlchemyDashboardQueryService(session)

    @provide(scope=Scope.REQUEST)
    async def get_machine_query_service(self, session: AsyncSession) -> MachineQueryService:
        return SQLAlchemyMachineQueryService(session)

    @provide(scope=Scope.REQUEST)
    async def get_zone_query_service(self, session: AsyncSession) -> ZoneQueryService:
        return SQLAlchemyZoneQueryService(session)

    @provide(scope=Scope.REQUEST)
    async def get_applicator_query_service(self, session: AsyncSession) -> ApplicatorQueryService:
        return SQLAlchemyApplicatorQueryService(session)

    @provide(scope=Scope.SESSION)
    async def get_dashboard_handler(self, query_service: DashboardQueryService) -> GetDashboardHandler:
        return GetDashboardHandler(query_service=query_service)

    @provide(scope=Scope.REQUEST)
    async def get_list_machines_handler(self, query_service: MachineQueryService) -> ListMachinesHandler:
        return ListMachinesHandler(query_service=query_service)

    @provide(scope=Scope.REQUEST)
    async def get_list_zones_handler(self, query_service: ZoneQueryService) -> ListZonesHandler:
        return ListZonesHandler(query_service=query_service)

    @provide(scope=Scope.REQUEST)
    async def get_list_applicators_handler(self, query_service: ApplicatorQueryService) -> ListApplicatorsHandler:
        return ListApplicatorsHandler(query_service=query_service)

    @provide(scope=Scope.REQUEST)
    async def get_list_blocked_handler(self, query_service: ApplicatorQueryService) -> ListBlockedApplicatorsHandler:
        return ListBlockedApplicatorsHandler(query_service=query_service)

    @provide(scope=Scope.REQUEST)
    async def get_applicator_history_handler(
        self, query_service: ApplicatorQueryService
    ) -> GetApplicatorHistoryHandler:
        return GetApplicatorHistoryHandler(query_service=query_service)

    @provide(scope=Scope.REQUEST)
    async def get_list_movements_handler(self, query_service: ApplicatorQueryService) -> ListMovementsHandler:
        return ListMovementsHandler(query_service=query_service)

    @provide(scope=Scope.REQUEST)
    async def get_scan_handler(
        self, uow: UnitOfWork, dashboard_handler: GetDashboardHandler, broadcaster: Broadcaster
    ) -> ScanApplicatorHandler:
        return ScanApplicatorHandler(uow=uow, dashboard_query=dashboard_handler, broadcaster=broadcaster)

    @provide(scope=Scope.REQUEST)
    async def get_change_state_handler(
        self, uow: UnitOfWork, dashboard_handler: GetDashboardHandler, broadcaster: Broadcaster
    ) -> ChangeApplicatorStateHandler:
        return ChangeApplicatorStateHandler(uow=uow, dashboard_query=dashboard_handler, broadcaster=broadcaster)

    @provide(scope=Scope.REQUEST)
    async def get_unbind_handler(
        self, uow: UnitOfWork, dashboard_handler: GetDashboardHandler, broadcaster: Broadcaster
    ) -> UnbindApplicatorHandler:
        return UnbindApplicatorHandler(uow=uow, dashboard_query=dashboard_handler, broadcaster=broadcaster)

    @provide(scope=Scope.REQUEST)
    async def get_block_handler(
        self, uow: UnitOfWork, dashboard_handler: GetDashboardHandler, broadcaster: Broadcaster
    ) -> BlockApplicatorHandler:
        return BlockApplicatorHandler(uow=uow, dashboard_query=dashboard_handler, broadcaster=broadcaster)

    @provide(scope=Scope.REQUEST)
    async def get_unblock_handler(self, uow: UnitOfWork, broadcaster: Broadcaster) -> UnblockApplicatorHandler:
        return UnblockApplicatorHandler(uow=uow, broadcaster=broadcaster)

    @provide(scope=Scope.REQUEST)
    async def get_create_machine_handler(self, uow: UnitOfWork, broadcaster: Broadcaster) -> CreateMachineHandler:
        return CreateMachineHandler(uow=uow, broadcaster=broadcaster)

    @provide(scope=Scope.REQUEST)
    async def get_create_applicator_handler(
        self, uow: UnitOfWork, dashboard_handler: GetDashboardHandler, broadcaster: Broadcaster
    ) -> CreateApplicatorHandler:
        return CreateApplicatorHandler(uow=uow, dashboard_query=dashboard_handler, broadcaster=broadcaster)

    @provide(scope=Scope.REQUEST)
    async def get_delete_machine_handler(self, uow: UnitOfWork, broadcaster: Broadcaster) -> DeleteMachineHandler:
        return DeleteMachineHandler(uow=uow, broadcaster=broadcaster)

    @provide(scope=Scope.REQUEST)
    async def get_delete_applicator_handler(
        self, uow: UnitOfWork, dashboard_handler: GetDashboardHandler, broadcaster: Broadcaster
    ) -> DeleteApplicatorHandler:
        return DeleteApplicatorHandler(uow=uow, dashboard_query=dashboard_handler, broadcaster=broadcaster)

    @provide(scope=Scope.REQUEST)
    async def get_login_handler(self, uow: UnitOfWork) -> LoginHandler:
        return LoginHandler(uow=uow)

    @provide(scope=Scope.REQUEST)
    async def get_create_user_handler(self, uow: UnitOfWork, broadcaster: Broadcaster) -> CreateUserHandler:
        return CreateUserHandler(uow=uow, broadcaster=broadcaster)



def setup_ioc(app: typing.Any) -> None:
    container = make_async_container(AppProvider())
    setup_dishka(container, app)
