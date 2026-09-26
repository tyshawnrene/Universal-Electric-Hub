import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

# .env lives at the repo root, one level above backend/
load_dotenv(REPO_ROOT / ".env")


class Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    # Production build of the React app (npm run build), served by Flask when present.
    FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
