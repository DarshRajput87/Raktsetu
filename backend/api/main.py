"""RaktSetu FastAPI application."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.errors import install_error_handlers
from api.routers import admin, auth, bank, donors, hospital, public
from api.services import background_loop, build_services
from config import get_settings
from db.loaders import load_state
from db.mongo import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("raktsetu")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: connect to MongoDB and load it into memory. Shutdown: stop the
    background loop and close the connection."""
    settings = get_settings()
    client = connect(settings.mongo_uri)
    app.state.db = client[settings.db_name]
    app.state.data = await load_state(app.state.db, settings.city_cache_capacity)
    app.state.services = build_services(settings)
    task = None
    if settings.background_tasks:
        task = asyncio.create_task(background_loop(app.state.data, app.state.db, settings))
    yield
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    client.close()


app = FastAPI(
    title="RaktSetu API",
    version="1.0.0",
    description="Finds the nearest blood bank with compatible stock by shortest-path search, "
                "and falls back to matching donors. Road data (c) OpenStreetMap contributors.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in get_settings().frontend_origin.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
for module in (auth, public, donors, hospital, bank, admin):
    app.include_router(module.router)


@app.get("/health", tags=["public"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
