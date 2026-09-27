from functools import lru_cache

from supabase import Client, create_client

from backend.config import Config


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
