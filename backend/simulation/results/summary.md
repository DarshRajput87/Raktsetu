# RaktSetu simulation results

90 days, 10 runs per method (seeds 1000 to 1009), mean ± standard deviation
across runs. Bold marks the best method for each metric. Synthetic 60 km city centred on Ahmedabad
(seed 42, 2026-11-13): 30 blood banks, 40 hospitals, 3,000 donors. Total time
22 s on AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD, Python 3.12.10.

| Metric | Traditional | RaktSetu | RaktSetu + transfers |
|---|---|---|---|
| Wastage (% of units expired) | 15.37 ± 0.42 | 13.87 ± 0.45 | **12.36 ± 0.41** |
| Time to locate blood (mean) (minutes) | 7.51 ± 0.16 | 4.21 ± 0.09 | **4.20 ± 0.09** |
| Time to locate blood (90th percentile) (minutes) | 18.90 ± 1.45 | **10.10 ± 0.32** | **10.10 ± 0.32** |
| Requests fulfilled (% of requests) | 79.73 ± 0.70 | 92.60 ± 0.49 | **93.08 ± 0.54** |
| Critical requests fulfilled (% of critical requests) | 80.02 ± 0.59 | 93.18 ± 0.60 | **93.71 ± 0.47** |
| Distance to the supplying banks (km by road, per fulfilled request) | 33.24 ± 0.26 | 13.62 ± 0.33 | **13.27 ± 0.29** |
| Donor fallback (% of requests that needed donors) | n/a (no fallback) | 24.02 ± 1.09 | 23.23 ± 1.12 |
| Units transferred (per run) | 0 ± 0 | 0 ± 0 | 1498 ± 52 |
| Requests (per run) | 5575 | 5575 | 5575 |

Charts: `wastage_over_time.png` and one `metric_<name>.png` per metric. Every run is in `runs.csv`,
the means in `summary.csv`, and the day-by-day wastage in `daily_wastage.csv`.

## How to read it

- **Wastage**: units that expired during the simulation, as a share of all units available at the
  start plus every unit donated. Units still in stock at the end are not counted as wasted.
- **Time to locate**: from the request to knowing where every unit will come from, for fulfilled
  requests. Traditional: 3 minutes per phone call. RaktSetu: 1 minute to search,
  plus the wait for the next 5-minute dispatch for hospital requests, plus
  3 minutes per donor called when the fallback is needed.
- **Fulfilled**: every unit asked for was found. A request that is only partly covered counts as
  not fulfilled and its units go back into stock.
- **Critical**: patient conditions with an urgency of 80 or more (accident, delivery
  complication, dengue with low platelets).
- **Distance**: road km from the requester to each bank that supplied units, added up, for fulfilled
  requests that took units from a bank.
- **Donor fallback**: requests where the banks within 25 km could not cover the request and
  donors were contacted. The traditional method has no donor fallback.

## Model

- Each day: about 105 donations (Poisson), each one unit at a random bank between
  08:00 and 20:00, blood group from the Indian population mix, component by the usual split
  (red cells 35%, whole blood 30%, plasma 25%, platelets 10%) with its standard shelf life.
- Each day: about 38 hospital requests (1 to 4 units) and 24
  public requests (1 or 2 units) at random minutes. Public requests come from 400 fixed
  neighbourhoods. The patient condition sets the urgency and the component (dengue needs platelets,
  thalassemia red cells, and so on).
- Units past their expiry are removed at the start of each day.
- Traditional: first come, first served; the requester calls banks from the directory in random
  order and stops after 10 calls; a bank hands out random compatible units.
- RaktSetu: public requests are searched on arrival; hospital requests wait in the priority queue
  (urgency + 100-point scale with aging) and are dispatched every 5 minutes.
  Banks within 25 km by road are used nearest first, units soonest to expire first. If they
  fall short, up to 10 eligible, available, consenting donors within 25 km are
  called nearest first; each agrees with probability 0.35.
- RaktSetu + transfers: at the start of each day, each unit expiring within 2 days moves
  (once) to the nearest bank within 25 km holding fewer than 2 units of that group
  and component.
- Within a run every method sees exactly the same donations and requests.
