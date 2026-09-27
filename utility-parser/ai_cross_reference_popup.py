import os
import time
import math
from itertools import combinations
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ServerError
from pydantic import BaseModel, Field
from supabase import Client, create_client


script_dir = Path(__file__).resolve().parent
load_dotenv(script_dir.parent / ".env")

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
EARTH_RADIUS_KM = 6371.0
MAX_RETRIES = 3


class PopupSection(BaseModel):
    title: str = Field(description="Section heading suitable for a right-side popup panel.")
    summary: str = Field(description="Single concise paragraph summary for this section.")
    bullets: list[str] = Field(description="Actionable bullet points for operators.")


class CrossReferencePopupReport(BaseModel):
    selected_projects_analyzed: list[str] = Field(description="Projects included in this targeted analysis.")
    land_estimates: str = Field(description="Land-use/trench corridor overlap estimate with assumptions.")
    boundary_conditions: str = Field(description="County/utility/service-territory boundary constraints and opportunities.")
    technical_conditions: str = Field(description="Technical factors: voltage class, line type, interconnection readiness, phasing.")
    cost_comparison: str = Field(description="Cost profile comparison between standalone execution and coordinated execution.")
    overlap_factors: str = Field(description="Geospatial and schedule overlap drivers and confidence caveats.")
    cost_reduction_analysis: str = Field(description="Estimated savings ranges and how they are achieved.")
    right_sidebar_popup: list[PopupSection] = Field(
        description="Ordered sections for rendering a comprehensive right-side popup bar in the frontend."
    )


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _dates_overlap(a_start: Any, a_end: Any, b_start: Any, b_end: Any) -> bool | None:
    if not all([a_start, a_end, b_start, b_end]):
        return None
    return str(a_start) <= str(b_end) and str(b_start) <= str(a_end)


def _in_service_gap_days(a_date: Any, b_date: Any) -> int | None:
    if not a_date or not b_date:
        return None
    from datetime import date

    d1 = a_date if isinstance(a_date, date) else date.fromisoformat(str(a_date))
    d2 = b_date if isinstance(b_date, date) else date.fromisoformat(str(b_date))
    return abs((d1 - d2).days)


def _tier(distance_km: float) -> str:
    if distance_km < 1.6:
        return "under_1.6km"
    if distance_km < 8:
        return "under_8km"
    if distance_km < 40:
        return "under_40km"
    return "over_40km"


def _estimate_pair_savings(distance_km: float, timeline_overlap: bool | None, cost_a: float | None, cost_b: float | None) -> float:
    if cost_a is None or cost_b is None:
        return 0.0
    anchor = min(float(cost_a), float(cost_b))
    if distance_km < 1.6:
        base = 0.12
    elif distance_km < 8:
        base = 0.08
    elif distance_km < 40:
        base = 0.04
    else:
        base = 0.0
    if timeline_overlap is True:
        base *= 1.25
    elif timeline_overlap is False:
        base *= 0.7
    return round(anchor * base, 2)


def _fetch_projects(project_ids: list[int | str]) -> list[dict]:
    rows = supabase.table("projects").select("*").in_("id", project_ids).execute().data or []
    if len(rows) < 2:
        raise ValueError("Fewer than 2 requested projects were found in Supabase.")
    return rows


def _compute_overlaps(projects: list[dict]) -> tuple[list[dict], float]:
    overlap_rows: list[dict] = []
    total_savings = 0.0
    located = [p for p in projects if p.get("lat") is not None and p.get("lng") is not None]
    for a, b in combinations(located, 2):
        distance = _haversine_km(float(a["lat"]), float(a["lng"]), float(b["lat"]), float(b["lng"]))
        timeline_overlap = _dates_overlap(a.get("start_date"), a.get("end_date"), b.get("start_date"), b.get("end_date"))
        est_savings = _estimate_pair_savings(distance, timeline_overlap, a.get("estimated_cost"), b.get("estimated_cost"))
        total_savings += est_savings
        overlap_rows.append(
            {
                "project_a": {"id": a.get("id"), "name": a.get("name"), "utility": a.get("utility")},
                "project_b": {"id": b.get("id"), "name": b.get("name"), "utility": b.get("utility")},
                "distance_km": round(distance, 3),
                "tier": _tier(distance),
                "cross_utility": bool(a.get("utility") and b.get("utility") and a.get("utility") != b.get("utility")),
                "dates_overlap": timeline_overlap,
                "in_service_gap_days": _in_service_gap_days(a.get("in_service_date"), b.get("in_service_date")),
                "estimated_pair_savings_usd": est_savings,
            }
        )
    overlap_rows.sort(key=lambda item: item["distance_km"])
    return overlap_rows, round(total_savings, 2)


def _build_prompt(projects: list[dict], overlaps: list[dict], total_savings: float) -> str:
    project_lines = []
    for i, p in enumerate(projects, 1):
        project_lines.append(
            f"""
Project {i} (ID: {p.get("id")}):
- Name: {p.get("name")}
- Utility: {p.get("utility")}
- State: {p.get("state")}
- Coordinates: ({p.get("lat")}, {p.get("lng")})
- Type: {p.get("project_type")}
- Scope: {p.get("scope")}
- Start/End: {p.get("start_date")} -> {p.get("end_date")}
- In-Service Date: {p.get("in_service_date")}
- Estimated Cost (USD): {p.get("estimated_cost")}
"""
        )

    overlap_lines = [
        f"- {o['project_a']['name']} <-> {o['project_b']['name']}: "
        f"{o['distance_km']} km, tier={o['tier']}, cross_utility={o['cross_utility']}, "
        f"dates_overlap={o['dates_overlap']}, in_service_gap_days={o['in_service_gap_days']}, "
        f"estimated_pair_savings_usd={o['estimated_pair_savings_usd']}"
        for o in overlaps
    ]
    if not overlap_lines:
        overlap_lines = ["- No pairwise overlap metrics could be computed from available coordinates."]

    return f"""
You are the GridSync FL AI Cross-Reference Agent that powers the frontend's "Run AI Cross-Reference Agent" experience.
Create a comprehensive right-side popup bar report for infrastructure coordination and cost reduction.

Use the supplied Supabase project data and geospatial overlap metrics. Be explicit about assumptions and confidence.
Do not fabricate exact legal boundary claims; if data is missing, state it and provide a practical next step.

Selected Projects:
{''.join(project_lines)}

Computed Geospatial Overlap Metrics:
{chr(10).join(overlap_lines)}

Heuristic aggregate estimated savings (USD) across analyzed pairs: {total_savings}

Output must follow the schema exactly and ensure right_sidebar_popup has at least 5 sections:
1) Land Estimates
2) Boundary Conditions
3) Technical Conditions
4) Cost Comparison
5) Cost Reduction Analysis
"""


def run_ai_cross_reference_agent(project_ids: list[int | str]) -> dict:
    projects = _fetch_projects(project_ids)
    overlaps, total_savings = _compute_overlaps(projects)
    prompt = _build_prompt(projects, overlaps, total_savings)

    for attempt in range(MAX_RETRIES):
        try:
            response = gemini.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CrossReferencePopupReport,
                    temperature=0.2,
                ),
            )
            payload = response.parsed.model_dump()
            payload["overlaps"] = overlaps
            payload["aggregate_estimated_savings_usd"] = total_savings
            return payload
        except ServerError:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep((attempt + 1) * 3)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Generate a comprehensive AI cross-reference popup report for selected Supabase project IDs."
    )
    parser.add_argument(
        "--project-ids",
        nargs="+",
        required=True,
        help="List of project IDs (for example: --project-ids 1 2 3).",
    )
    args = parser.parse_args()
    result = run_ai_cross_reference_agent(args.project_ids)
    print(json.dumps(result, indent=2))
