import re
from datetime import date, datetime
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator

# Source data mixes 2- and 4-digit years, e.g. "12/31/23" and "12/31/2024".
DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d")
DATE_PATTERN = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}")


def parse_date(value):
    if value is None or isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    # Free-text values like "10/1/2025 (phase 1) and 10/1/2026 (phase 2)" use the first date.
    match = DATE_PATTERN.search(text)
    candidates = (text, match.group(0)) if match else (text,)
    for candidate in candidates:
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    raise ValueError(f"Unrecognized date: {value!r}")


class Project(BaseModel):
    """Normalized utility capital project record."""

    id: Optional[Union[int, str]] = None
    name: str
    utility: Optional[str] = None
    state: Optional[str] = None
    project_type: Optional[str] = None
    scope: Optional[str] = None
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    in_service_date: Optional[date] = None
    estimated_cost: Optional[float] = None

    @field_validator("start_date", "end_date", "in_service_date", mode="before")
    @classmethod
    def _parse_dates(cls, value):
        return parse_date(value)
