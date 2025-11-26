# back_end/routes/documents.py
from fastapi import APIRouter, UploadFile
import uuid, os, logging
from services.file_processing import extract_text_from_file_bytes
from services.embeddings import client, embedding_model
from services.pinecone_client import index
from services.chunker import chunk_text_by_tokens, compute_chunk_hash              
from services.supabase_client import supabase
from fastapi import Form

router = APIRouter()
logger = logging.getLogger(__name__)




@router.post("/documents/upload")
async def upload_document(file: UploadFile, user_id: str = Form(...)):

    content = await file.read()

    # Upload to Supabase Storage
    path = f"{uuid.uuid4()}-{file.filename}"

    supabase.storage.from_("documents").upload(
        path,
        content,
        {"content-type": file.content_type},
    )

    # Extract text
    text = extract_text_from_file_bytes(file.filename, content)

    # Embed & store in Pinecone
    chunks = chunk_text_by_tokens(text)

    for chunk_text, start, end in chunks:
        chunk_id = compute_chunk_hash(path, start, end)
        embedding = client.embeddings.create(
            model=embedding_model,
            input=chunk_text
        )
        
        index.upsert(
            vectors=[
                {
                    "id": chunk_id,
                    "values": embedding.data[0].embedding,
                    "metadata": {
                        "text": chunk_text,
                        "file_name": file.filename
                    }
                }
            ],
            namespace=user_id
        )

    return {"message": "uploaded"}

