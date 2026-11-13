"""Small async reads and writes, one group per collection.

No search logic lives here: nothing is sorted or ranked by MongoDB. Dates are
stored as datetimes because MongoDB has no plain date type.
"""

from datetime import date, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase as DB


def to_mongo(doc: dict[str, Any]) -> dict[str, Any]:
    """Copy a document, turning date values into datetimes (also inside lists and dicts)."""
    return {key: _convert(value) for key, value in doc.items()}


def _convert(value: Any) -> Any:
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, dict):
        return to_mongo(value)
    if isinstance(value, list):
        return [_convert(v) for v in value]
    return value


# --- blood banks and hospitals -------------------------------------------------

async def get_bank(db: DB, bank_id: str) -> dict | None:
    return await db.blood_banks.find_one({"_id": bank_id})


async def list_banks(db: DB) -> list[dict]:
    return await db.blood_banks.find().to_list(None)


async def insert_bank(db: DB, bank: dict) -> None:
    await db.blood_banks.insert_one(to_mongo(bank))


async def update_bank(db: DB, bank_id: str, fields: dict) -> None:
    await db.blood_banks.update_one({"_id": bank_id}, {"$set": to_mongo(fields)})


async def get_hospital(db: DB, hospital_id: str) -> dict | None:
    return await db.hospitals.find_one({"_id": hospital_id})


async def update_hospital(db: DB, hospital_id: str, fields: dict) -> None:
    await db.hospitals.update_one({"_id": hospital_id}, {"$set": to_mongo(fields)})


# --- blood units ---------------------------------------------------------------

async def insert_unit(db: DB, unit: dict) -> None:
    await db.blood_units.insert_one(to_mongo(unit))


async def update_unit_status(db: DB, unit_id: str, status: str) -> None:
    await db.blood_units.update_one({"_id": unit_id}, {"$set": {"status": status}})


async def update_units_status(db: DB, unit_ids: list[str], status: str) -> None:
    if unit_ids:
        await db.blood_units.update_many({"_id": {"$in": unit_ids}}, {"$set": {"status": status}})


async def delete_unit(db: DB, unit_id: str) -> None:
    await db.blood_units.delete_one({"_id": unit_id})


# --- donors --------------------------------------------------------------------

async def get_donor(db: DB, donor_id: str) -> dict | None:
    return await db.donors.find_one({"_id": donor_id})


async def insert_donor(db: DB, donor: dict) -> None:
    await db.donors.insert_one(to_mongo(donor))


async def update_donor(db: DB, donor_id: str, fields: dict) -> None:
    await db.donors.update_one({"_id": donor_id}, {"$set": to_mongo(fields)})


# --- users ---------------------------------------------------------------------

async def get_user(db: DB, user_id: str) -> dict | None:
    return await db.users.find_one({"_id": user_id})


async def get_user_by_phone(db: DB, phone: str) -> dict | None:
    return await db.users.find_one({"phone": phone})


async def get_user_by_email(db: DB, email: str) -> dict | None:
    return await db.users.find_one({"email": email})


async def insert_user(db: DB, user: dict) -> None:
    await db.users.insert_one(to_mongo(user))


async def update_user(db: DB, user_id: str, fields: dict) -> None:
    await db.users.update_one({"_id": user_id}, {"$set": to_mongo(fields)})


# --- hospital requests ---------------------------------------------------------

async def insert_request(db: DB, request: dict) -> None:
    await db.requests.insert_one(to_mongo(request))


async def update_request(db: DB, request_id: str, fields: dict) -> None:
    await db.requests.update_one({"_id": request_id}, {"$set": to_mongo(fields)})


async def list_requests(db: DB) -> list[dict]:
    return await db.requests.find().to_list(None)


# --- logs ----------------------------------------------------------------------

async def insert_transaction(db: DB, transaction: dict) -> None:
    await db.transactions.insert_one(to_mongo(transaction))


async def list_transactions(db: DB) -> list[dict]:
    return await db.transactions.find().to_list(None)


async def insert_access_log(db: DB, entry: dict) -> None:
    await db.contact_access_logs.insert_one(to_mongo(entry))


async def count_access_logs(db: DB, viewer_id: str, since: datetime) -> int:
    return await db.contact_access_logs.count_documents({"viewer_id": viewer_id, "at": {"$gte": since}})


async def insert_misuse_report(db: DB, report: dict) -> None:
    await db.misuse_reports.insert_one(to_mongo(report))


async def list_misuse_reports(db: DB) -> list[dict]:
    return await db.misuse_reports.find().to_list(None)


# --- cities --------------------------------------------------------------------

async def list_cities(db: DB) -> list[dict]:
    return await db.cities.find().to_list(None)
