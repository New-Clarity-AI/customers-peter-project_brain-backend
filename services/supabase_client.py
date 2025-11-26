# back_end/services/supabase_client.py
import os
from supabase import create_client
import logging

logger = logging.getLogger(__name__)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
BUCKET = os.getenv("SUPABASE_BUCKET", "documents")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Set Supabase env vars")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_file_to_supabase(path: str, content: bytes, content_type: str):
    bucket = supabase.storage.from_(BUCKET)

   
    # Upload file
    res = bucket.upload(path, content)

    # Proper error handling
    if hasattr(res, "error") and res.error:
        raise Exception(res.error)

    return res

def get_public_url(path: str):
    return supabase.storage.from_(BUCKET).get_public_url(path)
