from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from domain.entities import ApplicatorState, Role


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(SQLEnum(Role), nullable=False)
    operator_code: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)


class ZoneORM(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    max_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    max_in_use: Mapped[int] = mapped_column(Integer, nullable=False)
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__: Any = {  # noqa: RUF012
        "version_id_col": version_id,
    }

    machines: Mapped[list["MachineORM"]] = relationship(
        "MachineORM", back_populates="zone", cascade="all, delete-orphan"
    )
    applicators: Mapped[list["ApplicatorORM"]] = relationship("ApplicatorORM", back_populates="zone")


class MachineORM(Base):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hardware_code: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), nullable=False)
    max_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__: Any = {  # noqa: RUF012
        "version_id_col": version_id,
    }

    zone: Mapped[ZoneORM] = relationship("ZoneORM", back_populates="machines")
    applicators: Mapped[list["ApplicatorORM"]] = relationship("ApplicatorORM", back_populates="machine")


class ApplicatorORM(Base):
    __tablename__ = "applicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    serial_number: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    current_zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    current_machine_id: Mapped[int | None] = mapped_column(ForeignKey("machines.id"), nullable=True)
    state: Mapped[ApplicatorState] = mapped_column(
        SQLEnum(ApplicatorState), nullable=False, default=ApplicatorState.NONE
    )

    zone: Mapped[Optional["ZoneORM"]] = relationship("ZoneORM", back_populates="applicators")
    machine: Mapped[Optional["MachineORM"]] = relationship("MachineORM", back_populates="applicators")


class MovementLogORM(Base):
    __tablename__ = "movement_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicator_id: Mapped[int] = mapped_column(ForeignKey("applicators.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    from_location: Mapped[str] = mapped_column(String(255), nullable=False)
    to_location: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class BlockLogORM(Base):
    __tablename__ = "block_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicator_id: Mapped[int] = mapped_column(ForeignKey("applicators.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
