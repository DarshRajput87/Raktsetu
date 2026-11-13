"""RaktSetu FastAPI application."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from config import get_settings
from db.loaders import load_state
from db.mongo import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("raktsetu")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    client = connect(settings.mongo_uri)
    app.state.db = client[settings.db_name]
    app.state.data = await load_state(app.state.db)
    yield
    client.close()


app = FastAPI(title="RaktSetu API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
