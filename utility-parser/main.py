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
    latitude: Optional[float] = Field(default=None, description="Regional/corridor centroid latitude representing a broader project footprint (county or multi-county service area midpoint, not a building pin).")
    longitude: Optional[float] = Field(default=None, description="Regional/corridor centroid longitude representing a broader project footprint (county or multi-county service area midpoint, not a building pin).")
    in_service_date: Optional[str] = Field(default=None, description="Planned in-service date.")
    price: Optional[float] = Field(default=None, description="Estimated total cost or capital expenditure price for the project in numeric format (e.g., in dollars).")
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


def normalize_regional_coordinate(value: Optional[float]) -> Optional[float]:
    """
    Broaden coordinate precision to reflect regional footprints rather than pinpoint
    addresses. Rounding to 0.05° (~3-5 km east/west in most of the US) helps keep
    overlap distance comparisons regionally consistent.
    """
    if value is None:
        return None
    return round(value * 20) / 20

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
    - latitude and longitude: Provide a **regional/corridor centroid** for a larger geographic footprint, NOT a building-level pin.
      Coordinate selection rules:
      1) If a route/corridor is named, use the midpoint of the corridor between endpoints.
      2) If one county is named, use that county centroid (not city hall or utility HQ).
      3) If multiple counties/areas are named, use a weighted midpoint across the full service area.
      4) Favor a broader regional centroid appropriate for mapping overlap, roughly representing a 10-30 mile project influence radius.
      5) If exact location is unknown, infer the best regional centroid from project scope text and keep it conservative.
    - in_service_date
    - price: The estimated total cost or capital expenditure price (convert to a plain numeric float value if expressed in millions or thousands, e.g., $5.2M becomes 5200000, or leave null if not mentioned).
    - project_scope
    """

    max_retries = 5
    response = None
    
    for attempt in range(max_retries):
        try:
            print(f"Running Gemini regional extraction with pricing (Attempt {attempt + 1}/{max_retries})...")
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

def process_single_pdf(file_path: Path, update_only: bool = False):
    extracted_data = parse_pdf_file(file_path)
    
    if not extracted_data or not extracted_data.projects:
        print("No projects extracted from PDF.")
        return

    print(f"\n--- Extracted {len(extracted_data.projects)} Projects ---")
    
    success_count = 0
    for proj in extracted_data.projects:
        proj.in_service_date = standardize_date(proj.in_service_date)
        proj.latitude = normalize_regional_coordinate(proj.latitude)
        proj.longitude = normalize_regional_coordinate(proj.longitude)
        project_dict = proj.model_dump()
        if proj.price is not None:
            # Support either column name in Supabase schemas.
            project_dict["estimated_cost"] = proj.price
        
        try:
            if update_only:
                supabase.table("projects").update(project_dict).eq("project_name", proj.project_name).eq("utility_company", proj.utility_company).execute()
                print(f"Updated: [{proj.utility_company}] {proj.project_name} | Cost: ${proj.price}")
            else:
                supabase.table("projects").insert(project_dict).execute()
                print(f"Inserted: [{proj.utility_company}] {proj.project_name} | Cost: ${proj.price}")
            success_count += 1
        except Exception as e:
            error_text = str(e)
            try:
                if 'column "estimated_cost" does not exist' in error_text:
                    legacy_payload = {k: v for k, v in project_dict.items() if k != "estimated_cost"}
                    if update_only:
                        supabase.table("projects").update(legacy_payload).eq("project_name", proj.project_name).eq("utility_company", proj.utility_company).execute()
                        print(f"Updated: [{proj.utility_company}] {proj.project_name} | Cost: ${proj.price}")
                    else:
                        supabase.table("projects").insert(legacy_payload).execute()
                        print(f"Inserted: [{proj.utility_company}] {proj.project_name} | Cost: ${proj.price}")
                    success_count += 1
                    continue
                if 'column "price" does not exist' in error_text:
                    normalized_payload = {k: v for k, v in project_dict.items() if k != "price"}
                    if update_only:
                        supabase.table("projects").update(normalized_payload).eq("project_name", proj.project_name).eq("utility_company", proj.utility_company).execute()
                        print(f"Updated: [{proj.utility_company}] {proj.project_name} | Cost: ${proj.price}")
                    else:
                        supabase.table("projects").insert(normalized_payload).execute()
                        print(f"Inserted: [{proj.utility_company}] {proj.project_name} | Cost: ${proj.price}")
                    success_count += 1
                    continue
            except Exception as retry_error:
                action = "update" if update_only else "insert"
                print(f"Failed to {action} '{proj.project_name}' after retry: {retry_error}")
                continue
            action = "update" if update_only else "insert"
            print(f"Failed to {action} '{proj.project_name}': {e}")

    action_word = "updated" if update_only else "stored"
    print(f"\nSuccessfully {action_word} {success_count}/{len(extracted_data.projects)} records with pricing in Supabase!")

    if not update_only:
        processed_dir = script_dir / "processed"
        processed_dir.mkdir(exist_ok=True)
        file_path.rename(processed_dir / file_path.name)
        print(f"Moved {file_path.name} to 'processed/' folder.")

if __name__ == "__main__":
    processed_dir = script_dir / "processed"
    processed_dir.mkdir(exist_ok=True)

    for pdf_file in processed_dir.glob("*.pdf"):
        print(f"Rescanning processed PDF (update mode): {pdf_file.name}")
        process_single_pdf(pdf_file, update_only=True)

    for pdf_file in script_dir.glob("*.pdf"):
        print(f"Found new PDF to process: {pdf_file.name}")
        process_single_pdf(pdf_file)