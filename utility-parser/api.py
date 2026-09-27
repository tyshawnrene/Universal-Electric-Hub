from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from supabase import create_client
from pathlib import Path

# Load environment variables
script_dir = Path(__file__).resolve().parent
# Look one level up for the .env file in the root directory
load_dotenv(script_dir.parent / ".env")

from .ai_cross_reference_popup import run_ai_cross_reference_agent
app = FastAPI(title="GridSync FL API")

# Enable CORS so your React frontend can communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class AnalysisRequest(BaseModel):
    project_ids: list[int]

@app.get("/api/projects")
def get_projects():
    try:
        response = supabase.table("projects").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
def analyze_projects(payload: AnalysisRequest):
    try:
        report = run_ai_cross_reference_agent(payload.project_ids)
        return {"report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))