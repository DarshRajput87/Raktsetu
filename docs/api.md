# RaktSetu API

Base URL: `http://localhost:8000` locally, or the Render URL once deployed. Interactive docs
with every schema are served at `/docs` (Swagger UI) and `/redoc`.

The examples below are real responses from the seeded synthetic city (seed 42, as of
2026-11-13). Long lists are cut to their first items (`...`), and tokens are shortened.

## Conventions

- **JSON in and out.** Dates are `YYYY-MM-DD`, times ISO 8601.
- **Auth:** send `Authorization: Bearer <token>`. A token comes from `/auth/otp/verify`
  (phone login) or `/auth/login` (hospital, bank and admin staff) and lasts 24 hours.
- **Roles:** `public` (anyone who logged in by OTP), `donor`, `hospital`, `bank_admin`, `admin`.
- **Errors** always have the same shape:

  ```json
  {"error": {"code": "validation_error", "message": "group: Input should be 'O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+' or 'AB-'"}}
  ```

  | Status | Codes |
  |---|---|
  | 400 | `bad_request`; a wrong, expired or unrequested OTP (`otp_not_requested`, ...) |
  | 401 | `unauthorized` (no token), `invalid_token`, `invalid_credentials` (wrong password) |
  | 403 | `forbidden` (wrong role), `not_verified` (staff account not yet verified), `contact_not_shared` |
  | 404 | `not_found` (bank, donor or request), `no_route` |
  | 409 | `already_registered`, `donor_not_eligible`, `not_enough_stock`, `nothing_pending`, `nothing_to_undo` |
  | 422 | `validation_error` (invalid input), a location outside every supported city |
  | 429 | `rate_limited`: more than 20 donor contact views today |

Endpoints:

| | Method and path | Who |
|---|---|---|
| [Health](#get-health) | `GET /health` | anyone |
| [Meta](#get-meta) | `GET /meta` | anyone |
| [Cities](#get-cities) | `GET /cities` | anyone |
| [Search](#get-search) | `GET /search` | anyone |
| [Route](#get-route) | `GET /route` | anyone |
| [Banks](#get-banks) | `GET /banks`, `GET /banks/{id}` | anyone |
| [OTP login](#post-authotpsend) | `POST /auth/otp/send`, `POST /auth/otp/verify` | anyone |
| [Staff login](#post-authlogin) | `POST /auth/login` | hospital, bank admin, admin |
| [Me](#get-authme) | `GET /auth/me` | logged in |
| [Donor contact](#get-donorsidcontact) | `GET /donors/{id}/contact` | logged in |
| [Report a donor](#post-donorsidreport) | `POST /donors/{id}/report` | logged in |
| [Donor](#post-donorsregister) | `POST /donors/register`, `GET`/`PATCH /donors/me`, `GET /donors/me/suggested-banks` | logged in / donor |
| [Hospital requests](#post-hospitalrequests) | `POST`/`GET /hospital/requests`, `GET /hospital/requests/{id}` | hospital |
| [Bank](#get-bankstock) | `/bank/stock`, `/bank/units`, `/bank/units/issue`, `/bank/requests`, `/bank/transactions`, `/bank/undo` | bank admin |
| [Admin](#get-adminplaces) | `/admin/places`, `/admin/hospitals/{id}/verify`, `/admin/banks/{id}/verify`, `/admin/reports` | admin |

---

## Public

### GET /health

Used by the host's health check.

```
GET /health
```
```json
{"status": "ok"}
```

### GET /meta

The values the frontend needs for its forms.

```
GET /meta
```
```json
{
  "today": "2026-11-13",
  "radius_km": 25.0,
  "blood_groups": ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"],
  "components": ["whole_blood", "red_cells", "platelets", "plasma"],
  "patient_conditions": {"accident": 100, "delivery_complication": 100, "dengue_low_platelets": 80,
                         "thalassemia": 75, "cancer_treatment": 65, "planned_surgery": 40, "other": 20},
  "attribution": "Road data (c) OpenStreetMap contributors"
}
```

### GET /cities

The cities with road data. A search outside every city's box returns 422.

```
GET /cities
```
```json
[
  {"id": "synthetic", "name": "Ahmedabad (synthetic grid)", "center": [23.0225, 72.5714],
   "bbox": [22.750029, 72.276149, 23.29497, 72.866651], "notes": "Development data on a fake road grid."}
]
```

### GET /search

Case 1. Banks within the radius (by road) that hold available, unexpired, compatible units,
nearest first, with the route to the nearest one. If there are none, matching donors instead,
**without phone numbers**.

| Query | Required | Meaning |
|---|---|---|
| `group` | yes | Recipient blood group, e.g. `B+` |
| `component` | yes | `whole_blood`, `red_cells`, `platelets` or `plasma` |
| `lat`, `lng` | yes | Where the patient is |
| `radius` | no | km of road, default 25, at most 100 |
| `city` | no | City id, if the user picked one |
| `trace` | no | `true` also returns Dijkstra's visit order for the animation |

**Banks found** (demo case 1):

```
GET /search?group=B+&component=red_cells&lat=23.0225&lng=72.5714
```
```json
{
  "city_id": "synthetic",
  "group": "B+",
  "component": "red_cells",
  "radius_km": 25.0,
  "compatible_groups": ["B+", "B-", "O+", "O-"],
  "start_node": "N030030",
  "start": [23.021693, 72.57343],
  "banks": [
    {"bank_id": "B022", "name": "Hari Nagar Blood Centre", "area": "Hari Nagar", "lat": 23.022681,
     "lng": 72.589861, "phone": "+91-00000-00121", "node_id": "N030032", "distance_km": 1.935,
     "est_travel_min": 2.6, "units": 21, "units_by_group": {"B+": 12, "O+": 9}},
    {"bank_id": "B002", "name": "Kamal Nagar Blood Centre", "distance_km": 7.12, "est_travel_min": 18.2,
     "units": 19, "units_by_group": {"B+": 9, "O+": 10}, "...": "..."}
  ],
  "route": [[23.021693, 72.57343], [23.024504, 72.580604], [23.022681, 72.589861]],
  "route_bank_id": "B022",
  "donors": [],
  "junctions_visited": 1108
}
```

**One far bank, with the trace** (demo case 2):

```
GET /search?group=AB-&component=platelets&lat=23.2021&lng=72.7706&trace=true
```
```json
{
  "banks": [{"bank_id": "B006", "name": "Gandhi Park Blood Centre", "distance_km": 19.931,
             "est_travel_min": 47.4, "units": 2, "units_by_group": {"B-": 2}, "...": "..."}],
  "route_bank_id": "B006",
  "junctions_visited": 756,
  "trace": [
    {"node": "N050050", "lat": 23.202367, "lng": 72.768636, "dist_km": 0.0, "parent": null},
    {"node": "N050051", "lat": 23.202156, "lng": 72.775466, "dist_km": 0.847, "parent": "N050050"},
    "... 754 more, in the order Dijkstra settled them"
  ],
  "banks_reached": [
    {"bank_id": "B016", "node": "N046038", "lat": 23.166458, "lng": 72.64788, "dist_km": 18.25, "has_stock": false},
    {"bank_id": "B006", "node": "N038043", "lat": 23.095309, "lng": 72.696059, "dist_km": 19.931, "has_stock": true}
  ],
  "...": "the other fields as above"
}
```

**Donor fallback** (demo case 3):

```
GET /search?group=O-&component=platelets&lat=22.8021&lng=72.3275
```
```json
{
  "compatible_groups": ["O-"],
  "banks": [],
  "route": [],
  "donors": [
    {"donor_id": "D00182", "name": "Vikram S.", "blood_group": "O-", "lat": 22.869358, "lng": 72.33553, "distance_km": 8.598},
    {"donor_id": "D01187", "name": "Amit P.", "blood_group": "O-", "lat": 22.913674, "lng": 72.279897, "distance_km": 18.182}
  ],
  "junctions_visited": 538,
  "...": "the other fields as above"
}
```

### GET /route

Shortest road route from a location to one bank (when the user picks a bank other than the nearest).

```
GET /route?lat=23.0225&lng=72.5714&bank_id=B001
```
```json
{"bank_id": "B001", "distance_km": 18.971, "est_travel_min": 50.5,
 "route": [[23.021693, 72.57343], [23.014445, 72.573525], "... 18 more points"]}
```

### GET /banks

All verified banks, for the map pins. `?city=<id>` limits it to one city.

```
GET /banks
```
```json
[
  {"id": "B001", "name": "Indira Gaon Blood Centre", "area": "Indira Gaon", "city_id": "synthetic",
   "lat": 22.942722, "lng": 72.669038, "phone": "+91-00000-00100", "verified": true},
  "... 29 more"
]
```

### GET /banks/{id}

One bank with its current stock by group and component.

```
GET /banks/B001
```
```json
{
  "id": "B001", "name": "Indira Gaon Blood Centre", "area": "Indira Gaon", "city_id": "synthetic",
  "lat": 22.942722, "lng": 72.669038, "phone": "+91-00000-00100", "verified": true,
  "stock": [
    {"blood_group": "O+", "component": "plasma", "units": 9, "earliest_expiry": "2026-11-23", "expiring_soon": 0},
    {"blood_group": "B+", "component": "plasma", "units": 6, "earliest_expiry": "2026-11-15", "expiring_soon": 1},
    "... 19 more"
  ]
}
```

---

## Authentication

### POST /auth/otp/send

Sends a 6-digit code that is valid for 5 minutes. No SMS provider is connected yet, so in
development (or with `SHOW_OTP=true`) the code comes back as `dev_otp`; otherwise it is `null`.

```
POST /auth/otp/send
{"phone": "+91-00000-12345"}
```
```json
{"sent": true, "expires_in_seconds": 300, "dev_otp": "459269"}
```

### POST /auth/otp/verify

Checks the code. The first login creates an account with the role `public`.

```
POST /auth/otp/verify
{"phone": "+91-00000-12345", "otp": "459269"}
```
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5...",
  "user": {"id": "U-59be9ea35323", "role": "public", "name": null, "phone": "+91-00000-12345",
           "email": null, "donor_id": null, "bank_id": null, "hospital_id": null}
}
```

Wrong code, or none was requested: `400`

```json
{"error": {"code": "otp_not_requested", "message": "Request a code for this phone number first."}}
```

### POST /auth/login

Email and password login for verified hospitals, bank admins and the system admin. The seeded
demo accounts all use the password `raktsetu123`: `admin@raktsetu.test`,
`b001@bank.raktsetu.test` ... `b030@...`, `h001@hospital.raktsetu.test` ... `h040@...`.

```
POST /auth/login
{"email": "h001@hospital.raktsetu.test", "password": "raktsetu123"}
```
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5...",
  "user": {"id": "U-hospital-H001", "role": "hospital", "name": "Ashok Colony General Hospital",
           "phone": null, "email": "h001@hospital.raktsetu.test", "donor_id": null, "bank_id": null,
           "hospital_id": "H001"}
}
```

Wrong password: `401 {"error": {"code": "invalid_credentials", "message": "Wrong email or password."}}`

### GET /auth/me

```
GET /auth/me
Authorization: Bearer <token>
```
```json
{"id": "U-59be9ea35323", "role": "public", "name": null, "phone": "+91-00000-12345", "email": null,
 "donor_id": null, "bank_id": null, "hospital_id": null}
```

---

## Donor contact and reports

### GET /donors/{id}/contact

The only endpoint that returns a donor's phone number. Login required; only donors who are
available and gave consent; at most 20 views per user per day; every view is written to
`contact_access_logs`.

```
GET /donors/D00182/contact
Authorization: Bearer <token>
```
```json
{"donor_id": "D00182", "name": "Vikram Sharma", "blood_group": "O-", "phone": "+91-00000-10181", "views_left_today": 19}
```

No token: `401 {"error": {"code": "unauthorized", "message": "Please log in to continue."}}`.
Over the limit: `429` with code `rate_limited`.

### POST /donors/{id}/report

Report misuse (for example a donor asking for money). Admins see it under `/admin/reports`.

```
POST /donors/D00182/report
Authorization: Bearer <token>
{"reason": "Asked for money"}
```
```json
{"id": "M-6956b274998c", "donor_id": "D00182", "reporter_id": "U-59be9ea35323", "reporter_role": "public",
 "reason": "Asked for money", "status": "open", "at": "2026-11-14T01:38:41.137761"}
```

---

## Donor (Case 3)

### POST /donors/register

Any logged-in user can register as a donor. Eligibility is computed (age 18-65, no health flags,
90 days since the last donation for men, 120 for women). Without `linked_bank_id` the nearest
bank by road is chosen. The response carries a new token, because the role is now `donor`.

```
POST /donors/register
Authorization: Bearer <token>
{"name": "Asha Mehta", "age": 29, "gender": "F", "blood_group": "O+", "lat": 23.03, "lng": 72.58,
 "health_checklist": {"recent_illness": false, "recent_surgery": false, "on_medication": false, "chronic_condition": false},
 "contact_consent": true, "available": true}
```
```json
{
  "donor": {
    "id": "D-3C38C25378", "name": "Asha Mehta", "age": 29, "gender": "F", "blood_group": "O+",
    "phone": "+91-00000-12345", "city_id": "synthetic", "lat": 23.03, "lng": 72.58,
    "linked_bank_id": "B022", "linked_bank_name": "Hari Nagar Blood Centre",
    "last_donation_date": null, "next_eligible_date": null,
    "health_checklist": {"recent_illness": false, "recent_surgery": false, "on_medication": false, "chronic_condition": false},
    "eligible": true, "eligibility_reasons": [], "available": true, "contact_consent": true, "donations": []
  },
  "token": "eyJhbGciOiJIUzI1NiIsInR5...",
  "user": {"id": "U-59be9ea35323", "role": "donor", "name": "Asha Mehta", "donor_id": "D-3C38C25378", "...": "..."}
}
```

### GET /donors/me

The donor's own record, including donation history (same shape as `donor` above).

### PATCH /donors/me

Change availability, details or the linked bank. Send only the fields that change.

```
PATCH /donors/me
Authorization: Bearer <donor token>
{"available": false}
```
```json
{"id": "D-3C38C25378", "name": "Asha Mehta", "available": false, "eligible": true, "...": "the rest of the donor"}
```

### GET /donors/me/suggested-banks

The 5 nearest banks by road distance, for choosing a linked bank.

```json
[
  {"id": "B022", "name": "Hari Nagar Blood Centre", "area": "Hari Nagar", "city_id": "synthetic",
   "lat": 23.022681, "lng": 72.589861, "phone": "+91-00000-00121", "verified": true, "distance_km": 1.716},
  {"id": "B002", "name": "Kamal Nagar Blood Centre", "distance_km": 7.163, "...": "..."},
  "... 3 more"
]
```

---

## Hospital (Case 2)

### POST /hospital/requests

Raises a request. It joins the priority queue (urgency from the patient condition, plus an aging
bonus while it waits) and is served within a few seconds by the background dispatcher: units are
reserved from the nearest banks, soonest to expire first. So it comes back `queued`.

`patient_condition` is one of `accident`, `delivery_complication`, `dengue_low_platelets`,
`thalassemia`, `cancer_treatment`, `planned_surgery`, `other`.

```
POST /hospital/requests
Authorization: Bearer <hospital token>
{"group": "B+", "component": "red_cells", "units_needed": 2, "patient_condition": "accident"}
```
```json
{
  "id": "R-5372DA99B2", "hospital_id": "H001", "hospital_name": "Ashok Colony General Hospital",
  "blood_group": "B+", "component": "red_cells", "units_needed": 2, "units_allocated": 0,
  "patient_condition": "accident", "base_score": 100, "priority": 100.0, "status": "queued",
  "created_at": "2026-11-14T01:38:41.289020", "processed_at": null, "sequence": null,
  "allocations": [], "donor_suggestions": []
}
```

### GET /hospital/requests and GET /hospital/requests/{id}

The hospital's requests, newest first, or one request. `status` is `queued`, `allocated` (units
reserved, waiting for the banks), `completed` (every bank accepted), `partial` or `unfulfilled`.
Matching donors near the hospital are always listed.

```
GET /hospital/requests/R-5372DA99B2
Authorization: Bearer <hospital token>
```
```json
{
  "id": "R-5372DA99B2", "status": "allocated", "units_needed": 2, "units_allocated": 2,
  "priority": 100.0, "processed_at": "2026-11-14T01:38:41.292020", "sequence": 1,
  "allocations": [
    {"bank_id": "B030", "bank_name": "Ashok Park Blood Centre", "distance_km": 4.012,
     "units": [{"unit_id": "U0003200", "blood_group": "B+", "expires_on": "2026-11-13"},
               {"unit_id": "U0003203", "blood_group": "B+", "expires_on": "2026-11-18"}],
     "status": "pending", "bank_phone": "+91-00000-00129"}
  ],
  "donor_suggestions": [
    {"donor_id": "D00188", "name": "Simran P.", "blood_group": "O+", "distance_km": 0.99},
    "... 19 more"
  ],
  "...": "the other fields as above"
}
```

With a non-hospital token: `403 {"error": {"code": "forbidden", "message": "This action needs the role: hospital."}}`

---

## Blood bank admin (Case 4)

Every bank endpoint works on the admin's own bank only.

### GET /bank/stock

```
GET /bank/stock
Authorization: Bearer <bank token>
```
```json
{
  "bank": {"id": "B030", "name": "Ashok Park Blood Centre", "...": "..."},
  "today": "2026-11-13",
  "total_units": 64,
  "rows": [
    {"blood_group": "O+", "component": "red_cells", "units": 8, "earliest_expiry": "2026-11-17", "expiring_soon": 0},
    "... 17 more"
  ],
  "expiring_soon": [
    {"id": "U0003135", "bank_id": "B030", "blood_group": "B+", "component": "whole_blood",
     "collected_on": "2026-10-10", "expires_on": "2026-11-14", "status": "available", "donor_id": null},
    "... 5 more"
  ]
}
```

### POST /bank/units

Adds a unit. With `donor_id` it records that donor's donation (the group comes from the donor,
the eligibility rules are checked (`409 donor_not_eligible` if they fail), and the donor's last donation date is updated).

```
POST /bank/units
Authorization: Bearer <bank token>
{"component": "red_cells", "blood_group": "B+"}
```
```json
{"id": "U-AAE0AF6CA3", "bank_id": "B030", "blood_group": "B+", "component": "red_cells",
 "collected_on": "2026-11-13", "expires_on": "2026-12-25", "status": "available", "donor_id": null}
```

### POST /bank/units/issue

Issues units first-expired-first-out, exact group before other compatible groups.

```
POST /bank/units/issue
Authorization: Bearer <bank token>
{"group": "B+", "component": "red_cells", "count": 1}
```
```json
{"issued": [{"id": "U0003139", "bank_id": "B030", "blood_group": "B+", "component": "red_cells",
             "collected_on": "2026-10-14", "expires_on": "2026-11-25", "status": "issued", "donor_id": null}]}
```

### GET /bank/requests

Hospital requests with units reserved at this bank: pending first, most urgent first.

```json
[
  {"request_id": "R-5372DA99B2", "hospital_name": "Ashok Colony General Hospital", "blood_group": "B+",
   "component": "red_cells", "patient_condition": "accident", "base_score": 100,
   "created_at": "2026-11-14T01:38:41.289020",
   "units": [{"unit_id": "U0003200", "blood_group": "B+", "expires_on": "2026-11-13"},
             {"unit_id": "U0003203", "blood_group": "B+", "expires_on": "2026-11-18"}],
   "distance_km": 4.012, "status": "pending"}
]
```

### PATCH /bank/requests/{id}

`accept` issues the reserved units. `reject` puts them back in stock, and the request rejoins
the queue to look for units at other banks (this one is skipped).

```
PATCH /bank/requests/R-5372DA99B2
Authorization: Bearer <bank token>
{"action": "accept"}
```
```json
{"request_id": "R-5372DA99B2", "status": "accepted", "...": "the rest as in GET /bank/requests"}
```

### GET /bank/transactions

The bank's log (our LinkedList), newest first. `?limit=` from 1 to 500, default 50.

```
GET /bank/transactions?limit=5
Authorization: Bearer <bank token>
```
```json
[
  {"id": "T20261114013841-000004", "action": "issued", "unit_ids": ["U0003200", "U0003203"],
   "actor_id": "U-bank-B030", "at": "2026-11-14T01:38:41.415905", "details": {"request_id": "R-5372DA99B2"}},
  {"id": "T20261114013841-000003", "action": "issued", "unit_ids": ["U0003139"],
   "actor_id": "U-bank-B030", "at": "2026-11-14T01:38:41.401838", "details": {"blood_group": "B+", "component": "red_cells"}},
  "... 2 more"
]
```

### POST /bank/undo

Undoes this admin's most recent add or issue (our Stack of inverse actions). `409` when there is
nothing left to undo.

```
POST /bank/undo
Authorization: Bearer <bank token>
```
```json
{"undone": "issue 1 B+ red cells unit(s)", "can_undo_more": true}
```

---

## System admin

### GET /admin/places

Every bank and hospital, unverified ones first.

```json
[
  {"id": "B030", "name": "Ashok Park Blood Centre", "area": "Ashok Park", "city_id": "synthetic",
   "lat": 22.852838, "lng": 72.532596, "phone": "+91-00000-00129", "verified": true, "kind": "bank"},
  "... 69 more"
]
```

### PATCH /admin/hospitals/{id}/verify and PATCH /admin/banks/{id}/verify

`{"verified": false}` hides a bank from search and blocks that place's staff login (`403 not_verified`).

```
PATCH /admin/banks/B002/verify
Authorization: Bearer <admin token>
{"verified": true}
```
```json
{"id": "B002", "name": "Kamal Nagar Blood Centre", "area": "Kamal Nagar", "city_id": "synthetic",
 "lat": 22.985388, "lng": 72.601712, "phone": "+91-00000-00101", "verified": true, "kind": "bank"}
```

### GET /admin/reports

Misuse reports, newest first.

```json
[
  {"id": "M-6956b274998c", "donor_id": "D00182", "reporter_id": "U-59be9ea35323", "reporter_role": "public",
   "reason": "Asked for money", "status": "open", "at": "2026-11-14T01:38:41.137000"}
]
```
