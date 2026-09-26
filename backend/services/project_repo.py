"""Read/write Project records in the Supabase `projects` table."""

import pandas as pd

from models.project import Project
from services.parser import to_projects
from services.supabase_client import get_supabase

TABLE = "projects"


def to_row(project: Project) -> dict:
    """Map a Project onto the table's column names (id/created_at are DB-generated)."""
    return {
        "project_name": project.name,
        "utility_company": project.utility,
        "state": project.state,
        "latitude": project.lat,
        "longitude": project.lng,
        # Stored as text; match the existing MM/DD/YYYY convention.
        "in_service_date": project.in_service_date.strftime("%m/%d/%Y") if project.in_service_date else None,
        "project_scope": project.scope,
    }


def list_projects(state: str | None = None, utility: str | None = None) -> tuple[list[Project], list[dict]]:
    query = get_supabase().table(TABLE).select("*").order("id")
    if state:
        query = query.eq("state", state)
    if utility:
        query = query.ilike("utility_company", f"%{utility}%")
    rows = query.execute().data
    if not rows:
        return [], []
    return to_projects(pd.DataFrame(rows))


def get_projects_by_ids(ids: list[int]) -> list[Project]:
    rows = get_supabase().table(TABLE).select("*").in_("id", ids).execute().data
    if not rows:
        return []
    projects, _ = to_projects(pd.DataFrame(rows))
    return projects


def insert_projects(projects: list[Project]) -> list[dict]:
    return get_supabase().table(TABLE).insert([to_row(p) for p in projects]).execute().data
