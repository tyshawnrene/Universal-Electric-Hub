import pandas as pd
from flask import Blueprint, abort, jsonify, request

from backend.services.parser import to_projects
from backend.services.project_repo import insert_projects, list_projects

projects_bp = Blueprint("projects", __name__)


@projects_bp.get("")
def get_projects():
    """List projects from Supabase. Optional filters: ?state=SC&utility=dominion"""
    projects, errors = list_projects(request.args.get("state"), request.args.get("utility"))
    return jsonify(
        count=len(projects),
        projects=[p.model_dump(mode="json") for p in projects],
        errors=errors,
    )


@projects_bp.post("")
def create_projects():
    """Save projects to Supabase. Body: {"projects": [...]}, e.g. the output of /api/parse/upload."""
    body = request.get_json(silent=True) or {}
    rows = body.get("projects")
    if not isinstance(rows, list) or not rows:
        abort(400, description='Body must include a non-empty "projects" list.')

    projects, errors = to_projects(pd.DataFrame(rows))
    if errors:
        return jsonify(error="Validation failed", errors=errors), 422

    inserted = insert_projects(projects)
    return jsonify(count=len(inserted), inserted=inserted), 201
