import types
from abc import ABC, abstractmethod

from typing_extensions import Self

from .entities import Applicator, ApplicatorState, BlockLog, Machine, MovementLog, Role, User, Zone


class UserRepository(ABC):
    """Abstract repository for User entities."""

    @abstractmethod
    async def get_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    async def get_by_operator_code(self, operator_code: str) -> User | None: ...

    @abstractmethod
    async def create(self, username: str, hashed_password: str, role: Role, operator_code: str | None) -> User: ...


class ZoneRepository(ABC):
    """Abstract repository for Zone entities."""

    @abstractmethod
    async def get_by_id(self, zone_id: int) -> Zone | None: ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Zone | None: ...

    @abstractmethod
    async def get_in_use_count(self, zone_id: int) -> int: ...

    @abstractmethod
    async def save(self, zone: Zone) -> None: ...

    @abstractmethod
    async def get_all(self) -> list[Zone]: ...


class MovementLogRepository(ABC):
    """Abstract repository for MovementLog entities."""

    @abstractmethod
    async def add(self, log: MovementLog) -> None: ...


class BlockLogRepository(ABC):
    """Abstract repository for BlockLog entities."""

    @abstractmethod
    async def add(self, log: BlockLog) -> None: ...


class ApplicatorRepository(ABC):
    """Abstract repository for Applicator entities."""

    @abstractmethod
    async def get_by_id(self, applicator_id: int) -> Applicator | None: ...

    @abstractmethod
    async def get_by_serial_number(self, serial_number: str) -> Applicator | None: ...

    @abstractmethod
    async def get_by_machine_id(self, machine_id: int) -> list[Applicator]: ...

    @abstractmethod
    async def save(self, applicator: Applicator) -> None: ...

    @abstractmethod
    async def create(self, serial_number: str, machine_id: int | None, state: ApplicatorState) -> Applicator: ...

    @abstractmethod
    async def delete(self, applicator_id: int) -> None: ...


class MachineRepository(ABC):
    """Abstract repository for Machine entities."""

    @abstractmethod
    async def get_by_id(self, machine_id: int) -> Machine | None: ...

    @abstractmethod
    async def get_by_hardware_code(self, hardware_code: str) -> Machine | None: ...

    @abstractmethod
    async def get_applicators_count(self, machine_id: int) -> int: ...

    @abstractmethod
    async def save(self, machine: Machine) -> None: ...

    @abstractmethod
    async def create(self, hardware_code: str, zone_id: int) -> Machine: ...

    @abstractmethod
    async def delete(self, machine_id: int) -> None: ...

    @abstractmethod
    async def get_all(self) -> list[Machine]: ...


class UnitOfWork(ABC):
    """Abstract Unit of Work pattern."""

    users: UserRepository
    zones: ZoneRepository
    machines: MachineRepository
    applicators: ApplicatorRepository
    movement_logs: MovementLogRepository
    block_logs: BlockLogRepository

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        traceback: types.TracebackType | None
    ) -> None:
        await self.rollback()

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


__all__ = [
    "ApplicatorRepository",
    "BlockLogRepository",
    "MachineRepository",
    "MovementLogRepository",
    "UnitOfWork",
    "UserRepository",
    "ZoneRepository",
]
