import typing
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, WebSocketException, status
from fastapi.security import OAuth2PasswordBearer

from config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict[str, typing.Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt: str = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user_payload(token: str = Depends(oauth2_scheme)) -> dict[str, typing.Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
        if user_id is None or role is None:
            raise credentials_exception
        return {"user_id": int(user_id), "role": role}
    except jwt.PyJWTError as e:
        raise credentials_exception from e


async def get_ws_user_payload(token: str) -> dict[str, typing.Any]:

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
        if user_id is None or role is None:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return {"user_id": int(user_id), "role": role}
    except jwt.PyJWTError as e:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token") from e


def require_role(required_role: str) -> typing.Callable[..., typing.Any]:
    async def role_checker(
        user_payload: dict[str, typing.Any] = Depends(get_current_user_payload),
    ) -> dict[str, typing.Any]:
        if user_payload.get("role") != required_role:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return user_payload

    return role_checker
