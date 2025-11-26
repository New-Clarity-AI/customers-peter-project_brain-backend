# app/utils/storage.py
import os
from supabase import create_client, Client
from dotenv import load_dotenv


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "documents")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

async def store_full_text(path: str, text: str) -> str:
    """
    Uploads text to Supabase Storage and returns the storage path.
    path example: "tenant_id/uuid-filename.txt"
    """
    if not supabase:
        return ""
    # Supabase Python client storage upload expects bytes
    res = supabase.storage.from_(STORAGE_BUCKET).upload(path, text.encode("utf-8"))
    # In production, check res for errors. Return path to reference in metadata
    return path
