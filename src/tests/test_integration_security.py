import json

import pytest
from fastapi import WebSocketDisconnect, status
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import text

from infrastructure.models.orm import MachineORM, ZoneORM
from main import app


@pytest.mark.asyncio
async def test_409_conflict_machine_creation(client: AsyncClient, admin_token, db_session) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create first machine
    resp1 = await client.post("/api/machines", json={"hardware_code": "M_CONFLICT", "zone_id": 1}, headers=headers)

    if resp1.status_code == status.HTTP_404_NOT_FOUND:
        # Zone doesn't exist, create it manually via DB for testing
        zone = ZoneORM(name="ZoneForConflictTest", max_capacity=10, max_in_use=5)
        db_session.add(zone)
        await db_session.commit()
        resp1 = await client.post(
            "/api/machines", json={"hardware_code": "M_CONFLICT", "zone_id": zone.id}, headers=headers
        )

    assert resp1.status_code in [status.HTTP_201_CREATED, status.HTTP_200_OK]

    # Try creating second machine with SAME hardware code
    resp2 = await client.post("/api/machines", json={"hardware_code": "M_CONFLICT", "zone_id": 1}, headers=headers)
    assert resp2.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_409_conflict_applicator_creation(client: AsyncClient, admin_token, db_session) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create first applicator
    resp1 = await client.post(
        "/api/applicators", json={"serial_number": "APP_CONFLICT", "machine_id": None, "state": "none"}, headers=headers
    )
    assert resp1.status_code in [status.HTTP_201_CREATED, status.HTTP_200_OK]

    # Try creating second applicator with SAME serial number
    resp2 = await client.post(
        "/api/applicators", json={"serial_number": "APP_CONFLICT", "machine_id": None, "state": "none"}, headers=headers
    )
    assert resp2.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rbac_vulnerabilities(client: AsyncClient, operator_token, admin_token, db_session) -> None:
    op_headers = {"Authorization": f"Bearer {operator_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Operator tries to delete a machine
    # First admin creates a machine
    zone = ZoneORM(name="ZoneRBAC", max_capacity=10, max_in_use=5)
    db_session.add(zone)
    await db_session.commit()

    await client.post(
        "/api/machines", json={"hardware_code": "M_RBAC_TEST", "zone_id": zone.id}, headers=admin_headers
    )

    # Get machine id
    machines_resp = await client.get("/api/machines", headers=admin_headers)
    machine_id = next(m["id"] for m in machines_resp.json() if m["hardware_code"] == "M_RBAC_TEST")

    # Operator tries to delete
    del_resp = await client.delete(f"/api/machines/{machine_id}", headers=op_headers)
    assert del_resp.status_code == status.HTTP_403_FORBIDDEN, "Operator should not be able to delete a machine!"

    # Operator tries to delete an applicator
    await client.post(
        "/api/applicators",
        json={"serial_number": "APP_RBAC_TEST", "machine_id": None, "state": "none"},
        headers=admin_headers,
    )

    app_in_db = await db_session.execute(text("SELECT id FROM applicators WHERE serial_number='APP_RBAC_TEST'"))
    app_id = app_in_db.scalar()

    del_app_resp = await client.delete(f"/api/applicators/{app_id}", headers=op_headers)
    assert del_app_resp.status_code == status.HTTP_403_FORBIDDEN, "Operator should not be able to delete an applicator!"


@pytest.mark.asyncio
async def test_cors_vulnerability(client: AsyncClient) -> None:
    # Try to make a request with an arbitrary Origin header
    headers = {
        "Origin": "http://malicious.com",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization",
    }
    response = await client.options("/api/machines", headers=headers)
    if "access-control-allow-origin" in response.headers:
        assert response.headers["access-control-allow-origin"] != "http://malicious.com", (
            "CORS vulnerability! Allowed malicious origin."
        )
        assert response.headers["access-control-allow-origin"] != "*", "CORS vulnerability! Allowed all origins."


@pytest.mark.asyncio
async def test_websocket_targeted_updates(client: AsyncClient, admin_token, db_session) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    zone = ZoneORM(name="ZoneWS", max_capacity=10, max_in_use=5)
    db_session.add(zone)
    await db_session.flush()
    machine = MachineORM(hardware_code="M_WS_TEST", zone_id=zone.id)
    db_session.add(machine)
    await db_session.commit()

    with TestClient(app) as test_client:
        # Verify invalid token is rejected
        with pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: SIM117
            with test_client.websocket_connect("/api/ws/dashboard/M_WS_TEST?token=invalid"):
                pass
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

        # Verify valid token gets accepted
        with test_client.websocket_connect(f"/api/ws/dashboard/M_WS_TEST?token={admin_token}") as websocket:
            # First message should be the initial dashboard state
            data = websocket.receive_json()
            assert data["hardware_code"] == "M_WS_TEST"

            # Try to trigger an update
            scan_resp = test_client.post(
                "/api/scan", json={"serial_number": "APP_WS_TEST", "hardware_code": "M_WS_TEST"}, headers=headers
            )

            if scan_resp.status_code == status.HTTP_404_NOT_FOUND:
                # Need to create the applicator first
                test_client.post(
                    "/api/applicators",
                    json={"serial_number": "APP_WS_TEST", "machine_id": None, "state": "none"},
                    headers=headers,
                )
                test_client.post(
                    "/api/scan", json={"serial_number": "APP_WS_TEST", "hardware_code": "M_WS_TEST"}, headers=headers
                )

            # Wait for WS message
            update_data = websocket.receive_text()
            update_json = json.loads(update_data)
            assert update_json["hardware_code"] == "M_WS_TEST"
            assert len(update_json["applicators"]) > 0
            assert update_json["applicators"][0]["serial_number"] == "APP_WS_TEST"


@pytest.mark.asyncio
async def test_websocket_inventory_security(admin_token) -> None:
    with TestClient(app) as test_client:
        # Missing token
        with pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: SIM117
            with test_client.websocket_connect("/api/ws/inventory"):
                pass
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

        # Invalid token
        with pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: SIM117
            with test_client.websocket_connect("/api/ws/inventory?token=invalid"):
                pass
        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION

        # Valid token
        with test_client.websocket_connect(f"/api/ws/inventory?token={admin_token}"):
            pass


@pytest.mark.asyncio
async def test_websocket_inventory_broadcast(admin_token, db_session) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    zone = ZoneORM(name="ZoneWSInv", max_capacity=10, max_in_use=5)
    db_session.add(zone)
    await db_session.flush()
    await db_session.commit()
    with (
        TestClient(app) as test_client,
        test_client.websocket_connect(f"/api/ws/inventory?token={admin_token}") as websocket,
    ):
        resp = test_client.post(
            "/api/machines", json={"hardware_code": "M_INV_TEST", "zone_id": zone.id}, headers=headers
        )
        assert resp.status_code == status.HTTP_201_CREATED
        update_data = websocket.receive_text()
        update_json = json.loads(update_data)
        assert update_json["event"] == "machine_created"
        assert update_json["hardware_code"] == "M_INV_TEST"


@pytest.mark.asyncio
async def test_operator_cannot_create_user(client: AsyncClient, operator_token, admin_token) -> None:
    op_headers = {"Authorization": f"Bearer {operator_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Operator tries to create another operator
    resp = await client.post(
        "/api/users",
        json={
            "username": "new_operator",
            "password": "securepassword",
            "role": "Operator",
            "operator_code": "OP123"
        },
        headers=op_headers
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN, "Operator should NOT be able to create a user!"

    # Admin should be able to create a user
    resp_admin = await client.post(
        "/api/users",
        json={
            "username": "new_admin_created_op",
            "password": "securepassword",
            "role": "Operator",
            "operator_code": "OP456"
        },
        headers=admin_headers
    )
    assert resp_admin.status_code == status.HTTP_201_CREATED, "Tech_Admin should be able to create a user!"
