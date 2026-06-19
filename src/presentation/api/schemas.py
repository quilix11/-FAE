from pydantic import BaseModel

from domain.entities import ApplicatorState, Role


class ScanRequest(BaseModel):
    serial_number: str
    hardware_code: str


class StateUpdateRequest(BaseModel):
    new_state: ApplicatorState


class BlockRequest(BaseModel):
    reason: str


class MachineCreateRequest(BaseModel):
    hardware_code: str
    zone_id: int


class ApplicatorCreateRequest(BaseModel):
    serial_number: str
    machine_id: int | None = None
    state: ApplicatorState = ApplicatorState.NONE


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: Role
    operator_code: str | None = None

