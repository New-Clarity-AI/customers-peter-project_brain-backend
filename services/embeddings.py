import tiktoken
from openai import OpenAI
from services.pinecone_client import index
import uuid
import os, time
from dotenv import load_dotenv
from typing import List
import logging



load_dotenv()
client = OpenAI()
embedding_model = os.getenv("EMBEDDING_MODEL")
BATCH = int(os.getenv("EMBED_BATCH_SIZE", "64"))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def embed_text(text: str):
    response =client.embeddings.create(model=embedding_model, input=text)
    return response.data[0].embedding


def create_embeddings(chunks: list[str]):
    embeddings = []

    for chunk in chunks:
        emb = embed_text(chunk)
        embeddings.append(emb)

    return embeddings


def chunk_text(text: str, max_tokens=400):
    enc = tiktoken.encoding_for_model("gpt-4.1")
    tokens = enc.encode(text)

    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk = enc.decode(tokens[i:i+max_tokens])
        chunks.append(chunk)

    return chunks

def store_chunks_in_pinecone(chunks, doc_name):
    for chunk in chunks:
        emb = create_embeddings(chunk)
        vector_id = str(uuid.uuid4())

    print("Embedding length:", len(emb))
    print("Upserting into Pinecone...")

    response = index.upsert(
                    vectors=[
                        {"id": vector_id,
                        "values": emb,
                        "metadata": {"text": chunk}
                        }],
                    namespace=user_id  
                    )





    print("Pinecone upsert response:", response)

    return {"status": "chunks_stored"}, logger.info(f"Stored {len(chunks)} chunks for document {doc_name}")

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch texts -> embeddings (simple batching + retry)"""
    out = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i:i+BATCH]
        for attempt in range(3):
            try:
                resp = client.embeddings.create(model=embedding_model, input=batch)
                out.extend([d["embedding"] for d in resp["data"]])
                break
            except Exception as e:
                wait = 2 ** attempt
                time.sleep(wait)
                if attempt == 2:
                    raise
    return out