"""
NOTE (Gridlock challenge): this script pulls generic "under construction"
power infrastructure from OSM, but does NOT reliably separate it by
utility/owner — OSM's `operator` tag is inconsistently filled in, so it's
a weak substitute for the real per-utility planning-document data the
challenge asks for (DESC's SCRTP filings, Georgia Power's 10-Year
Transmission Plan). Treat this as a way to sanity-check coordinates or
pad out a demo, not as your primary data source — see the challenge's
Finding_Real_Locations_Guide for how to pull the real utility filings.
If you do use this, you'll need to add a `utility` column yourself
(e.g. by matching each row's `owner` value against a known list of utility
names) since the dashboard's overlap logic requires it.

Fetches power infrastructure that is under construction (or proposed) from
OpenStreetMap via the Overpass API, and writes it out in the same schema
the dashboard expects (data/projects.csv).

OSM tagging conventions this script looks for:
  1. Lifecycle prefix (the "official" OSM convention, same pattern as
     highway=construction): power=construction + construction=<type>
     e.g. power=construction, construction=substation
  2. The looser/older convention some mappers use instead:
     construction:power=<type>
     e.g. construction:power=line

It also picks up power=proposed / proposed:power=<type> so you can include
planned-but-not-yet-started projects if you want a bigger dataset.

Usage:
    python fetch_osm_data.py --area "Spain"
    python fetch_osm_data.py --bbox 36.0 -9.5 43.8 3.3   # south west north east
    python fetch_osm_data.py --area "Spain" --include-proposed
"""

import argparse
import sys
import time

import pandas as pd
import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Types of power features we care about
POWER_TYPES = ["plant", "substation", "generator", "line", "cable", "converter", "transformer"]


def build_query(area_name: str | None, bbox: list | None, include_proposed: bool) -> str:
    type_regex = "|".join(POWER_TYPES)

    if area_name:
        area_clause = f'area["name"="{area_name}"]->.searchArea;'
        area_filter = "(area.searchArea)"
    else:
        area_clause = ""
        s, w, n, e = bbox
        area_filter = f"({s},{w},{n},{e})"

    statuses = ["construction"]
    if include_proposed:
        statuses.append("proposed")

    clauses = []
    for status in statuses:
        # Convention 1: power=<status> + construction/proposed=<type>
        clauses.append(f'node["power"="{status}"]["{status}"~"{type_regex}"]{area_filter};')
        clauses.append(f'way["power"="{status}"]["{status}"~"{type_regex}"]{area_filter};')
        # Convention 2: <status>:power=<type>
        clauses.append(f'node["{status}:power"~"{type_regex}"]{area_filter};')
        clauses.append(f'way["{status}:power"~"{type_regex}"]{area_filter};')

    query = f"""
    [out:json][timeout:90];
    {area_clause}
    (
      {" ".join(clauses)}
    );
    out center tags;
    """
    return query


def parse_capacity_mw(tags: dict) -> float | None:
    """Pulls capacity out of whichever tag has it, converts to MW."""
    for key in ("plant:output:electricity", "generator:output:electricity"):
        if key in tags:
            val = tags[key].lower().replace(" ", "")
            try:
                if "gw" in val:
                    return float(val.replace("gw", "")) * 1000
                if "mw" in val:
                    return float(val.replace("mw", ""))
                if "kw" in val:
                    return float(val.replace("kw", "")) / 1000
                return float(val)
            except ValueError:
                return None
    return None


def infer_type(tags: dict) -> str:
    for status in ("construction", "proposed"):
        if tags.get("power") == status and status in tags:
            return tags[status].replace("_", " ").title()
        key = f"{status}:power"
        if key in tags:
            return tags[key].replace("_", " ").title()
    return tags.get("power", "unknown").replace("_", " ").title()


def infer_status(tags: dict) -> str:
    if tags.get("power") == "proposed" or "proposed:power" in tags:
        return "Planned"
    return "Under Construction"


def fetch(area_name, bbox, include_proposed):
    query = build_query(area_name, bbox, include_proposed)
    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=120)
    resp.raise_for_status()
    return resp.json()


def to_dataframe(osm_json: dict) -> pd.DataFrame:
    rows = []
    for i, el in enumerate(osm_json.get("elements", [])):
        tags = el.get("tags", {})

        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:  # way/relation — Overpass gives a center when asked with "out center"
            center = el.get("center", {})
            lat, lon = center.get("lat"), center.get("lon")

        if lat is None or lon is None:
            continue

        rows.append({
            "id": f"OSM{el['id']}",
            "name": tags.get("name", f"Unnamed {infer_type(tags)}"),
            "type": infer_type(tags),
            "status": infer_status(tags),
            "lat": lat,
            "lon": lon,
            "capacity_mw": parse_capacity_mw(tags),
            "expected_completion": tags.get("opening_date") or tags.get("check_date"),
            "owner": tags.get("operator", "Unknown"),
        })

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Fetch under-construction power infrastructure from OSM")
    parser.add_argument("--area", type=str, help='OSM area name, e.g. "Spain" or "California"')
    parser.add_argument("--bbox", type=float, nargs=4, metavar=("SOUTH", "WEST", "NORTH", "EAST"),
                         help="Bounding box instead of an area name")
    parser.add_argument("--include-proposed", action="store_true",
                         help="Also include proposed (not-yet-started) projects")
    parser.add_argument("--out", type=str, default="data/projects.csv")
    args = parser.parse_args()

    if not args.area and not args.bbox:
        print("Provide either --area \"Name\" or --bbox SOUTH WEST NORTH EAST", file=sys.stderr)
        sys.exit(1)

    print("Querying Overpass API... (can take 10-60s for large areas)")
    start = time.time()
    data = fetch(args.area, args.bbox, args.include_proposed)
    print(f"Got {len(data.get('elements', []))} raw elements in {time.time() - start:.1f}s")

    df = to_dataframe(data)
    if df.empty:
        print("No matching elements found. Try a larger area, a different region, "
              "or run with --include-proposed.")
        sys.exit(0)

    # Fill missing capacity with the column median so the dashboard's
    # capacity-diff comparison still works; flag rows where it was missing.
    df["capacity_estimated"] = df["capacity_mw"].isna()
    if df["capacity_mw"].notna().any():
        df["capacity_mw"] = df["capacity_mw"].fillna(df["capacity_mw"].median())
    else:
        df["capacity_mw"] = df["capacity_mw"].fillna(0)

    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} projects to {args.out}")
    print(df["type"].value_counts())


if __name__ == "__main__":
    main()
