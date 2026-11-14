# Demo script (5 minutes)

A walkthrough of the three cases for the viva, on the synthetic city (seed 42, as of
2026-11-13). `<site>` is `https://raktsetu.zorvx.shop` (or `http://localhost:3000` locally).

## Before you start (5 minutes before)

1. **Wake the API.** The free Render plan sleeps after 15 minutes without traffic and takes up to a
   minute to start. Open `<api>/health` and wait for `{"status":"ok"}`.
2. Open these tabs, in order:
   - Tab 1: `<site>/?group=B+&component=red_cells&lat=23.0225&lng=72.5714`
   - Tab 2: `<site>/?group=AB-&component=platelets&lat=23.2021&lng=72.7706`
   - Tab 3: `<site>/?group=O-&component=platelets&lat=22.8021&lng=72.3275`
   - Tab 4: `<site>/hospital`, logged in as `h001@hospital.raktsetu.test` / `raktsetu123`
   - Tab 5: `<site>/bank`, **not** logged in yet (you log in as the bank that receives the request)
3. Turn the screen to a phone-sized window if you want to show the mobile layout (most searches
   happen on a phone in an emergency).
4. If the data has been changed by earlier tests, reset it from your computer:
   `python -m db.seed --reset --mongo-uri "<atlas uri>"` in `backend/`, then restart the Render service.

## 1. Case 1: find blood (1 minute 30)

Tab 1: B+ red cells, at the city centre.

1. Say: *"A family needs B+ red cells. The location is set from the phone's GPS, or by tapping the map."*
2. Press **Search for B+ red cells**.
3. Point at the list: 22 banks within 25 km **by road**, nearest first. The nearest is
   **Hari Nagar Blood Centre at 1.9 km**, with units per compatible group (B+, and O+ which B+ can receive).
4. Point at the map: the route to the nearest bank is drawn along the roads.
5. Say: *"Distances are road distances from our own Dijkstra on the road graph, not straight lines.
   MongoDB only stores the data; the search runs in memory on structures we wrote."*

## 2. How it works: the Dijkstra animation (1 minute)

Tab 2: AB- platelets on the north-east edge, a rare group and a short-lived component.

1. Press **Search for AB- platelets**: only one bank has stock, **Gandhi Park Blood Centre at
   19.9 km**.
2. Press **Show how it works**. Narrate while it plays:
   - *"The 25 km circle is the cutoff."*
   - *"Each dot is a road junction, lit in the order Dijkstra settles it: a wave spreading by road
     distance, using our MinHeap."*
   - *"A bank flashes grey when it is reached without stock (Ganga Gaon at 18.3 km), green with its
     distance when it has stock."*
   - *"Then the shortest route to the nearest bank with stock is drawn, segment by segment."*
3. Mention that the search stops at 25 km: on the 60 km city it explores about 800 of 3,721
   junctions, so it stays fast however big the city is (`docs/dsa.md`).

## 3. Donor fallback and privacy (1 minute)

Tab 3: O- platelets on the south-west outskirts.

1. Press **Search for O- platelets**. Banner: *No blood bank within 25 km has O- platelets.*
2. Donors appear instead, nearest first: **Vikram S. at 8.6 km**. Point out: short name only, no
   phone number on the page.
3. Press **Show number** on Vikram S. A phone login opens: enter any number in the form
   `+91-00000-12345`, press **Send code** (the code is filled in, as no SMS provider is connected),
   then **Log in**.
4. The number appears. Say: *"Only donors who agreed to be contacted and are available are listed.
   A phone number needs a login, each view is logged, and a user can see at most 20 a day. Misuse
   can be reported to the admin."*
5. Optional: **Search wider (50 km)**.

## 4. Case 2: a hospital request (1 minute)

Tab 4, logged in as Ashok Colony General Hospital.

1. Raise a request: **B+**, **Red cells**, **2** units, patient condition **Accident**.
   Press **Raise request**.
2. It shows *In queue*, then within a few seconds *Units are reserved. Waiting for the blood bank to
   accept.* Point at the allocated bank and units (the ones closest to expiry), and the donors listed
   near the hospital.
3. Say: *"Requests wait in a max-heap keyed on urgency: an accident is 100, a planned surgery 40.
   Waiting raises the priority by 0.5 a minute, so a low-urgency request is never starved."*
4. Note the bank's name (Ashok Park Blood Centre, `b030`).

## 5. The blood bank (30 seconds)

Tab 5: log in as `b030@bank.raktsetu.test` / `raktsetu123`.

1. **Incoming hospital requests**: press **Accept and issue**. Back in tab 4 the request becomes
   *Completed*.
2. **Stock**: units by group and component, with expiring-soon units highlighted.
3. **Issue units**: issue one B+ red cells unit; it is the one closest to expiry (FEFO, a MinHeap
   keyed by expiry date). **Recent activity** shows it (a linked-list log).
4. Press **Undo last action**: the unit is back in stock (a stack of inverse actions).

## If asked: results

- `backend/simulation/results/summary.md`: 90 simulated days, traditional phone-around against
  RaktSetu. Wastage 15.4% → 12.4% with transfers; requests fulfilled 80% → 93%; time to locate 7.5 →
  4.2 minutes; distance to the bank 33 → 14 km.
- `backend/benchmarks/results/summary.md`: our heap against heapq, cutoff against full Dijkstra,
  search time by city size.

## If something goes wrong

| Problem | Fix |
|---|---|
| The page shows an error on load | The API is asleep: open `<api>/health`, wait, reload |
| "RaktSetu is not available in this area yet" | The pin is outside the city; use the tab links above |
| The hospital request stays *In queue* | The background dispatcher runs every 3 seconds; refresh once |
| A bank login says it is waiting for verification | Log in as `admin@raktsetu.test` and verify it under `/admin` |
| Numbers differ from this script | The data was changed by earlier use: reseed (see "Before you start") |
