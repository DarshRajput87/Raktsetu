"""Phase 4: OTP login, role guards and the donor-contact safeguards."""

from datetime import datetime, timedelta

from modules.auth import ContactLimiter, OtpStore

T0 = datetime(2026, 11, 13, 10, 0, 0)


# --- the rules themselves, with an injected clock --------------------------------

def test_otp_store_rules():
    store = OtpStore("secret", ttl_seconds=300, max_attempts=3)
    otp = store.issue("+91-00000-1", T0)
    assert len(otp) == 6 and otp.isdigit()
    assert otp not in str(store._codes)                               # stored hashed
    wrong = "000000" if otp != "000000" else "111111"
    assert store.verify("+91-00000-1", wrong, T0) == OtpStore.WRONG
    assert store.verify("+91-00000-2", otp, T0) == OtpStore.MISSING   # other phone
    assert store.verify("+91-00000-1", otp, T0 + timedelta(seconds=299)) == OtpStore.OK
    assert store.verify("+91-00000-1", otp, T0) == OtpStore.MISSING   # single use


def test_otp_expires_after_five_minutes():
    store = OtpStore("secret", ttl_seconds=300)
    otp = store.issue("+91-00000-1", T0)
    assert store.verify("+91-00000-1", otp, T0 + timedelta(seconds=301)) == OtpStore.EXPIRED
    assert store.verify("+91-00000-1", otp, T0) == OtpStore.MISSING


def test_otp_locks_after_too_many_wrong_attempts():
    store = OtpStore("secret", max_attempts=3)
    otp = store.issue("+91-00000-1", T0)
    wrong = "000000" if otp != "000000" else "111111"
    for _ in range(3):
        assert store.verify("+91-00000-1", wrong, T0) == OtpStore.WRONG
    assert store.verify("+91-00000-1", otp, T0) == OtpStore.LOCKED


def test_contact_limiter_resets_each_day():
    limiter = ContactLimiter(limit=2)
    day1, day2 = T0.date(), T0.date() + timedelta(days=1)
    assert limiter.allow("u1", day1) and limiter.allow("u1", day1)
    assert not limiter.allow("u1", day1) and limiter.remaining("u1", day1) == 0
    assert limiter.allow("u2", day1)                    # per user
    assert limiter.allow("u1", day2) and limiter.remaining("u1", day2) == 1


# --- through the API -------------------------------------------------------------

async def test_otp_login_creates_a_public_user(api):
    phone = "+91-00000-70001"
    sent = await api.client.post("/auth/otp/send", json={"phone": phone})
    assert sent.status_code == 200 and sent.json()["expires_in_seconds"] == 300
    verified = await api.client.post("/auth/otp/verify", json={"phone": phone, "otp": sent.json()["dev_otp"]})
    body = verified.json()
    assert verified.status_code == 200 and body["user"]["role"] == "public" and body["user"]["phone"] == phone
    me = await api.client.get("/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.json()["id"] == body["user"]["id"]
    # A second login with the same phone is the same account.
    again = await api.otp_login(phone)
    assert (await api.client.get("/auth/me", headers=again)).json()["id"] == body["user"]["id"]


async def test_wrong_and_expired_otp(api):
    phone = "+91-00000-70002"
    otp = (await api.client.post("/auth/otp/send", json={"phone": phone})).json()["dev_otp"]
    wrong = "000000" if otp != "000000" else "111111"
    response = await api.client.post("/auth/otp/verify", json={"phone": phone, "otp": wrong})
    assert response.status_code == 400 and response.json()["error"]["code"] == "wrong_otp"

    original = api.services.otp._ttl
    api.services.otp._ttl = timedelta(seconds=-1)        # codes are born expired
    try:
        otp = (await api.client.post("/auth/otp/send", json={"phone": phone})).json()["dev_otp"]
        response = await api.client.post("/auth/otp/verify", json={"phone": phone, "otp": otp})
    finally:
        api.services.otp._ttl = original
    assert response.status_code == 400 and response.json()["error"]["code"] == "otp_expired"

    response = await api.client.post("/auth/otp/send", json={"phone": "not a phone"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "validation_error"


async def test_staff_login_and_role_guard(api):
    response = await api.client.post("/auth/login", json={"email": "b001@bank.raktsetu.test", "password": "nope"})
    assert response.status_code == 401 and response.json()["error"]["code"] == "invalid_credentials"

    bank = await api.staff_login("b001@bank.raktsetu.test")
    assert (await api.client.get("/bank/stock", headers=bank)).status_code == 200
    # A bank admin is not a hospital or a system admin.
    for path in ("/hospital/requests", "/admin/reports"):
        response = await api.client.get(path, headers=bank)
        assert response.status_code == 403 and response.json()["error"]["code"] == "forbidden"

    public = await api.otp_login()
    assert (await api.client.get("/bank/stock", headers=public)).status_code == 403
    response = await api.client.get("/bank/stock")
    assert response.status_code == 401 and response.json()["error"]["code"] == "unauthorized"
    response = await api.client.get("/bank/stock", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401 and response.json()["error"]["code"] == "invalid_token"


async def test_unverified_bank_cannot_log_in(api):
    admin = await api.staff_login("admin@raktsetu.test")
    response = await api.client.patch("/admin/banks/B030/verify", json={"verified": False}, headers=admin)
    assert response.status_code == 200 and response.json()["verified"] is False
    response = await api.client.post("/auth/login", json={"email": "b030@bank.raktsetu.test",
                                                          "password": "raktsetu123"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "not_verified"
    await api.client.patch("/admin/banks/B030/verify", json={"verified": True}, headers=admin)
    await api.staff_login("b030@bank.raktsetu.test")


def sharing_donors(api):
    return [d for d in api.state.donors_by_id.values() if d["contact_consent"] and d["available"]]


async def test_contact_needs_login_and_is_logged(api):
    donor = sharing_donors(api)[0]
    response = await api.client.get(f"/donors/{donor['_id']}/contact")
    assert response.status_code == 401

    user = await api.otp_login()
    user_id = (await api.client.get("/auth/me", headers=user)).json()["id"]
    response = await api.client.get(f"/donors/{donor['_id']}/contact", headers=user)
    assert response.status_code == 200
    assert response.json()["phone"] == donor["phone"] and response.json()["views_left_today"] == 19
    logs = await api.db.contact_access_logs.find({"viewer_id": user_id}).to_list(None)
    assert len(logs) == 1 and logs[0]["donor_id"] == donor["_id"] and logs[0]["at"] is not None

    assert (await api.client.get("/donors/NOPE/contact", headers=user)).status_code == 404


async def test_contact_only_for_consenting_available_donors(api):
    user = await api.otp_login()
    no_consent = next(d for d in api.state.donors_by_id.values() if not d["contact_consent"])
    unavailable = next(d for d in api.state.donors_by_id.values() if d["contact_consent"] and not d["available"])
    for donor in (no_consent, unavailable):
        response = await api.client.get(f"/donors/{donor['_id']}/contact", headers=user)
        assert response.status_code == 403 and response.json()["error"]["code"] == "contact_not_shared"
        assert "phone" not in response.text


async def test_contact_rate_limit(api):
    user = await api.otp_login()
    user_id = (await api.client.get("/auth/me", headers=user)).json()["id"]
    donors = sharing_donors(api)[:21]
    for donor in donors[:20]:
        assert (await api.client.get(f"/donors/{donor['_id']}/contact", headers=user)).status_code == 200
    response = await api.client.get(f"/donors/{donors[20]['_id']}/contact", headers=user)
    assert response.status_code == 429 and response.json()["error"]["code"] == "rate_limited"
    assert "limit of 20" in response.json()["error"]["message"]
    assert await api.db.contact_access_logs.count_documents({"viewer_id": user_id}) == 20   # the 21st is not logged
    # Another user is not affected.
    other = await api.otp_login()
    assert (await api.client.get(f"/donors/{donors[0]['_id']}/contact", headers=other)).status_code == 200


async def test_misuse_report(api):
    user = await api.otp_login()
    donor = sharing_donors(api)[0]
    assert (await api.client.post(f"/donors/{donor['_id']}/report", json={"reason": "spam calls"})).status_code == 401
    response = await api.client.post(f"/donors/{donor['_id']}/report", json={"reason": "Wrong number listed"},
                                     headers=user)
    assert response.status_code == 201 and response.json()["status"] == "open"
    admin = await api.staff_login("admin@raktsetu.test")
    reports = (await api.client.get("/admin/reports", headers=admin)).json()
    assert reports[0]["reason"] == "Wrong number listed" and reports[0]["donor_id"] == donor["_id"]
    assert (await api.client.post("/donors/NOPE/report", json={"reason": "abc"}, headers=user)).status_code == 404
