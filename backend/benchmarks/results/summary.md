# RaktSetu benchmark results

Machine: AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD, Python 3.12.10, Windows 11. Seed 42; data as of 2026-11-13.

## Heap: push then pop n items

| n | raktsetu_minheap_ms | python_heapq_ms | ratio |
|---|---|---|---|
| 1,000 | 4.79 | 0.58 | 8.24 |
| 10,000 | 77.09 | 7.74 | 9.97 |
| 25,000 | 210.8 | 25.14 | 8.39 |
| 50,000 | 466.97 | 60.03 | 7.78 |
| 75,000 | 749.77 | 89.97 | 8.33 |
| 100,000 | 1,050.18 | 124.28 | 8.45 |

## Dijkstra: 25 km cutoff vs full search

| graph | junctions | roads | start_points | full_ms_mean | cutoff_ms_mean | full_nodes_mean | cutoff_nodes_mean | speedup | nodes_share_pct |
|---|---|---|---|---|---|---|---|---|---|
| Synthetic 60 km grid | 3,721 | 6,587 | 200 | 21.45 | 4.76 | 3,721 | 826 | 4.5 | 22.2 |
| Ahmedabad real roads | 110,226 | 143,349 | 200 | 908.66 | 433.28 | 110,172 | 52,029 | 2.1 | 47.2 |

## Search time by synthetic city size

| city | junctions | searches | median_ms | p95_ms | mean_junctions_visited | donor_fallback_pct |
|---|---|---|---|---|---|---|
| 30 km grid | 961 | 200 | 4.64 | 7.57 | 595 | 0.5 |
| 60 km grid | 3,721 | 200 | 5.96 | 9.92 | 799 | 18.5 |
| 100 km grid | 10,201 | 200 | 6.91 | 10.24 | 923 | 38.0 |

## Search time on real roads (Gujarat)

| city | junctions | searches | median_ms | p95_ms | mean_junctions_visited | donor_fallback_pct |
|---|---|---|---|---|---|---|
| Ahmedabad | 110,226 | 100 | 545.63 | 772.11 | 55,313 | 9.0 |
| Bhavnagar | 19,295 | 100 | 126.16 | 157.03 | 17,484 | 0.0 |
| Jamnagar | 24,853 | 100 | 139.3 | 173.65 | 16,598 | 3.0 |
| Junagadh | 21,411 | 100 | 92.54 | 117.15 | 11,216 | 6.0 |
| Rajkot | 45,564 | 100 | 293.84 | 352.89 | 31,112 | 9.0 |
| Surat | 105,432 | 100 | 555.27 | 643.39 | 53,374 | 11.0 |
| Vadodara | 83,571 | 100 | 423.21 | 493.57 | 41,671 | 32.0 |
