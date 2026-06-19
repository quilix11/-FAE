import pytest
from fastapi import status

from domain.entities import ApplicatorState
from infrastructure.models.orm import ApplicatorORM, MachineORM, ZoneORM


@pytest.mark.asyncio
async def test_auth_success(client) -> None:
    response = await client.post("/auth/login", data={"username": "admin", "password": "adminpass"})
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_auth_failure(client) -> None:
    response = await client.post("/auth/login", data={"username": "admin", "password": "wrongpassword"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_operator_code_login_success(client) -> None:
    # login_type is passed as a form field, username field holds the operator_code value
    response = await client.post(
        "/auth/login",
        data={"username": "OP_123", "password": "oppass", "login_type": "operator_code"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_operator_code_login_failure(client) -> None:
    # Wrong operator code
    response1 = await client.post(
        "/auth/login",
        data={"username": "BAD_OP_CODE", "password": "oppass", "login_type": "operator_code"},
    )
    assert response1.status_code == status.HTTP_401_UNAUTHORIZED

    # Right operator code, wrong password
    response2 = await client.post(
        "/auth/login",
        data={"username": "OP_123", "password": "wrongpassword", "login_type": "operator_code"},
    )
    assert response2.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_zone_machine_applicator(client, admin_token, db_session) -> None:
    # API doesn't have create_zone, we seed it manually for test
    zone = ZoneORM(name="ZoneA", max_capacity=2, max_in_use=1)
    db_session.add(zone)
    await db_session.commit()

    # Create machine (Admin)
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.post("/api/machines", json={"hardware_code": "M1", "zone_id": zone.id}, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED

    # Create applicator (Admin)
    response = await client.post(
        "/api/applicators", json={"serial_number": "APP1", "machine_id": None, "state": "none"}, headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED

    # Verify they exist
    response = await client.get("/api/machines", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_operator_cannot_create_machine(client, operator_token) -> None:
    headers = {"Authorization": f"Bearer {operator_token}"}
    response = await client.post("/api/machines", json={"hardware_code": "M2", "zone_id": 1}, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_scan_applicator(client, admin_token, operator_token, db_session) -> None:
    # Setup data
    zone = ZoneORM(name="ZoneB", max_capacity=2, max_in_use=1)
    db_session.add(zone)
    await db_session.flush()
    machine = MachineORM(hardware_code="M10", zone_id=zone.id)
    db_session.add(machine)
    await db_session.flush()
    app1 = ApplicatorORM(
        serial_number="APP10", current_zone_id=None, current_machine_id=None, state=ApplicatorState.NONE
    )
    db_session.add(app1)
    await db_session.commit()

    # Operator scans applicator to machine
    headers = {"Authorization": f"Bearer {operator_token}"}
    response = await client.post("/api/scan", json={"serial_number": "APP10", "hardware_code": "M10"}, headers=headers)
    assert response.status_code == status.HTTP_200_OK

    # Verify
    await db_session.refresh(app1)
    assert app1.current_machine_id == machine.id
    assert app1.current_zone_id == zone.id


@pytest.mark.asyncio
async def test_change_state_and_in_use_limit(client, admin_token, operator_token, db_session) -> None:
    # Setup data
    zone = ZoneORM(name="ZoneC", max_capacity=5, max_in_use=1)
    db_session.add(zone)
    await db_session.flush()
    machine = MachineORM(hardware_code="M20", zone_id=zone.id)
    db_session.add(machine)
    await db_session.flush()
    app1 = ApplicatorORM(
        serial_number="APP20", current_zone_id=zone.id, current_machine_id=machine.id, state=ApplicatorState.ON_RACK
    )
    app2 = ApplicatorORM(
        serial_number="APP21", current_zone_id=zone.id, current_machine_id=machine.id, state=ApplicatorState.ON_RACK
    )
    db_session.add_all([app1, app2])
    await db_session.commit()

    headers = {"Authorization": f"Bearer {operator_token}"}

    # Change app1 to in_use
    response = await client.patch(f"/api/applicators/{app1.id}/state", json={"new_state": "in_use"}, headers=headers)
    assert response.status_code == status.HTTP_200_OK

    # Try to change app2 to in_use, should fail because max_in_use=1
    response = await client.patch(f"/api/applicators/{app2.id}/state", json={"new_state": "in_use"}, headers=headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "reached its in_use limit" in response.json()["detail"]


@pytest.mark.asyncio
async def test_unbind_applicator(client, admin_token, operator_token, db_session) -> None:
    zone = ZoneORM(name="ZoneD", max_capacity=2, max_in_use=1)
    db_session.add(zone)
    await db_session.flush()
    machine = MachineORM(hardware_code="M30", zone_id=zone.id)
    db_session.add(machine)
    await db_session.flush()
    app1 = ApplicatorORM(
        serial_number="APP30", current_zone_id=zone.id, current_machine_id=machine.id, state=ApplicatorState.ON_RACK
    )
    db_session.add(app1)
    await db_session.commit()

    # Operator can unbind (remove an applicator from their machine back to Service)
    op_headers = {"Authorization": f"Bearer {operator_token}"}
    response = await client.post(f"/api/applicators/{app1.id}/unbind", headers=op_headers)
    assert response.status_code == status.HTTP_200_OK

    await db_session.refresh(app1)
    assert app1.current_machine_id is None
    assert app1.current_zone_id is None
    assert app1.state == ApplicatorState.NONE

    # Admin can unbind too
    app2 = ApplicatorORM(
        serial_number="APP31", current_zone_id=zone.id, current_machine_id=machine.id, state=ApplicatorState.ON_RACK
    )
    db_session.add(app2)
    await db_session.commit()

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.post(f"/api/applicators/{app2.id}/unbind", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK

    await db_session.refresh(app2)
    assert app2.current_machine_id is None


@pytest.mark.asyncio
async def test_create_unattached_applicator_is_listed(client, admin_token, db_session) -> None:
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Create an applicator WITHOUT a machine (the case that previously "vanished")
    resp = await client.post(
        "/api/applicators", json={"serial_number": "FREE-1", "machine_id": None}, headers=admin_headers
    )
    assert resp.status_code == status.HTTP_201_CREATED

    # It must show up in the full inventory list, with no machine
    resp = await client.get("/api/applicators", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()
    match = next((a for a in items if a["serial_number"] == "FREE-1"), None)
    assert match is not None
    assert match["machine_code"] is None

    # Creating the same serial again is rejected as duplicate
    resp = await client.post(
        "/api/applicators", json={"serial_number": "FREE-1", "machine_id": None}, headers=admin_headers
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_movement_history_records_scan_and_unbind(client, admin_token, operator_token, db_session) -> None:
    zone = ZoneORM(name="ZoneHist", max_capacity=5, max_in_use=3)
    db_session.add(zone)
    await db_session.flush()
    machine = MachineORM(hardware_code="M_HIST", zone_id=zone.id)
    db_session.add(machine)
    await db_session.flush()
    app1 = ApplicatorORM(
        serial_number="APP_HIST", current_zone_id=None, current_machine_id=None, state=ApplicatorState.NONE
    )
    db_session.add(app1)
    await db_session.commit()

    op_headers = {"Authorization": f"Bearer {operator_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Operator scans it onto the machine, then unbinds -> two movement entries
    resp = await client.post("/api/scan", json={"serial_number": "APP_HIST", "hardware_code": "M_HIST"}, headers=op_headers)
    assert resp.status_code == status.HTTP_200_OK
    resp = await client.post(f"/api/applicators/{app1.id}/unbind", headers=op_headers)
    assert resp.status_code == status.HTTP_200_OK

    # Per-applicator history (admin)
    resp = await client.get(f"/api/applicators/{app1.id}/history", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK
    history = resp.json()
    assert len(history) == 2
    # Newest first: the unbind to Service
    assert history[0]["to_location"] == "Service"
    assert all(h["serial_number"] == "APP_HIST" for h in history)

    # Global recent feed contains these too
    resp = await client.get("/api/movements", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK
    assert any(m["serial_number"] == "APP_HIST" for m in resp.json())

    # Operator is not allowed to read history
    resp = await client.get("/api/movements", headers=op_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_block_and_unblock_applicator(client, admin_token, operator_token, db_session) -> None:
    blocked_zone = ZoneORM(name="Blocked", max_capacity=1000, max_in_use=0)
    zone = ZoneORM(name="ZoneBlk", max_capacity=5, max_in_use=2)
    db_session.add_all([blocked_zone, zone])
    await db_session.flush()
    machine = MachineORM(hardware_code="M_BLK", zone_id=zone.id)
    db_session.add(machine)
    await db_session.flush()
    app1 = ApplicatorORM(
        serial_number="APP_BLK", current_zone_id=zone.id, current_machine_id=machine.id, state=ApplicatorState.IN_USE
    )
    db_session.add(app1)
    await db_session.commit()

    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Operator cannot block (admin-only)
    op_headers = {"Authorization": f"Bearer {operator_token}"}
    resp = await client.post(f"/api/applicators/{app1.id}/block", json={"reason": "x"}, headers=op_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Admin blocks with a reason
    resp = await client.post(
        f"/api/applicators/{app1.id}/block", json={"reason": "Defective tip"}, headers=admin_headers
    )
    assert resp.status_code == status.HTTP_200_OK

    await db_session.refresh(app1)
    assert app1.current_machine_id is None
    assert app1.current_zone_id == blocked_zone.id

    # Blocked list shows it with the reason
    resp = await client.get("/api/applicators/blocked", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK
    blocked = resp.json()
    assert any(b["serial_number"] == "APP_BLK" and b["reason"] == "Defective tip" for b in blocked)

    # Unblock returns it to Service (unbound)
    resp = await client.post(f"/api/applicators/{app1.id}/unblock", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK

    await db_session.refresh(app1)
    assert app1.current_zone_id is None
    assert app1.current_machine_id is None

    resp = await client.get("/api/applicators/blocked", headers=admin_headers)
    assert all(b["serial_number"] != "APP_BLK" for b in resp.json())


@pytest.mark.asyncio
async def test_delete_machine_unbinds_attached_applicators(client, admin_token, db_session) -> None:
    zone = ZoneORM(name="ZoneDel", max_capacity=3, max_in_use=2)
    db_session.add(zone)
    await db_session.flush()
    machine = MachineORM(hardware_code="M_DEL", zone_id=zone.id)
    db_session.add(machine)
    await db_session.flush()
    app = ApplicatorORM(
        serial_number="APP_DEL",
        current_zone_id=zone.id,
        current_machine_id=machine.id,
        state=ApplicatorState.ON_RACK,
    )
    db_session.add(app)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.delete(f"/api/machines/{machine.id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    await db_session.refresh(app)
    assert app.current_machine_id is None
    assert app.current_zone_id is None
    assert app.state == ApplicatorState.NONE
