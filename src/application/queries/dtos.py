from pydantic import BaseModel, ConfigDict


class ApplicatorDTO(BaseModel):
    """Data transfer object for applicator data."""

    id: int
    serial_number: str
    state: str

    model_config = ConfigDict(from_attributes=True)


class DashboardDTO(BaseModel):
    """Data transfer object for dashboard view."""

    machine_id: int
    hardware_code: str
    zone_name: str
    max_capacity: int
    current_capacity: int
    max_in_use: int
    current_in_use: int
    applicators: list[ApplicatorDTO]

    model_config = ConfigDict(from_attributes=True)


class ApplicatorListItemDTO(BaseModel):
    """Data transfer object for an applicator in the full inventory list."""

    id: int
    serial_number: str
    state: str
    machine_code: str | None = None
    zone_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MovementLogDTO(BaseModel):
    """Data transfer object for a single movement-history entry."""

    id: int
    applicator_id: int
    serial_number: str | None = None
    from_location: str
    to_location: str
    timestamp: str
    user: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BlockedApplicatorDTO(BaseModel):
    """Data transfer object for a blocked applicator with its latest block reason."""

    id: int
    serial_number: str
    reason: str | None = None
    blocked_at: str | None = None
    blocked_by: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MachineDTO(BaseModel):
    """Data transfer object for machine listings."""

    id: int
    hardware_code: str
    zone_name: str

    model_config = ConfigDict(from_attributes=True)


class ZoneDTO(BaseModel):
    """Data transfer object for zone listings."""

    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "ApplicatorDTO",
    "ApplicatorListItemDTO",
    "BlockedApplicatorDTO",
    "DashboardDTO",
    "MachineDTO",
    "MovementLogDTO",
    "ZoneDTO",
]
