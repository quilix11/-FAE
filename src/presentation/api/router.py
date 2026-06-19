import typing

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Path,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm

from application.commands.handlers import (
    BlockApplicatorHandler,
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
from application.queries.dtos import (
    ApplicatorListItemDTO,
    BlockedApplicatorDTO,
    DashboardDTO,
    MachineDTO,
    MovementLogDTO,
    ZoneDTO,
)
from application.queries.handlers import (
    GetApplicatorHistoryHandler,
    GetDashboardHandler,
    ListApplicatorsHandler,
    ListBlockedApplicatorsHandler,
    ListMachinesHandler,
    ListMovementsHandler,
    ListZonesHandler,
)
from domain.entities import Role
from infrastructure.auth import get_current_user_payload, get_password_hash, get_ws_user_payload
from infrastructure.pubsub import broadcast
from presentation.api.schemas import (
    ApplicatorCreateRequest,
    BlockRequest,
    MachineCreateRequest,
    ScanRequest,
    StateUpdateRequest,
    UserCreateRequest,
)

router = APIRouter()

def require_role_flexible(allowed_roles: list[Role]) -> typing.Callable[[dict[str, typing.Any]], dict[str, typing.Any]]:
    def checker(payload: dict[str, typing.Any] = Depends(get_current_user_payload)) -> dict[str, typing.Any]:
        if Role(payload["role"]) not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return payload

    return checker

@router.post("/auth/login")
@inject
async def login(
    form_data: typing.Annotated[OAuth2PasswordRequestForm, Depends()],
    handler: FromDishka[LoginHandler],
    login_type: typing.Annotated[str, Form()] = "username",
) -> dict[str, str]:
    return await handler.execute(form_data.username, form_data.password, login_type)

@router.get("/api/dashboard/{hardware_code}")
@inject
async def get_dashboard(
    hardware_code: str,
    handler: FromDishka[GetDashboardHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(get_current_user_payload)],
) -> DashboardDTO:
    dto = await handler.execute(hardware_code)
    if not dto:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return dto

@router.websocket("/api/ws/dashboard/{hardware_code}")
@inject
async def websocket_dashboard(
    websocket: WebSocket,
    hardware_code: str,
    handler: FromDishka[GetDashboardHandler],
) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        await get_ws_user_payload(token)
    except WebSocketException as e:
        await websocket.close(code=e.code, reason=e.reason)
        return

    await websocket.accept()


    try:
        # Initial send
        dto = await handler.execute(hardware_code)
        if dto:
            await websocket.send_json(dto.model_dump())

        subscriber = broadcast.subscribe(f"dashboard_updates_{hardware_code}")
        async with subscriber as sub:
            if sub is not None:
                async for event in typing.cast("typing.AsyncGenerator[typing.Any, None]", sub):
                    if event is not None:
                        await websocket.send_text(event.message)
    except WebSocketDisconnect:
        pass


@router.websocket("/api/ws/inventory")
async def websocket_inventory(
    websocket: WebSocket,
) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        await get_ws_user_payload(token)
    except WebSocketException as e:
        await websocket.close(code=e.code, reason=e.reason)
        return

    await websocket.accept()

    try:
        subscriber = broadcast.subscribe("global_inventory")
        async with subscriber as sub:
            if sub is not None:
                async for event in typing.cast("typing.AsyncGenerator[typing.Any, None]", sub):
                    if event is not None:
                        await websocket.send_text(event.message)
    except WebSocketDisconnect:
        pass


@router.post("/api/scan", status_code=status.HTTP_200_OK)
@inject
async def scan_applicator(
    request: ScanRequest,
    handler: FromDishka[ScanApplicatorHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(get_current_user_payload)],
) -> dict[str, str]:
    await handler.execute(request.serial_number, request.hardware_code, typing.cast("int", user_payload["user_id"]))
    return {"status": "success", "message": "Applicator scanned successfully"}


@router.patch("/api/applicators/{id}/state", status_code=status.HTTP_200_OK)
@inject
async def change_applicator_state(
    request: StateUpdateRequest,
    handler: FromDishka[ChangeApplicatorStateHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(get_current_user_payload)],
    item_id: typing.Annotated[int, Path(alias="id")],
) -> dict[str, str]:
    await handler.execute(item_id, request.new_state, typing.cast("int", user_payload["user_id"]))
    return {"status": "success", "message": "Applicator state updated successfully"}


# RBAC Protected Routes


@router.post("/api/applicators/{id}/unbind", status_code=status.HTTP_200_OK)
@inject
async def unbind_applicator(
    handler: FromDishka[UnbindApplicatorHandler],
    user_payload: typing.Annotated[
        dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN, Role.OPERATOR]))
    ],
    item_id: typing.Annotated[int, Path(alias="id")],
) -> dict[str, str]:
    await handler.execute(item_id, typing.cast("int", user_payload["user_id"]))
    return {"status": "success", "message": "Applicator unbound"}


@router.get("/api/applicators", status_code=status.HTTP_200_OK)
@inject
async def list_applicators(
    handler: FromDishka[ListApplicatorsHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(get_current_user_payload)],
) -> list[ApplicatorListItemDTO]:
    return await handler.execute()


@router.get("/api/applicators/blocked", status_code=status.HTTP_200_OK)
@inject
async def list_blocked_applicators(
    handler: FromDishka[ListBlockedApplicatorsHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN]))],
) -> list[BlockedApplicatorDTO]:
    return await handler.execute()


@router.get("/api/movements", status_code=status.HTTP_200_OK)
@inject
async def list_movements(
    handler: FromDishka[ListMovementsHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN]))],
    limit: int = 100,
) -> list[MovementLogDTO]:
    return await handler.execute(min(max(limit, 1), 500))


@router.get("/api/applicators/{id}/history", status_code=status.HTTP_200_OK)
@inject
async def get_applicator_history(
    handler: FromDishka[GetApplicatorHistoryHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN]))],
    item_id: typing.Annotated[int, Path(alias="id")],
) -> list[MovementLogDTO]:
    return await handler.execute(item_id)


@router.post("/api/applicators/{id}/block", status_code=status.HTTP_200_OK)
@inject
async def block_applicator(
    request: BlockRequest,
    handler: FromDishka[BlockApplicatorHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN]))],
    item_id: typing.Annotated[int, Path(alias="id")],
) -> dict[str, str]:
    await handler.execute(item_id, request.reason, typing.cast("int", user_payload["user_id"]))
    return {"status": "success", "message": "Applicator blocked"}


@router.post("/api/applicators/{id}/unblock", status_code=status.HTTP_200_OK)
@inject
async def unblock_applicator(
    handler: FromDishka[UnblockApplicatorHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN]))],
    item_id: typing.Annotated[int, Path(alias="id")],
) -> dict[str, str]:
    await handler.execute(item_id, typing.cast("int", user_payload["user_id"]))
    return {"status": "success", "message": "Applicator unblocked"}


@router.get("/api/public/machines", status_code=status.HTTP_200_OK)
@inject
async def list_machines_public(
    handler: FromDishka[ListMachinesHandler],
) -> list[dict[str, str]]:
    machines = await handler.execute()
    return [{"hardware_code": m.hardware_code, "zone_name": m.zone_name} for m in machines]


@router.get("/api/machines", status_code=status.HTTP_200_OK)
@inject
async def list_machines(
    handler: FromDishka[ListMachinesHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(get_current_user_payload)],
) -> list[MachineDTO]:
    return await handler.execute()


@router.get("/api/zones", status_code=status.HTTP_200_OK)
@inject
async def list_zones(
    handler: FromDishka[ListZonesHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(get_current_user_payload)],
) -> list[ZoneDTO]:
    return await handler.execute()


@router.post("/api/machines", status_code=status.HTTP_201_CREATED)
@inject
async def create_machine(
    request: MachineCreateRequest,
    handler: FromDishka[CreateMachineHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN]))],
) -> dict[str, str]:
    await handler.execute(request.hardware_code, request.zone_id)
    return {"status": "success", "message": "Machine created successfully"}


@router.post("/api/applicators", status_code=status.HTTP_201_CREATED)
@inject
async def create_applicator(
    request: ApplicatorCreateRequest,
    handler: FromDishka[CreateApplicatorHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN]))],
) -> dict[str, str]:
    await handler.execute(request.serial_number, request.machine_id, request.state)
    return {"status": "success", "message": "Applicator created successfully"}


@router.delete("/api/machines/{id}", status_code=status.HTTP_200_OK)
@inject
async def delete_machine(
    handler: FromDishka[DeleteMachineHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN]))],
    item_id: typing.Annotated[int, Path(alias="id")],
) -> dict[str, str]:
    await handler.execute(item_id)
    return {"status": "success"}


@router.delete("/api/applicators/{id}", status_code=status.HTTP_200_OK)
@inject
async def delete_applicator(
    handler: FromDishka[DeleteApplicatorHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN]))],
    item_id: typing.Annotated[int, Path(alias="id")],
) -> dict[str, str]:
    await handler.execute(item_id)
    return {"status": "success"}


@router.post("/api/users", status_code=status.HTTP_201_CREATED)
@inject
async def create_user(
    request: UserCreateRequest,
    handler: FromDishka[CreateUserHandler],
    user_payload: typing.Annotated[dict[str, typing.Any], Depends(require_role_flexible([Role.TECH_ADMIN]))],
) -> dict[str, str]:
    hashed_pwd = get_password_hash(request.password)
    await handler.execute(
        username=request.username,
        password_hash=hashed_pwd,
        role=request.role,
        operator_code=request.operator_code
    )
    return {"status": "success", "message": "User created successfully"}
