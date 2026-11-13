"""Demo login accounts for the seeded hospitals, blood banks and the system admin.

Development data only: every account uses the same password (DEMO_PASSWORD).
    admin@raktsetu.test
    b001@bank.raktsetu.test       (bank admin of bank B001)
    h001@hospital.raktsetu.test   (hospital H001)
For a real city the id prefix is part of the address, e.g. ahmedabad.b001@bank.raktsetu.test.
"""

import bcrypt
from pymongo.database import Database

DEMO_PASSWORD = "raktsetu123"


def account_email(place_id: str, kind: str) -> str:
    return f"{place_id.lower().replace(':', '.')}@{kind}.raktsetu.test"


def seed_accounts(db: Database) -> int:
    """Recreate the demo accounts. Returns how many were written."""
    password_hash = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt(rounds=10)).decode()
    users = [{"_id": "U-admin", "email": "admin@raktsetu.test", "role": "admin", "name": "System Admin"}]
    for bank in db.blood_banks.find({}, {"name": 1}):
        user_id = f"U-bank-{bank['_id']}"
        users.append({"_id": user_id, "email": account_email(bank["_id"], "bank"),
                      "role": "bank_admin", "bank_id": bank["_id"], "name": bank["name"]})
        db.blood_banks.update_one({"_id": bank["_id"]}, {"$set": {"admin_user_id": user_id}})
    for hospital in db.hospitals.find({}, {"name": 1}):
        users.append({"_id": f"U-hospital-{hospital['_id']}", "email": account_email(hospital["_id"], "hospital"),
                      "role": "hospital", "hospital_id": hospital["_id"], "name": hospital["name"]})
    for user in users:
        user.update({"password_hash": password_hash, "seeded": True})
    db.users.delete_many({"seeded": True})
    db.users.insert_many(users)
    return len(users)
