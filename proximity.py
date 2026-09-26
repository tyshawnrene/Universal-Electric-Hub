"""
Core overlap logic for the Gridlock challenge:

- Geographic overlap: two planned projects from DIFFERENT utilities within
  a distance threshold (default 25 miles) of each other.
- Timeline overlap: their planned build windows (start_date/end_date)
  intersect.

Geographic overlap is the primary signal; timeline overlap is a secondary
signal layered on top. Only cross-utility pairs are considered — two
projects from the *same* utility being close together isn't a
coordination opportunity for this challenge.
"""

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS_MILES = 3958.8


def find_geographic_overlaps(df: pd.DataFrame, radius_miles: float = 25.0) -> pd.DataFrame:
    """
    Returns all cross-utility pairs within radius_miles of each other.
    Requires a 'utility' column so same-utility pairs can be excluded.
    """
    coords = np.radians(df[["lat", "lon"]].values)
    tree = BallTree(coords, metric="haversine")
    radius_rad = radius_miles / EARTH_RADIUS_MILES

    indices, distances = tree.query_radius(coords, r=radius_rad, return_distance=True)

    pairs = []
    for i, (neighbors, dists) in enumerate(zip(indices, distances)):
        for j, d in zip(neighbors, dists):
            if i >= j:
                continue
            if df.iloc[i]["utility"] == df.iloc[j]["utility"]:
                continue  # only cross-utility pairs count
            pairs.append({
                "project_a": df.iloc[i]["id"],
                "project_b": df.iloc[j]["id"],
                "distance_miles": round(d * EARTH_RADIUS_MILES, 2),
            })

    return pd.DataFrame(pairs, columns=["project_a", "project_b", "distance_miles"])


def _date_ranges_overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start <= b_end and b_start <= a_end


def build_opportunity_table(df: pd.DataFrame, overlap_df: pd.DataFrame, radius_miles: float = 25.0) -> pd.DataFrame:
    """
    Joins project attributes onto each geographic overlap pair, adds a
    timeline-overlap flag, and produces a ranked coordination-opportunity
    score (geographic overlap is required to appear here at all; timeline
    overlap boosts the ranking on top of that).
    """
    if overlap_df.empty:
        return overlap_df

    merged = overlap_df.merge(
        df, left_on="project_a", right_on="id", suffixes=("", "_a")
    ).merge(
        df, left_on="project_b", right_on="id", suffixes=("_a", "_b")
    )

    starts_a = pd.to_datetime(merged["start_date_a"])
    ends_a = pd.to_datetime(merged["end_date_a"])
    starts_b = pd.to_datetime(merged["start_date_b"])
    ends_b = pd.to_datetime(merged["end_date_b"])

    merged["timeline_overlap"] = [
        _date_ranges_overlap(sa, ea, sb, eb)
        for sa, ea, sb, eb in zip(starts_a, ends_a, starts_b, ends_b)
    ]

    # Simple, transparent scoring: closer distance = higher score, and a
    # flat bonus if the build windows also overlap. This is intentionally
    # rough — tune the weighting/bonus to fit how your team wants to
    # prioritize distance vs. timing.
    TIMELINE_BONUS = 15  # miles-equivalent bonus applied to the score
    merged["coordination_score"] = (
        (radius_miles - merged["distance_miles"]).clip(lower=0)
        + merged["timeline_overlap"].astype(int) * TIMELINE_BONUS
    )

    cols = [
        "project_a", "name_a", "utility_a", "type_a", "status_a",
        "start_date_a", "end_date_a", "length_miles_a",
        "project_b", "name_b", "utility_b", "type_b", "status_b",
        "start_date_b", "end_date_b", "length_miles_b",
        "distance_miles", "timeline_overlap", "coordination_score",
    ]
    return merged[cols].sort_values("coordination_score", ascending=False).reset_index(drop=True)


def estimate_shared_cost_savings(row: pd.Series, cost_per_mile: float = 1_500_000) -> dict:
    """
    Very rough bonus-round estimate: if both projects in a pair are
    transmission lines, assume they could share right-of-way / crews for
    the shorter of the two segments, saving a fraction of typical
    per-mile build cost. This is a placeholder assumption for demo
    purposes, not a real engineering or financial estimate — swap in a
    sourced cost figure if you want a more defensible number.
    """
    if row.get("type_a") != "Transmission Line" or row.get("type_b") != "Transmission Line":
        return {"applicable": False}

    shorter_length = min(row.get("length_miles_a", 0) or 0, row.get("length_miles_b", 0) or 0)
    SHARED_FRACTION = 0.3  # assume ~30% of the shorter line's cost could be shared

    estimated_savings = shorter_length * cost_per_mile * SHARED_FRACTION
    return {
        "applicable": True,
        "shared_length_miles": shorter_length,
        "estimated_savings_usd": round(estimated_savings),
        "assumption": f"~{int(SHARED_FRACTION*100)}% of shorter line's cost "
                       f"(${cost_per_mile:,.0f}/mi assumed) shared via right-of-way/crews",
    }
