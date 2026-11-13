"""API test setup: a test database seeded with the generated city (seed 42,
as of 2026-11-13) and the app running in-process."""

import itertools

import httpx
import pytest
import pytest_asyncio
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from config import get_settings
from db.accounts import DEMO_PASSWORD
from db.seed import seed

_phones = itertools.count(1)


class Api:
    """The HTTP client plus the app, with login helpers."""

    def __init__(self, client: httpx.AsyncClient, app) -> None:
        self.client, self.app = client, app
        self.state = app.state.data
        self.db = app.state.db
        self.services = app.state.services

    async def otp_login(self, phone: str | None = None) -> dict:
        """Log in by OTP (a new phone number each time unless one is given)."""
        phone = phone or f"+91-00000-7{next(_phones):04d}"
        sent = (await self.client.post("/auth/otp/send", json={"phone": phone})).json()
        response = await self.client.post("/auth/otp/verify", json={"phone": phone, "otp": sent["dev_otp"]})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['token']}"}

    async def staff_login(self, email: str) -> dict:
        response = await self.client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest_asyncio.fixture(scope="module")
async def api():
    settings = get_settings()
    assert settings.db_name == "raktsetu_test"
    try:
        mongo = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)
        mongo.admin.command("ping")
    except PyMongoError:
        pytest.skip("MongoDB is not running")
    try:
        seed(mongo[settings.db_name], "output", reset=True)
    except SystemExit as exc:
        pytest.skip(str(exc))

    from api.main import app

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield Api(client, app)
