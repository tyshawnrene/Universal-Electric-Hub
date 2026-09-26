import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Initialize the official Google GenAI client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# 1. Define the exact data schema you want the output to match
class UtilityProject(BaseModel):
    utility_name: str = Field(description="Name of the utility company, e.g., FPL or Duke Energy")
    project_name: str = Field(description="Name or title of the construction project")
    project_type: str = Field(description="Type of work, e.g., Substation Upgrade, Transmission Line")
    latitude: float = Field(description="Approximate latitude coordinate")
    longitude: float = Field(description="Approximate longitude coordinate")
    start_date: str = Field(description="Start date in YYYY-MM-DD format")
    end_date: str = Field(description="End date in YYYY-MM-DD format")
    estimated_cost_millions: float = Field(description="Estimated project cost in millions of dollars")

class UtilityProjectList(BaseModel):
    projects: list[UtilityProject]

def parse_utility_document(file_path: str):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        document_text = f.read()

    print("Sending text to Gemini for structured extraction...")

    # 2. Call Gemini 2.5 Flash with strict JSON schema enforcement
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Extract all planned utility infrastructure projects from this document:\n\n{document_text}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=UtilityProjectList,
            temperature=0.1,  # Low temperature keeps output factual and deterministic
        ),
    )

    print("\n--- Extracted Structured JSON Data ---")
    print(response.text)
    
    # Optional: Save output to a JSON file so your backend guy can immediately import it to Supabase
    output_file = "parsed_projects.json"
    with open(output_file, "w", encoding="utf-8") as out:
        out.write(response.text)
    print(f"\nSaved structured data successfully to {output_file}!")

if __name__ == "__main__":
    parse_utility_document("sample_data.txt")