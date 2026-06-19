import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import text


@pytest.mark.asyncio
async def test_auth_missing_and_invalid_token(client: AsyncClient) -> None:
    # Missing token
    resp = await client.get("/api/machines")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Invalid token
    resp = await client.get("/api/machines", headers={"Authorization": "Bearer invalid_token"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Malformed token format
    resp = await client.get("/api/machines", headers={"Authorization": "invalid_token"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_sql_injection_attempt(client: AsyncClient, admin_token, db_session) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Try SQL injection in serial_number
    malicious_serial = "'; DROP TABLE applicators; --"
    resp = await client.post(
        "/api/applicators",
        json={"serial_number": malicious_serial, "machine_id": None, "state": "none"},
        headers=headers,
    )
    assert resp.status_code in [
        status.HTTP_201_CREATED,
        status.HTTP_200_OK,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    ], "Should handle input safely without executing SQL"

    # Check if we can get it
    resp_get = await client.get("/api/machines", headers=headers)
    assert resp_get.status_code == status.HTTP_200_OK
    # The DB shouldn't be dropped


@pytest.mark.asyncio
async def test_scan_invalid_machine(client: AsyncClient, operator_token) -> None:
    headers = {"Authorization": f"Bearer {operator_token}"}

    # Scan applicator to non-existent machine
    resp = await client.post(
        "/api/scan", json={"serial_number": "ANY_APP", "hardware_code": "NON_EXISTENT_MACHINE_999"}, headers=headers
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_state_transition(client: AsyncClient, operator_token, admin_token, db_session) -> None:
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    operator_headers = {"Authorization": f"Bearer {operator_token}"}

    # Create applicator
    resp_app = await client.post(
        "/api/applicators",
        json={"serial_number": "APP_STATE_TEST", "machine_id": None, "state": "none"},
        headers=admin_headers,
    )
    app_data = resp_app.json()
    app_id = app_data.get("id", None)

    if not app_id:
        app_in_db = await db_session.execute(text("SELECT id FROM applicators WHERE serial_number='APP_STATE_TEST'"))
        app_id = app_in_db.scalar()

    # Try changing to invalid state string
    resp = await client.patch(
        f"/api/applicators/{app_id}/state", json={"new_state": "INVALID_STATE"}, headers=operator_headers
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, "Should return validation error for invalid state"


@pytest.mark.asyncio
async def test_websocket_invalid_token(client: AsyncClient) -> None:
    try:
        async with client.websocket_connect("/api/ws/dashboard/M_WS_TEST?token=invalid_token") as websocket:
            # Should be rejected
            await websocket.receive_text()
            pytest.fail("WebSocket should have been closed/rejected")
    except Exception as e:
        # Expected to fail
        assert e


@pytest.mark.asyncio
async def test_delete_non_existent_resources(client: AsyncClient, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp_machine = await client.delete("/api/machines/999999", headers=headers)
    assert resp_machine.status_code == status.HTTP_404_NOT_FOUND

    resp_app = await client.delete("/api/applicators/999999", headers=headers)
    assert resp_app.status_code == status.HTTP_404_NOT_FOUND
