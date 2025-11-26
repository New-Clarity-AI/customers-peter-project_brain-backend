import os
from supabase import create_client, Client
from uuid import uuid4
from dotenv import load_dotenv


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def upload_to_supabase(file, filename):
    bucket = "documents"
    file_ext = filename.split(".")[-1]
    storage_path = f"{uuid4()}.{file_ext}"

    data = await file.read()
    res = supabase.storage.from_(bucket).upload(storage_path, data)

    if res.get("error"):
        raise Exception(res["error"]["message"])

    public_url = supabase.storage.from_(bucket).get_public_url(storage_path)
    return public_url
