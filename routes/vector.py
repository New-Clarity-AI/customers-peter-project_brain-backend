# back_end/routes/vector.py
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
import os
import uuid
from fastapi import APIRouter
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
router = APIRouter()

embedding_model = os.getenv("EMBEDDING_MODEL")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX"))

def process_document(text: str, filename: str):
    chunks = [text[i:i+800] for i in range(0, len(text), 800)]

    embeds = client.embeddings.create(
        model=embedding_model,
        input=chunks
    )

    vectors = []
    for i, emb in enumerate(embeds.data):
        vectors.append({
            "id": str(uuid.uuid4()),
            "values": emb.embedding,
            "metadata": {"filename": filename, "chunk": i, "text": chunks[i]}
        })

    index.upsert(vectors=vectors)

@router.post("/vector/query")
def query_vector(question: str):
    # Create embedding
    emb = client.embeddings.create(
        model=embedding_model,
        input=question
    )

    # Query vector DB
    results = index.query(
        vector=emb.data[0].embedding,
        top_k=5,
        include_metadata=True
    )

    # Safely return full match objects (NOT just text)
    cleaned_matches = []

    for match in results.get("matches", []):
        if isinstance(match, dict):
            metadata = match.get("metadata", {})
            cleaned_matches.append({
                "score": match.get("score"),
                "id": match.get("id"),
                "metadata": {
                    "text": metadata.get("text", "")
                }
            })

    return {"matches": cleaned_matches}


