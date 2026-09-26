from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from supabase import create_client
from agent import run_targeted_analysis # Import your agent logic

app = FastAPI(title="GridSync FL API")

# Enable CORS for your frontend development server
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
    response = supabase.table("projects").select("*").execute()
    return response.data

@app.post("/api/analyze")
def analyze_projects(payload: AnalysisRequest):
    try:
        report = run_targeted_analysis(payload.project_ids)
        return {"report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))