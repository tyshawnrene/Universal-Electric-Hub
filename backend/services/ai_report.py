"""Gemini-generated coordination report for a set of selected projects.

Ported from utility-parser/agent.py so the frontend only talks to this Flask API.
"""

import time
from functools import lru_cache

from google import genai
from google.genai import types
from google.genai.errors import ServerError
from pydantic import BaseModel, Field

from config import Config
from models.project import Project

MAX_RETRIES = 3


class TargetedGridOverlapReport(BaseModel):
    selected_projects_analyzed: list[str] = Field(description="Names of the specific projects included in this cross-reference.")
    spatial_and_corridor_synergy: str = Field(description="Detailed breakdown of geographic proximity, shared utility corridors, and substation tie-ins.")
    schedule_alignment: str = Field(description="Temporal overlap analysis of target in-service dates and construction staging opportunities.")
    strategic_recommendations: str = Field(description="Actionable recommendations for joint filings, shared equipment staging, or constraint mitigation.")


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    if not Config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY must be set in .env")
    return genai.Client(api_key=Config.GEMINI_API_KEY)


def build_prompt(projects: list[Project], overlaps: list[dict]) -> str:
    projects_text = ""
    for i, p in enumerate(projects, 1):
        coords = f"({p.lat}, {p.lng})" if p.lat is not None else "unknown"
        projects_text += f"""
        Target Project {i} (ID: {p.id}):
        - Name: {p.name}
        - Utility: {p.utility}
        - State: {p.state}
        - Coordinates: {coords}
        - In-Service Date: {p.in_service_date or "unknown"}
        - Scope: {p.scope}
        ----------------------------------
        """

    overlap_text = "\n".join(
        f"        - {o['project_a']['name']} <-> {o['project_b']['name']}: {o['distance_km']} km ({o['tier']})"
        for o in overlaps
    ) or "        - No computed distances (coordinates missing for some projects)."

    return f"""
    You are an expert Chief Grid Infrastructure Strategist.
    Analyze the spatial overlaps, timeline adjacencies, and collaborative deployment potential for these selected projects.

    Selected Projects:
    {projects_text}

    Computed pairwise distances:
{overlap_text}
    """


def generate_report(projects: list[Project], overlaps: list[dict]) -> dict:
    prompt = build_prompt(projects, overlaps)
    for attempt in range(MAX_RETRIES):
        try:
            response = get_client().models.generate_content(
                model=Config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TargetedGridOverlapReport,
                    temperature=0.2,
                ),
            )
            return response.parsed.model_dump()
        except ServerError:
            # Retry 503 "model busy" spikes with a short backoff.
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep((attempt + 1) * 3)
