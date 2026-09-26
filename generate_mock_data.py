"""
Generates mock planned-construction data for two neighboring utilities,
modeled on the Gridlock challenge (Dominion Energy South Carolina vs.
Georgia Power along the SC/GA border).

Deliberately generates mostly non-overlapping projects, with a handful of
"seeded" true overlaps (close in both location and build window) so the
overlap-detection logic has real matches to find, and a couple of
"partial" overlaps (close in location, but not timeline, or vice versa)
so the two overlap signals can be told apart in the demo.

Replace this with real data pulled from each utility's public transmission
plan filings (see the challenge's Finding_Real_Locations_Guide) once
you've extracted real project coordinates and dates.
"""

import numpy as np
import pandas as pd

np.random.seed(7)

UTILITIES = ["DESC", "GPC"]  # Dominion Energy South Carolina, Georgia Power
TYPES = ["Transmission Line", "Substation", "Substation Upgrade"]
STATUSES = ["Planned", "Under Construction", "Permitting"]

# Rough bounding box along the SC/GA border (Savannah River corridor)
LAT_RANGE = (32.0, 34.8)
LON_RANGE = (-83.2, -80.8)

N_PER_UTILITY = 25


def random_date(start_year=2025, end_year=2031):
    start = pd.Timestamp(f"{start_year}-01-01")
    end = pd.Timestamp(f"{end_year}-12-31")
    delta_days = (end - start).days
    return start + pd.to_timedelta(np.random.randint(0, delta_days), unit="D")


def make_project(i, utility, lat=None, lon=None, start=None, end=None):
    if lat is None:
        lat = np.random.uniform(*LAT_RANGE)
    if lon is None:
        lon = np.random.uniform(*LON_RANGE)
    if start is None:
        start = random_date()
    if end is None:
        end = start + pd.Timedelta(days=int(np.random.randint(180, 720)))

    ptype = np.random.choice(TYPES)
    return {
        "id": f"{utility}{i:03d}",
        "name": f"{utility} {ptype} {i:03d}",
        "utility": utility,
        "type": ptype,
        "status": np.random.choice(STATUSES, p=[0.4, 0.4, 0.2]),
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "capacity_mw": int(np.random.choice([25, 50, 100, 150, 230, 500])) if ptype != "Substation" else None,
        "voltage_kv": int(np.random.choice([115, 230, 500])),
        "length_miles": round(np.random.uniform(2, 40), 1) if ptype == "Transmission Line" else None,
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "owner": "Dominion Energy South Carolina" if utility == "DESC" else "Georgia Power",
    }


rows = []
project_counter = {"DESC": 0, "GPC": 0}

for utility in UTILITIES:
    for _ in range(N_PER_UTILITY):
        project_counter[utility] += 1
        rows.append(make_project(project_counter[utility], utility))

# --- Seed a few deliberate TRUE overlaps: close location + overlapping build window ---
seed_points = [
    (33.55, -82.05),  # near Augusta / North Augusta
    (32.45, -81.15),  # near Savannah / Hardeeville area
    (34.05, -81.55),  # further north along the river
]
for i, (lat, lon) in enumerate(seed_points):
    shared_start = random_date(2026, 2027)
    shared_end = shared_start + pd.Timedelta(days=400)

    project_counter["DESC"] += 1
    rows.append(make_project(
        project_counter["DESC"], "DESC",
        lat=lat + np.random.uniform(-0.05, 0.05), lon=lon + np.random.uniform(-0.05, 0.05),
        start=shared_start, end=shared_end,
    ))
    project_counter["GPC"] += 1
    rows.append(make_project(
        project_counter["GPC"], "GPC",
        lat=lat + np.random.uniform(-0.05, 0.05), lon=lon + np.random.uniform(-0.05, 0.05),
        start=shared_start, end=shared_end,
    ))

# --- Seed a "location-only" overlap: close together, but different build windows ---
lat, lon = 33.0, -81.7
project_counter["DESC"] += 1
rows.append(make_project(
    project_counter["DESC"], "DESC", lat=lat, lon=lon,
    start=pd.Timestamp("2025-01-01"), end=pd.Timestamp("2025-08-01"),
))
project_counter["GPC"] += 1
rows.append(make_project(
    project_counter["GPC"], "GPC", lat=lat + 0.03, lon=lon + 0.02,
    start=pd.Timestamp("2029-01-01"), end=pd.Timestamp("2029-08-01"),
))

df = pd.DataFrame(rows)
df.to_csv("data/projects.csv", index=False)
print(f"Wrote {len(df)} mock projects ({(df['utility'] == 'DESC').sum()} DESC, "
      f"{(df['utility'] == 'GPC').sum()} GPC) to data/projects.csv")
