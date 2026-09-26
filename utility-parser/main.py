import os
import time
from google.genai.errors import ServerError
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from supabase import create_client, Client

# Resolve paths relative to where this script lives
script_dir = Path(__file__).resolve().parent

# Load environment variables from the .env file inside utility-parser
load_dotenv(script_dir / ".env")

api_key = os.getenv("GEMINI_API_KEY")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables or .env file.")

# Initialize Gemini Client
client = genai.Client(api_key=api_key)

# Initialize Supabase Client (if keys are provided)
supabase: Client = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)

# Define the exact schema you want to extract from the utility PDF
class UtilityProjectExtraction(BaseModel):
    project_name: str = Field(description="The formal title or name of the transmission/grid project.")
    utility_company: str = Field(description="The name of the utility provider (e.g., Dominion Energy, Georgia Power, FPL).")
    state: str = Field(description="Two-letter state abbreviation where the project is located.")
    latitude: float = Field(description="Approximate latitude coordinate of the project site or substation.")
    longitude: float = Field(description="Approximate longitude coordinate of the project site or substation.")
    in_service_date: str = Field(description="Target or actual in-service date (YYYY-MM-DD or descriptive).")
    project_scope: str = Field(description="Brief 1-2 sentence summary of the construction or rebuild work.")

def parse_utility_pdf(pdf_path: str):
    print(f"Uploading {pdf_path} to Gemini Files API...")
    uploaded_file = client.files.upload(file=pdf_path)
    print(f"File uploaded successfully. Remote URI Name: {uploaded_file.name}")

    while uploaded_file.state.name == "PROCESSING":
        print("Processing PDF on server...")
        time.sleep(2)
        uploaded_file = client.files.get(name=uploaded_file.name)

    print("Running Gemini extraction analysis...")

    # Retry loop for 503 high demand spikes
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=[
                    uploaded_file,
                    "Extract the key transmission project metadata from this utility regulatory document. "
                    "Accurately estimate or extract geographic coordinates if mentioned, or derive them from city/substation names if possible."
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=UtilityProjectExtraction,
                    temperature=0.1,
                ),
            )
            break
        except ServerError as e:
            if attempt < max_retries - 1:
                print(f"Model busy (503). Retrying in {(attempt + 1) * 3} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep((attempt + 1) * 3)
            else:
                raise e

    client.files.delete(name=uploaded_file.name)
    print("Cleanup complete.")

    return response.parsed

def save_to_supabase(extracted_data):
    if not supabase:
        print("Supabase credentials not found. Skipping database insert.")
        return

    data_dict = extracted_data.model_dump()
    try:
        response = supabase.table("projects").insert(data_dict).execute()
        print("Successfully pushed new project to Supabase!", response)
    except Exception as e:
        print(f"Error saving to Supabase: {e}")

if __name__ == "__main__":
    # Ensure a processed archive folder exists
    processed_dir = script_dir / "processed"
    processed_dir.mkdir(exist_ok=True)

    # Look for any PDF files in the main utility-parser folder (excluding subfolders)
    pdf_files = [f for f in script_dir.glob("*.pdf") if f.is_file()]
    
    if pdf_files:
        # Grab the first new incoming PDF
        target_pdf = pdf_files[0]
        print(f"Found new PDF to process: {target_pdf.name}")
        
        # Run extraction & push to Supabase
        extracted_data = parse_utility_pdf(str(target_pdf))
        print("\n--- Extracted Structured Data ---")
        print(extracted_data.model_dump_json(indent=2))
        
        save_to_supabase(extracted_data)
        
        # Move the processed PDF to the 'processed' folder so it isn't scanned again
        destination = processed_dir / target_pdf.name
        target_pdf.rename(destination)
        print(f"Moved {target_pdf.name} to 'processed/' folder.")
        
    else:
        print(f"No new PDF files found inside '{script_dir}'. Drop a new PDF into the folder to ingest!")