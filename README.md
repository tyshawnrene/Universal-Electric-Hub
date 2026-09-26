# Gridlock — Cross-Utility Coordination Finder

Compares planned/under-construction projects from two neighboring
utilities (modeled on Dominion Energy South Carolina and Georgia Power)
and flags pairs of projects that are:

1. **Geographically close** (within a configurable mile radius, default
   25mi) — the primary signal.
2. **Also overlapping in build timeline** — a secondary signal layered on
   top, used to rank the geographic matches.

Only cross-utility pairs count — two projects from the same utility being
close together isn't a coordination opportunity here.

## Setup

```bash
pip install -r requirements.txt
```

## Get data

**Mock data (default, good for demoing the logic immediately):**

```bash
python generate_mock_data.py
```

Generates ~58 projects split between two fictional utilities ("DESC" and
"GPC") scattered along a mock SC/GA border region, with a handful of
deliberately seeded true overlaps (close + same build window) and a couple
of partial overlaps (close but different timing) so you can see both
signals working independently in the demo.

**Real data (what the challenge actually wants):**

This challenge is scored on using _real_ public planning data — Dominion
Energy South Carolina's SCRTP filings and Georgia Power's 10-Year
Transmission Plan (embedded in their IRP). Pulling and geocoding that data
is manual work specific to each utility's filing format, so it's
intentionally not automated here — see the challenge's companion
`Finding_Real_Locations_Guide` for how to extract coordinates and dates
from the real filings. Once you have it, format it to match the schema
below and drop it in as `data/projects.csv`, or upload it from the
dashboard's sidebar.

`fetch_osm_data.py` (from an earlier iteration of this project) can pull
generic "under construction" power infrastructure from OpenStreetMap, but
it does NOT reliably attribute projects to a specific utility, so it's at
best a way to sanity-check coordinates — not a substitute for the real
filings.

## Required CSV schema

```
id, name, utility, type, status, lat, lon,
capacity_mw, voltage_kv, length_miles,
start_date, end_date, owner
```

- `utility`: short code distinguishing the two utilities (e.g. `DESC`, `GPC`) — required for cross-utility filtering.
- `type`: e.g. `Transmission Line`, `Substation`, `Substation Upgrade`.
- `length_miles`: only meaningful for transmission lines; used by the cost/impact estimate.
- `start_date` / `end_date`: planned build window, used for timeline overlap.

## Run the dashboard

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Use the sidebar to adjust the distance
threshold, filter by status/type, or upload your own CSV.

## What it shows

- **Map**: both utilities' projects color-coded, with flagged (overlapping)
  projects highlighted larger and connected by lines to their match.
- **Ranked Coordination Opportunities**: every cross-utility geographic
  overlap, sorted by a coordination score that rewards closer distance and
  gives a bonus for also overlapping in timeline. Downloadable as CSV.
- **Cost/Impact Estimate (bonus)**: a rough shared right-of-way savings
  estimate for the top-ranked opportunity, when both projects are
  transmission lines. The cost-per-mile and shared-fraction assumptions in
  `proximity.py` (`estimate_shared_cost_savings`) are placeholders —
  replace them with a sourced figure if you want a defensible number for
  judging.

## Project structure

```
app.py                  # Streamlit dashboard (UI)
proximity.py            # Geographic + timeline overlap logic, ranking, cost estimate
generate_mock_data.py   # Two-utility mock dataset with seeded overlaps
fetch_osm_data.py       # Generic OSM pull — supplementary only, see note above
data/projects.csv       # Generated data
requirements.txt
```

## Extending for judging

- Swap the placeholder cost assumption in `estimate_shared_cost_savings`
  for a sourced per-mile transmission construction cost.
- Extend the cost estimate to substation pairs (e.g. shared land/capacity
  savings) — currently only implemented for line-to-line pairs.
- If you get real line _geometries_ (not just point coordinates) from the
  utility filings, consider checking actual route overlap/crossing instead
  of point-to-point distance — would need `geopandas` + `shapely`.
