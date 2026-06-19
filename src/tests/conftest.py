import asyncio
import unittest.mock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from domain.entities import Role
from infrastructure import auth
from infrastructure.models.orm import Base, UserORM
from infrastructure.pubsub import broadcast
from main import app

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)



@pytest_asyncio.fixture(scope="function", autouse=True)
async def mock_broadcaster_init():

    if not hasattr(broadcast._backend, "_published"):  # noqa: SLF001
        broadcast._backend._published = asyncio.Queue()  # noqa: SLF001
    yield

@pytest_asyncio.fixture(scope="function", autouse=True)
async def mock_get_session(db_session):
    async def _mock():
        yield db_session

    with unittest.mock.patch("infrastructure.ioc.get_session", new=_mock):
        yield


@pytest_asyncio.fixture(scope="function")
async def db_session():
    # Setup DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        # Seed test users
        admin = UserORM(
            username="admin",
            hashed_password=auth.get_password_hash("adminpass"),
            role=Role.TECH_ADMIN
        )
        operator = UserORM(
            username="operator",
            hashed_password=auth.get_password_hash("oppass"),
            role=Role.OPERATOR,
            operator_code="OP_123"
        )
        session.add_all([admin, operator])
        await session.commit()
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def admin_token(client):
    response = await client.post("/auth/login", data={"username": "admin", "password": "adminpass"})
    return response.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def operator_token(client):
    response = await client.post("/auth/login", data={"username": "operator", "password": "oppass"})
    return response.json()["access_token"]
