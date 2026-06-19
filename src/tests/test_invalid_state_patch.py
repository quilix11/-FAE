import pytest
from fastapi import status
from httpx import AsyncClient

from domain.entities import ApplicatorState
from infrastructure.models.orm import ApplicatorORM, MachineORM, ZoneORM


@pytest.mark.asyncio
async def test_patch_applicator_invalid_state(client: AsyncClient, admin_token: str, db_session) -> None:
    # Setup data
    zone = ZoneORM(name="ZoneE", max_capacity=5, max_in_use=5)
    db_session.add(zone)
    await db_session.flush()
    machine = MachineORM(hardware_code="M40", zone_id=zone.id)
    db_session.add(machine)
    await db_session.flush()
    app = ApplicatorORM(
        serial_number="APP40", current_zone_id=zone.id, current_machine_id=machine.id, state=ApplicatorState.ON_RACK
    )
    db_session.add(app)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {admin_token}"}

    # Try to patch with an invalid state
    response = await client.patch(
        f"/api/applicators/{app.id}/state",
        json={"new_state": "SUPER_INVALID_STATE"},
        headers=headers,
    )

    # Verify we get 422 Unprocessable Entity instead of 500 Internal Server Error
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert (
        "Input should be" in response.json()["detail"][0]["msg"]
        or "value is not a valid enumeration member" in response.text
    )
