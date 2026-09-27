import pandas as pd
import httpx
from flask import Blueprint, abort, current_app, jsonify, request

from backend.services.ai_report import generate_report
from backend.services.parser import to_projects
from backend.services.project_repo import get_projects_by_ids, list_projects
from backend.services.proximity import find_overlaps

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.get("/overlaps")
def overlaps_from_db():
    """Find overlapping project pairs among everything in Supabase.

    Query params: max_km (default 40), state, utility, cross_utility_only (true/false)
    """
    max_km = request.args.get("max_km", 40.0, type=float)
    cross_only = request.args.get("cross_utility_only", "false").lower() == "true"
    try:
        projects, errors = list_projects(request.args.get("state"), request.args.get("utility"))
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        abort(503, description=f"Database connection failed: {exc}")

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


@analysis_bp.post("/report")
def report():
    """AI coordination report for selected projects. Body: {"project_ids": [1, 2, ...]}"""
    body = request.get_json(silent=True) or {}
    ids = body.get("project_ids")
    if not isinstance(ids, list) or len(ids) < 2:
        abort(400, description='Body must include a "project_ids" list with at least 2 ids.')

    try:
        projects = get_projects_by_ids(ids)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        abort(503, description=f"Database connection failed: {exc}")
    if len(projects) < 2:
        abort(404, description="Fewer than 2 of the requested projects were found.")

    overlaps = find_overlaps(projects, max_km=float("inf"))
    try:
        report = generate_report(projects, overlaps)
    except Exception as e:
        current_app.logger.exception("Gemini report failed")
        abort(502, description=f"AI report generation failed: {e}")
    return jsonify(report=report, overlaps=overlaps)
