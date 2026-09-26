import pandas as pd
from flask import Blueprint, abort, jsonify, request

from services.parser import to_projects
from services.project_repo import list_projects
from services.proximity import find_overlaps

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.get("/overlaps")
def overlaps_from_db():
    """Find overlapping project pairs among everything in Supabase.

    Query params: max_km (default 40), state, utility, cross_utility_only (true/false)
    """
    max_km = request.args.get("max_km", 40.0, type=float)
    cross_only = request.args.get("cross_utility_only", "false").lower() == "true"
    projects, errors = list_projects(request.args.get("state"), request.args.get("utility"))

    results = find_overlaps(projects, max_km)
    if cross_only:
        results = [o for o in results if o["cross_utility"]]
    return jsonify(count=len(results), overlaps=results, errors=errors)


@analysis_bp.post("/overlaps")
def overlaps():
    """Find project pairs within max_km of each other, for projects sent in the body.

    Body: {"projects": [...], "max_km": 40}
    """
    body = request.get_json(silent=True) or {}
    rows = body.get("projects")
    if not isinstance(rows, list) or len(rows) < 2:
        abort(400, description='Body must include a "projects" list with at least 2 items.')

    projects, errors = to_projects(pd.DataFrame(rows))
    max_km = float(body.get("max_km", 40.0))
    results = find_overlaps(projects, max_km)
    return jsonify(count=len(results), overlaps=results, errors=errors)
