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
load_dotenv(script_dir / ".env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class ProjectRecord(BaseModel):
    project_name: str = Field(description="Name of the transmission project or substation upgrade.")
    utility_company: str = Field(description="Name of the utility operating the project.")
    state: str = Field(description="Two-letter state abbreviation.")
    latitude: Optional[float] = Field(default=None, description="Latitude if available in text or maps.")
    longitude: Optional[float] = Field(default=None, description="Longitude if available in text or maps.")
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
    
    # Handle "Q4 2025" or similar quarter formats -> map to end of quarter
    quarter_match = re.search(r'Q([1-4])\s*(\d{4})', date_str, re.IGNORECASE)
    if quarter_match:
        q, year = quarter_match.groups()
        mapping = {'1': f"{year}-03-31", '2': f"{year}-06-30", '3': f"{year}-09-30", '4': f"{year}-12-31"}
        return mapping.get(q)
    
    # Handle Year-only like "2025" -> map to end of year
    if re.fullmatch(r'\d{4}', date_str):
        return f"{date_str}-12-31"

    # Try standard Python parsing for regular dates (e.g., MM/DD/YYYY, Month DD YYYY)
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y', '%b %d, %Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
            
    # Return original string if it can't be automatically parsed
    return date_str

def sanitize_table_name(company_name: str, file_name: str) -> str:
    """
    Takes an extracted utility company name or filename and converts it 
    into a safe, standardized PostgreSQL table name (snake_case).
    Example: 'Florida Power & Light' -> 'florida_power_light_projects'
    """
    base_string = company_name if company_name else file_name
    base_string = re.sub(r'\.[^/.]+$', '', base_string)
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', base_string)
    snake_case = re.sub(r'\s+', '_', clean.strip()).lower()
    return f"{snake_case}_projects"

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
    - latitude and longitude (If exact coordinates are not in the text, look for named substations, 
      towns, or endpoints so we can estimate location, otherwise leave null).
    - in_service_date
    - project_scope
    """

    max_retries = 5
    response = None
    
    for attempt in range(max_retries):
        try:
            print(f"Running Gemini extraction analysis (Attempt {attempt + 1}/{max_retries})...")
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=[uploaded_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DocumentExtraction,
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
    print("Cleanup complete.")
    return response.parsed

def process_single_pdf(file_path: Path):
    extracted_data = parse_pdf_file(file_path)
    
    if not extracted_data or not extracted_data.projects:
        print("No projects extracted from PDF.")
        return

    print(f"\n--- Extracted {len(extracted_data.projects)} Projects ---")
    
    for proj in extracted_data.projects:
        # Standardize the date format cleanly
        proj.in_service_date = standardize_date(proj.in_service_date)
        
        project_dict = proj.model_dump()
        target_table = sanitize_table_name(proj.utility_company, file_path.name)
        
        try:
            res = supabase.table(target_table).insert(project_dict).execute()
            print(f"Pushed to Supabase table [{target_table}]: {proj.project_name}")
        except Exception as e:
            # Fallback to the master 'projects' table
            fallback_table = "projects"
            try:
                fallback_res = supabase.table(fallback_table).insert(project_dict).execute()
                print(f"Pushed to unified master table [{fallback_table}]: {proj.project_name}")
            except Exception as inner_e:
                print(f"Failed to push project '{proj.project_name}' to master table: {inner_e}")

    processed_dir = script_dir / "processed"
    processed_dir.mkdir(exist_ok=True)
    file_path.rename(processed_dir / file_path.name)
    print(f"Moved {file_path.name} to 'processed/' folder.")

if __name__ == "__main__":
    for pdf_file in script_dir.glob("*.pdf"):
        print(f"Found new PDF to process: {pdf_file.name}")
        process_single_pdf(pdf_file)