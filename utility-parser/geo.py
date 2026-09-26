import os
import time
import re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from typing import Optional
from google.genai import types
from google.genai.errors import ServerError
from pydantic import BaseModel, Field
from supabase import create_client, Client

script_dir = Path(__file__).resolve().parent
load_dotenv(script_dir / ".env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class ProjectGeoRecord(BaseModel):
    project_name: str = Field(description="Exact name of the transmission project or substation upgrade as written in the document.")
    utility_company: str = Field(description="Name of the utility operating the project.")
    latitude: float = Field(description="Latitude coordinate for the project, substation, or line endpoints.")
    longitude: float = Field(description="Longitude coordinate for the project, substation, or line endpoints.")

class DocumentGeoExtraction(BaseModel):
    projects: list[ProjectGeoRecord] = Field(description="List of projects with their extracted geographical coordinates.")

def parse_pdf_coordinates(file_path: Path):
    print(f"Uploading {file_path.name} to Gemini Files API for Geo-extraction...")
    uploaded_file = client.files.upload(file=file_path)
    print(f"File uploaded successfully. Remote URI Name: {uploaded_file.name}")

    prompt = """
    Analyze this document and extract ONLY projects that have explicit latitude and longitude coordinates, 
    or where you can accurately map named substations and terminals to precise geographical coordinates. 
    Return the project name, utility company, and its lat/long coordinates. Do not skip coordinates.
    """

    max_retries = 5
    response = None
    
    for attempt in range(max_retries):
        try:
            print(f"Running Gemini Geo extraction analysis (Attempt {attempt + 1}/{max_retries})...")
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=[uploaded_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DocumentGeoExtraction,
                    temperature=0.0,
                ),
            )
            break
        except ServerError as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"Model busy (503). Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise e

    client.files.delete(name=uploaded_file.name)
    print("Geo-extraction cleanup complete.")
    return response.parsed

def update_project_coordinates(file_path: Path):
    extracted_data = parse_pdf_coordinates(file_path)
    
    if not extracted_data or not extracted_data.projects:
        print("No geographical coordinates extracted from PDF.")
        return

    print(f"\n--- Updating Coordinates for {len(extracted_data.projects)} Projects ---")
    
    updated_count = 0
    for proj in extracted_data.projects:
        try:
            # Update existing row in Supabase matching by project name and utility company
            res = supabase.table("projects") \
                .update({"latitude": proj.latitude, "longitude": proj.longitude}) \
                .eq("project_name", proj.project_name) \
                .eq("utility_company", proj.utility_company) \
                .execute()
            
            print(f"Updated coordinates for: [{proj.utility_company}] {proj.project_name} -> ({proj.latitude}, {proj.longitude})")
            updated_count += 1
        except Exception as e:
            print(f"Failed to update coordinates for '{proj.project_name}': {e}")

    print(f"\nSuccessfully updated coordinates for {updated_count} projects in Supabase!")

if __name__ == "__main__":
    for pdf_file in script_dir.glob("*.pdf"):
        # Skip files in the 'processed' folder if you want, or target specific files
        if "processed" in str(pdf_file.parent):
            continue
        print(f"Processing geo-data for PDF: {pdf_file.name}")
        update_project_coordinates(pdf_file)