import os
from pathlib import Path

from dotenv import load_dotenv

# .env lives at the repo root, one level above backend/
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
