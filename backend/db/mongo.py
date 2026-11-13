"""Async MongoDB connection (Motor). Opened in the FastAPI lifespan, closed on shutdown."""

from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


def connect(mongo_uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)


def get_db(request: Request) -> AsyncIOMotorDatabase:
    """FastAPI dependency: the database opened at startup."""
    return request.app.state.db
