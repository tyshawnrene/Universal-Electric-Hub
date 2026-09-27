from flask import Blueprint, abort, jsonify, request

from backend.services.parser import read_file, to_projects

parse_bp = Blueprint("parse", __name__)


@parse_bp.post("/upload")
def upload():
    """Parse an uploaded CSV/XLSX/JSON file (form field "file") into projects."""
    file = request.files.get("file")
    if not file or not file.filename:
        abort(400, description='Send a file in the "file" form field.')

    try:
        df = read_file(file.filename, file.read())
    except ValueError as e:
        abort(400, description=str(e))

    projects, errors = to_projects(df)
    return jsonify(
        count=len(projects),
        projects=[p.model_dump(mode="json") for p in projects],
        errors=errors,
    )
