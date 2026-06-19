class DomainError(Exception):
    """Base class for domain-specific exceptions."""


class CapacityExceededError(DomainError):
    """Raised when a capacity limit is exceeded."""


class InvalidStateError(DomainError):
    """Raised when an operation is invalid for the current state."""


class EntityNotFoundError(DomainError):
    """Raised when a requested entity does not exist."""


class ConcurrencyError(DomainError):
    """Raised when an optimistic concurrency conflict is detected."""


class DuplicateEntityError(DomainError):
    """Raised when trying to create an entity that already exists."""


class AuthenticationError(DomainError):
    """Raised when authentication fails."""


__all__ = [
    "CapacityExceededError",
    "ConcurrencyError",
    "DomainError",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "InvalidStateError",
    "AuthenticationError",
]
