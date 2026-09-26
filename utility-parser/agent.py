import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ServerError
from pydantic import BaseModel, Field
from supabase import create_client, Client

script_dir = Path(__file__).resolve().parent
load_dotenv(script_dir / ".env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class TargetedGridOverlapReport(BaseModel):
    selected_projects_analyzed: list[str] = Field(description="Names of the specific projects included in this cross-reference.")
    spatial_and_corridor_synergy: str = Field(description="Detailed breakdown of geographic proximity, shared utility corridors, and substation tie-ins.")
    schedule_alignment: str = Field(description="Temporal overlap analysis of target in-service dates and construction staging opportunities.")
    strategic_recommendations: str = Field(description="Actionable recommendations for joint filings, shared equipment staging, or constraint mitigation.")

def run_targeted_analysis(project_ids: list[int]):
    response = supabase.table("projects").select("*").in_("id", project_ids).execute()
    projects = response.data
    
    if not projects:
        raise ValueError("No matching projects found for the provided IDs.")

    projects_text = ""
    for i, p in enumerate(projects, 1):
        projects_text += f"""
        Target Project {i} (ID: {p.get('id')}):
        - Name: {p.get('project_name')}
        - Utility: {p.get('utility_company')}
        - State: {p.get('state')}
        - Coordinates: ({p.get('latitude')}, {p.get('longitude')})
        - In-Service Date: {p.get('in_service_date')}
        - Scope: {p.get('project_scope')}
        ----------------------------------
        """

    prompt = f"""
    You are an expert Chief Grid Infrastructure Strategist. 
    Analyze the spatial overlaps, timeline adjacencies, and collaborative deployment potential for these selected projects.

    Selected Projects:
    {projects_text}
    """

    # Retry loop for 503 high demand spikes
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TargetedGridOverlapReport,
                    temperature=0.2,
                ),
            )
            return response.parsed
        except ServerError as e:
            if attempt < max_retries - 1:
                print(f"Model busy (503). Retrying analysis in {(attempt + 1) * 3} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep((attempt + 1) * 3)
            else:
                raise e