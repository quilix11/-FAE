import typing
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from infrastructure.ioc import setup_ioc
from infrastructure.pubsub import broadcast
from presentation.api.exceptions import setup_exception_handlers
from presentation.api.router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> typing.AsyncGenerator[None, None]:
    await broadcast.connect()
    yield
    await broadcast.disconnect()


app = FastAPI(title="Applicator Fujikura API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_exception_handlers(app)
app.include_router(router)


setup_ioc(app)
