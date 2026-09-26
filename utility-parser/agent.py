import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
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
    print(f"Fetching selected project records (IDs: {project_ids}) from Supabase...")
    
    # Query Supabase for only the user-selected project IDs
    response = supabase.table("projects").select("*").in_("id", project_ids).execute()
    projects = response.data
    
    if not projects:
        print("No matching projects found for the provided IDs.")
        return None

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
    A business user has explicitly selected the following transmission projects for a targeted cross-reference analysis. 
    Analyze their spatial overlaps, timeline adjacencies, and collaborative deployment potential based strictly on these selected datapoints.

    Selected Projects:
    {projects_text}
    """

    print("Synthesizing targeted cross-reference report via Gemini...")
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TargetedGridOverlapReport,
            temperature=0.2,
        ),
    )

    print("\n=== TARGETED GRID ANALYSIS REPORT ===")
    print(response.text)
    return response.parsed

if __name__ == "__main__":
    # Example: Allow the user to input specific project IDs interactively from the terminal
    print("Available projects can be viewed in your Supabase dashboard.")
    user_input = input("Enter project IDs to cross-reference (comma-separated, e.g., 2, 5): ")
    
    try:
        selected_ids = [int(pid.strip()) for pid in user_input.split(",")]
        run_targeted_analysis(selected_ids)
    except ValueError:
        print("Invalid input. Please enter numbers separated by commas.")