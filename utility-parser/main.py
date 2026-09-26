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

# 1. Define schema for an individual project
class ProjectRecord(BaseModel):
    project_name: str = Field(description="Name of the transmission project or substation upgrade.")
    utility_company: str = Field(description="Name of the utility operating the project.")
    state: str = Field(description="Two-letter state abbreviation where the project is located.")
    latitude: float = Field(description="Approximate latitude coordinate for the project or nearest substation.")
    longitude: float = Field(description="Approximate longitude coordinate for the project or nearest substation.")
    in_service_date: str = Field(description="Planned in-service date (YYYY-MM-DD or formatted string).")
    project_scope: str = Field(description="Detailed technical description of the project scope and need.")

# 2. Wrap it in a container schema to extract ALL projects from the document
class DocumentExtraction(BaseModel):
    projects: list[ProjectRecord] = Field(description="Complete list of all transmission and capital projects found in the document.")

def parse_pdf_file(file_path: Path):
    print(f"Uploading {file_path.name} to Gemini Files API...")
    uploaded_file = client.files.upload(file=file_path)
    print(f"File uploaded successfully. Remote URI Name: {uploaded_file.name}")

    prompt = """
    Extract EVERY SINGLE transmission project, line rebuild, and substation upgrade listed in this document. 
    Do not skip any projects. For each project, extract the exact name, utility company, state, approximate latitude and longitude coordinates, planned in-service date, and detailed project scope.
    """

    max_retries = 5
    response = None
    
    for attempt in range(max_retries):
        try:
            print(f"Running Gemini extraction analysis (Attempt {attempt + 1}/{max_retries})...")
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",  # Using a stable production model with separate quota limits
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

    # Cleanup remote file
    client.files.delete(name=uploaded_file.name)
    print("Cleanup complete.")

    return response.parsed

def process_single_pdf(file_path: Path):
    extracted_data = parse_pdf_file(file_path)
    
    if not extracted_data or not extracted_data.projects:
        print("No projects extracted from PDF.")
        return

    print(f"\n--- Extracted {len(extracted_data.projects)} Projects ---")
    
    # Loop through every extracted project and push to Supabase individually
    for proj in extracted_data.projects:
        project_dict = proj.model_dump()
        
        try:
            res = supabase.table("projects").insert(project_dict).execute()
            print(f"Pushed to Supabase: {proj.project_name}")
        except Exception as e:
            print(f"Failed to push project '{proj.project_name}': {e}")

    # Move processed file
    processed_dir = script_dir / "processed"
    processed_dir.mkdir(exist_ok=True)
    file_path.rename(processed_dir / file_path.name)
    print(f"Moved {file_path.name} to 'processed/' folder.")

if __name__ == "__main__":
    for pdf_file in script_dir.glob("*.pdf"):
        print(f"Found new PDF to process: {pdf_file.name}")
        process_single_pdf(pdf_file)