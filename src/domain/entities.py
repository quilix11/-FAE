from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .exceptions import CapacityExceededError, InvalidStateError


class Role(str, Enum):
    """User roles for RBAC."""

    OPERATOR = "Operator"
    TECH_ADMIN = "Tech_Admin"


class ApplicatorState(str, Enum):
    """Possible states of an applicator."""

    IN_USE = "in_use"
    ON_RACK = "on_rack"
    NONE = "none"


@dataclass
class User:
    id: int
    username: str
    hashed_password: str
    role: Role
    operator_code: str | None = None


@dataclass
class MovementLog:
    applicator_id: int
    user_id: int
    from_location: str
    to_location: str
    timestamp: datetime
    id: int | None = None


@dataclass
class BlockLog:
    applicator_id: int
    user_id: int
    reason: str
    timestamp: datetime
    id: int | None = None


@dataclass
class Zone:
    id: int
    name: str
    max_capacity: int
    max_in_use: int
    version: int = 1


@dataclass
class Machine:
    id: int
    hardware_code: str
    zone_id: int
    max_capacity: int
    version: int = 1


@dataclass
class Applicator:
    id: int
    serial_number: str
    current_zone_id: int | None
    current_machine_id: int | None
    state: ApplicatorState

    def move_to_machine(
        self, target_machine: "Machine", target_zone: "Zone", current_machine_applicators: int, target_zone_in_use: int
    ) -> None:
        """Move applicator to a new machine.
        If it's already bound to a different machine, raise InvalidStateError (Explicit unbinding rule).
        Check max_capacity for the target machine.
        """
        if self.current_machine_id == target_machine.id:
            return  # Already on this machine, no-op

        if target_machine.zone_id != target_zone.id:
            raise InvalidStateError("Target machine does not belong to the target zone.")

        # Rule: No Implicit Unbinding
        # "Service" or "Applicator room" is considered "unbound" state.
        # Here we assume unbound means current_machine_id is None.
        if self.current_machine_id is not None:
            raise InvalidStateError(
                f"Applicator {self.id} is already bound to a machine. "
                "It must be explicitly unbound first "
                "(e.g. moved to Service/Applicator room)."
            )

        if current_machine_applicators >= target_machine.max_capacity:
            raise CapacityExceededError(
                f"Machine {target_machine.id} has reached its capacity of {target_machine.max_capacity}."
            )

        self.current_machine_id = target_machine.id
        self.current_zone_id = target_zone.id

    def set_state(self, new_state: "ApplicatorState", target_zone: "Zone", target_zone_in_use_count: int) -> None:
        """Change state of the applicator.
        Rule: If new_state is in_use, check if target_zone_in_use_count < target_zone.max_in_use.
        If exceeded, set state to on_rack (or raise error as per plan, we will raise error for 400).
        """
        if (
            new_state == ApplicatorState.IN_USE
            and self.state != ApplicatorState.IN_USE
            and target_zone_in_use_count >= target_zone.max_in_use
        ):
            raise CapacityExceededError(
                    f"Zone {target_zone.id} has reached its in_use limit of {target_zone.max_in_use}."
                )

        self.state = new_state

    def unbind(self) -> None:
        """Explicitly unbind from machine (e.g. moving to Service)."""
        self.current_machine_id = None
        self.current_zone_id = None
        self.state = ApplicatorState.NONE

    def block(self, blocked_zone_id: int) -> None:
        """Move the applicator to the Blocked zone (e.g. defective/out of service).

        It is detached from any machine; being in the Blocked zone is what marks
        it as blocked (no dedicated state value is required).
        """
        self.current_machine_id = None
        self.current_zone_id = blocked_zone_id
        self.state = ApplicatorState.NONE


__all__ = [
    "Applicator",
    "ApplicatorState",
    "BlockLog",
    "Machine",
    "MovementLog",
    "Role",
    "User",
    "Zone",
]
