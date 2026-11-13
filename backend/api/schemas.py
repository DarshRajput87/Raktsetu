"""Pydantic request and response models."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

BloodGroup = Literal["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]
Component = Literal["whole_blood", "red_cells", "platelets", "plasma"]
Condition = Literal["accident", "delivery_complication", "dengue_low_platelets", "thalassemia",
                    "cancer_treatment", "planned_surgery", "other"]
PHONE_PATTERN = r"^\+?[0-9][0-9\- ]{8,16}[0-9]$"


class Message(BaseModel):
    message: str


# --- auth ----------------------------------------------------------------------

class OtpSendIn(BaseModel):
    phone: str = Field(pattern=PHONE_PATTERN, examples=["+91-00000-12345"])


class OtpSendOut(BaseModel):
    sent: bool
    expires_in_seconds: int
    dev_otp: str | None = Field(None, description="Only in development mode: the code that was 'sent'.")


class OtpVerifyIn(BaseModel):
    phone: str = Field(pattern=PHONE_PATTERN)
    otp: str = Field(pattern=r"^[0-9]{6}$")


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    role: str
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    donor_id: str | None = None
    bank_id: str | None = None
    hospital_id: str | None = None


class TokenOut(BaseModel):
    token: str
    user: UserOut


# --- public --------------------------------------------------------------------

class CityOut(BaseModel):
    id: str
    name: str
    center: list[float]
    bbox: list[float]
    notes: str | None = None


class BankOut(BaseModel):
    id: str
    name: str
    area: str = ""
    city_id: str
    lat: float
    lng: float
    phone: str
    verified: bool = True


class StockRow(BaseModel):
    blood_group: str
    component: str
    units: int
    earliest_expiry: date
    expiring_soon: int


class BankDetailOut(BankOut):
    stock: list[StockRow]


class ContactOut(BaseModel):
    donor_id: str
    name: str
    blood_group: str
    phone: str
    views_left_today: int


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ReportOut(BaseModel):
    id: str
    donor_id: str
    reporter_id: str
    reporter_role: str
    reason: str
    status: str
    at: datetime


# --- donors --------------------------------------------------------------------

class HealthChecklist(BaseModel):
    recent_illness: bool = False
    recent_surgery: bool = False
    on_medication: bool = False
    chronic_condition: bool = False


class DonorRegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    age: int = Field(ge=1, le=120)
    gender: Literal["M", "F"]
    blood_group: BloodGroup
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    health_checklist: HealthChecklist = HealthChecklist()
    last_donation_date: date | None = None
    contact_consent: bool = False
    available: bool = True
    linked_bank_id: str | None = None


class DonorUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=80)
    age: int | None = Field(None, ge=1, le=120)
    gender: Literal["M", "F"] | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    health_checklist: HealthChecklist | None = None
    contact_consent: bool | None = None
    available: bool | None = None
    linked_bank_id: str | None = None


class DonationOut(BaseModel):
    date: date
    bank_id: str
    bank_name: str | None = None
    component: str
    unit_id: str


class DonorOut(BaseModel):
    id: str
    name: str
    age: int
    gender: str
    blood_group: str
    phone: str
    city_id: str
    lat: float
    lng: float
    linked_bank_id: str | None
    linked_bank_name: str | None = None
    last_donation_date: date | None
    next_eligible_date: date | None = None
    health_checklist: dict[str, bool]
    eligible: bool
    eligibility_reasons: list[str] = []
    available: bool
    contact_consent: bool
    donations: list[DonationOut] = []


class DonorRegisterOut(BaseModel):
    donor: DonorOut
    token: str = Field(description="A new token: the account's role is now 'donor'.")
    user: UserOut


class SuggestedBank(BankOut):
    distance_km: float


# --- hospital requests ---------------------------------------------------------

class RequestIn(BaseModel):
    group: BloodGroup
    component: Component
    units_needed: int = Field(ge=1, le=50)
    patient_condition: Condition


class AllocatedUnit(BaseModel):
    unit_id: str
    blood_group: str
    expires_on: date


class AllocationOut(BaseModel):
    bank_id: str
    bank_name: str
    distance_km: float
    units: list[AllocatedUnit]
    status: str
    bank_phone: str | None = None


class DonorSuggestion(BaseModel):
    donor_id: str
    name: str
    blood_group: str
    distance_km: float


class RequestOut(BaseModel):
    id: str
    hospital_id: str
    hospital_name: str
    blood_group: str
    component: str
    units_needed: int
    units_allocated: int
    patient_condition: str
    base_score: int
    priority: float = Field(description="Urgency plus the aging bonus, right now.")
    status: str
    created_at: datetime
    processed_at: datetime | None
    sequence: int | None = Field(description="Order in which the queue served this request.")
    allocations: list[AllocationOut]
    donor_suggestions: list[DonorSuggestion]


# --- bank admin ----------------------------------------------------------------

class UnitOut(BaseModel):
    id: str
    bank_id: str
    blood_group: str
    component: str
    collected_on: date | None
    expires_on: date
    status: str
    donor_id: str | None = None


class StockOut(BaseModel):
    bank: BankOut
    today: date
    total_units: int
    rows: list[StockRow]
    expiring_soon: list[UnitOut]


class AddUnitIn(BaseModel):
    component: Component
    blood_group: BloodGroup | None = Field(None, description="Not needed when donor_id is given.")
    donor_id: str | None = Field(None, description="Records the unit as this donor's donation.")


class IssueIn(BaseModel):
    group: BloodGroup
    component: Component
    count: int = Field(ge=1, le=100)


class IssueOut(BaseModel):
    issued: list[UnitOut]


class BankRequestOut(BaseModel):
    request_id: str
    hospital_name: str
    blood_group: str
    component: str
    patient_condition: str
    base_score: int
    created_at: datetime
    units: list[AllocatedUnit]
    distance_km: float
    status: str


class DecisionIn(BaseModel):
    action: Literal["accept", "reject"]


class TransactionOut(BaseModel):
    id: str
    action: str
    unit_ids: list[str]
    actor_id: str | None
    at: datetime
    details: dict


class UndoOut(BaseModel):
    undone: str
    can_undo_more: bool


# --- admin ---------------------------------------------------------------------

class VerifyIn(BaseModel):
    verified: bool = True


class PlaceOut(BankOut):
    kind: str
