"""Turn uploaded CSV/XLSX/JSON data into validated Project records."""

import io

import pandas as pd
from pydantic import ValidationError

from models.project import Project

# Maps common source column spellings onto Project field names.
COLUMN_ALIASES = {
    "project_name": "name",
    "project": "name",
    "company": "utility",
    "utility_company": "utility",
    "owner": "utility",
    "project_scope": "scope",
    "description": "scope",
    "type": "project_type",
    "latitude": "lat",
    "longitude": "lng",
    "long": "lng",
    "lon": "lng",
    "start": "start_date",
    "end": "end_date",
    "cost": "estimated_cost",
}


def read_file(filename: str, data: bytes) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(data))
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data))
    if name.endswith(".json"):
        return pd.read_json(io.BytesIO(data))
    raise ValueError(f"Unsupported file type: {filename}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))
    return df.rename(columns=COLUMN_ALIASES)


def to_projects(df: pd.DataFrame) -> tuple[list[Project], list[dict]]:
    """Validate each row. Returns (valid projects, per-row errors)."""
    df = normalize_columns(df)
    df = df.astype(object).where(pd.notna(df), None)

    projects, errors = [], []
    for i, row in enumerate(df.to_dict(orient="records")):
        try:
            projects.append(Project.model_validate(row))
        except ValidationError as e:
            errors.append({"row": i, "errors": e.errors(include_url=False, include_input=False, include_context=False)})
    return projects, errors
