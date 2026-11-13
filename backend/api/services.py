"""Glue between the in-memory modules and MongoDB.

The rule everywhere: change memory first (modules/), then write the same change
to MongoDB through the repositories.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date

from motor.motor_asyncio import AsyncIOMotorDatabase

from config import Settings
from db import repositories as repo
from db.loaders import ensure_city_loaded
from modules import requests as request_ops
from modules import stock
from modules.auth import ContactLimiter, LogSmsSender, OtpStore, SmsSender
from modules.cities import city_for_location
from modules.dates import utcnow
from modules.state import AppState

log = logging.getLogger("raktsetu")


@dataclass
class Services:
    otp: OtpStore
    contact_limiter: ContactLimiter
    sms: SmsSender


def build_services(settings: Settings) -> Services:
    return Services(otp=OtpStore(settings.jwt_secret, settings.otp_ttl_seconds),
                    contact_limiter=ContactLimiter(settings.contact_views_per_day),
                    sms=LogSmsSender())


async def city_ready(state: AppState, db: AsyncIOMotorDatabase, lat: float, lng: float,
                     picked: str | None = None) -> str:
    """Work out the city of a location and make sure its road graph is in memory."""
    city_id = city_for_location(state.cities, lat, lng, picked)
    await ensure_city_loaded(state, db, city_id)
    return city_id


async def flush_audit(state: AppState, db: AsyncIOMotorDatabase) -> None:
    """Write the log entries recorded in memory since the last flush."""
    for entry in state.audit.take_unsaved():
        await repo.insert_transaction(db, entry)


async def save_request(db: AsyncIOMotorDatabase, request: dict) -> None:
    fields = {k: v for k, v in request.items() if k != "_id"}
    await repo.update_request(db, request["_id"], fields)


async def dispatch_requests(state: AppState, db: AsyncIOMotorDatabase, settings: Settings) -> list[dict]:
    """Serve the waiting hospital requests, most urgent first, and persist the result."""
    if state.request_queue.is_empty():
        return []
    for request in state.request_queue.waiting():
        await ensure_city_loaded(state, db, request["city_id"])
    processed = request_ops.process_queue(state, settings.today, utcnow(), settings.search_radius_km)
    for request in processed:
        for allocation in request["allocations"]:
            if allocation["status"] == "pending":
                await repo.update_units_status(db, allocation["unit_ids"], "reserved")
        await save_request(db, request)
        log.info("Request %s (%s, priority base %s) -> %s", request["_id"], request["patient_condition"],
                 request["base_score"], request["status"])
    await flush_audit(state, db)
    return processed


async def purge_expired(state: AppState, db: AsyncIOMotorDatabase, today: date) -> int:
    """Mark expired units in memory and in MongoDB."""
    expired = stock.purge_expired(state, today, utcnow())
    await repo.update_units_status(db, [u["_id"] for u in expired], "expired")
    await flush_audit(state, db)
    if expired:
        log.info("Marked %d unit(s) as expired", len(expired))
    return len(expired)


async def background_loop(state: AppState, db: AsyncIOMotorDatabase, settings: Settings) -> None:
    """Runs for the life of the app:
    - every few seconds: dispatch waiting hospital requests
    - every minute: re-key the request queue so waiting requests age
    - once a day (and at startup): purge expired units
    """
    last_purge: date | None = None
    last_rekey = utcnow()
    while True:
        try:
            if last_purge != settings.today:
                await purge_expired(state, db, settings.today)
                last_purge = settings.today
            if (utcnow() - last_rekey).total_seconds() >= 60:
                state.request_queue.rekey(utcnow())
                last_rekey = utcnow()
            await dispatch_requests(state, db, settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Background task failed; will retry")
        await asyncio.sleep(settings.request_dispatch_seconds)
