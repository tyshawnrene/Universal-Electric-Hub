import os
import time
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from typing import Optional
from google.genai import types
from google.genai.errors import ServerError
from pydantic import BaseModel, Field
from supabase import create_client, Client

script_dir = Path(__file__).resolve().parent
# Look one level up for the .env file in the root directory
load_dotenv(script_dir.parent / ".env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class ProjectRecord(BaseModel):
    project_name: str = Field(description="Exact name of the transmission project, line rebuild, or substation upgrade.")
    utility_company: str = Field(description="Name of the utility operating the project.")
    state: str = Field(description="Two-letter state abbreviation.")
    latitude: Optional[float] = Field(default=None, description="Regional or corridor centerpoint latitude (e.g., county centroid or midpoint of the transmission line route).")
    longitude: Optional[float] = Field(default=None, description="Regional or corridor centerpoint longitude (e.g., county centroid or midpoint of the transmission line route).")
    in_service_date: Optional[str] = Field(default=None, description="Planned in-service date.")
    project_scope: str = Field(description="Detailed technical description of the project scope.")

class DocumentExtraction(BaseModel):
    projects: list[ProjectRecord] = Field(description="Complete list of all transmission and capital projects found in the document.")

def standardize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Cleans and standardizes messy utility date strings into a uniform YYYY-MM-DD format.
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # Handle quarters like "Q4 2025" -> map to end of quarter
    quarter_match = re.search(r'Q([1-4])\s*(\d{4})', date_str, re.IGNORECASE)
    if quarter_match:
        q, year = quarter_match.groups()
        mapping = {'1': f"{year}-03-31", '2': f"{year}-06-30", '3': f"{year}-09-30", '4': f"{year}-12-31"}
        return mapping.get(q)
    
    # Handle Year-only like "2025" -> map to end of year
    if re.fullmatch(r'\d{4}', date_str):
        return f"{date_str}-12-31"

    # Try standard Python parsing for regular formats
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y', '%b %d, %Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
            
    return date_str

def parse_pdf_file(file_path: Path):
    print(f"Uploading {file_path.name} to Gemini Files API...")
    uploaded_file = client.files.upload(file=file_path)
    print(f"File uploaded successfully. Remote URI Name: {uploaded_file.name}")

    prompt = """
    Extract EVERY SINGLE transmission project, line rebuild, and substation upgrade listed in this document. 
    Do not skip any projects. For each project, extract:
    - project_name
    - utility_company
    - state
    - latitude and longitude: Instead of exact building-level pins, provide the **regional or corridor centerpoint** coordinates (such as the county centroid, the midpoint of the transmission line route between terminal substations, or the general area center). If an exact location isn't specified, calculate or estimate the centerpoint of the region/county mentioned.
    - in_service_date
    - project_scope
    """

    max_retries = 5
    response = None
    
    for attempt in range(max_retries):
        try:
            print(f"Running Gemini regional extraction (Attempt {attempt + 1}/{max_retries})...")
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=[uploaded_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DocumentExtraction,
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
    print("Cleanup complete.")
    return response.parsed

def process_single_pdf(file_path: Path):
    extracted_data = parse_pdf_file(file_path)
    
    if not extracted_data or not extracted_data.projects:
        print("No projects extracted from PDF.")
        return

    print(f"\n--- Extracted {len(extracted_data.projects)} Projects ---")
    
    success_count = 0
    for proj in extracted_data.projects:
        proj.in_service_date = standardize_date(proj.in_service_date)
        project_dict = proj.model_dump()
        
        try:
            supabase.table("projects").insert(project_dict).execute()
            print(f"Inserted regional marker: [{proj.utility_company}] {proj.project_name} -> ({proj.latitude}, {proj.longitude})")
            success_count += 1
        except Exception as e:
            print(f"Failed to insert '{proj.project_name}': {e}")

    print(f"\nSuccessfully stored {success_count}/{len(extracted_data.projects)} regional records in Supabase!")

    processed_dir = script_dir / "processed"
    processed_dir.mkdir(exist_ok=True)
    file_path.rename(processed_dir / file_path.name)
    print(f"Moved {file_path.name} to 'processed/' folder.")

if __name__ == "__main__":
    for pdf_file in script_dir.glob("*.pdf"):
        if "processed" in str(pdf_file.parent):
            continue
        print(f"Found new PDF to process: {pdf_file.name}")
        process_single_pdf(pdf_file)