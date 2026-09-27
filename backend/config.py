import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

# .env lives at the repo root, one level above backend/
load_dotenv(REPO_ROOT / ".env")


def _env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().strip('"').strip("'") or None


class Config:
    SUPABASE_URL = _env_value("SUPABASE_URL")
    SUPABASE_KEY = _env_value("SUPABASE_KEY")
    GEMINI_API_KEY = _env_value("GEMINI_API_KEY")
    GEMINI_MODEL = _env_value("GEMINI_MODEL") or "gemini-3.8-flash"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit
    CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
    # Production build of the React app (npm run build), served by Flask when present.
    FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
