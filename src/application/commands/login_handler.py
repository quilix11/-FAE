from domain.exceptions import AuthenticationError
from domain.interfaces import UnitOfWork
from infrastructure.auth import create_access_token, verify_password


class LoginHandler:
    """Handles user authentication and token generation."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, identifier: str, password: str, login_type: str = "username") -> dict[str, str]:
        async with self.uow:
            if login_type == "operator_code":
                user = await self.uow.users.get_by_operator_code(identifier)
            else:
                user = await self.uow.users.get_by_username(identifier)

        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Incorrect identifier or password")

        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role},
        )
        return {"access_token": access_token, "token_type": "bearer"}
