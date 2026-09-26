"""Pairwise spatial/temporal overlap analysis between projects.

This is an in-memory fallback; once data is in Supabase, the same tiers can be
computed with PostGIS ST_DWithin.
"""

import math
from itertools import combinations

from models.project import Project

EARTH_RADIUS_KM = 6371.0

# (tier name, max distance in km), checked in order
PROXIMITY_TIERS = [
    ("under_1.6km", 1.6),
    ("under_8km", 8.0),
    ("under_40km", 40.0),
]


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def classify_tier(distance_km: float) -> str | None:
    for tier, max_km in PROXIMITY_TIERS:
        if distance_km < max_km:
            return tier
    return None


def dates_overlap(a: Project, b: Project) -> bool | None:
    """True/False if both projects have full date ranges, else None (unknown)."""
    if not all([a.start_date, a.end_date, b.start_date, b.end_date]):
        return None
    return a.start_date <= b.end_date and b.start_date <= a.end_date


def in_service_gap_days(a: Project, b: Project) -> int | None:
    """Days between the two in-service dates; small gaps suggest coordinated scheduling."""
    if not (a.in_service_date and b.in_service_date):
        return None
    return abs((a.in_service_date - b.in_service_date).days)


def find_overlaps(projects: list[Project], max_km: float = 40.0) -> list[dict]:
    overlaps = []
    for a, b in combinations(projects, 2):
        distance = haversine_km(a.lat, a.lng, b.lat, b.lng)
        if distance > max_km:
            continue
        overlaps.append({
            "project_a": {"id": a.id, "name": a.name, "utility": a.utility},
            "project_b": {"id": b.id, "name": b.name, "utility": b.utility},
            "distance_km": round(distance, 3),
            "tier": classify_tier(distance),
            "cross_utility": bool(a.utility and b.utility and a.utility != b.utility),
            "dates_overlap": dates_overlap(a, b),
            "in_service_gap_days": in_service_gap_days(a, b),
        })
    return sorted(overlaps, key=lambda o: o["distance_km"])
