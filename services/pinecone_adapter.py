# app/services/pinecone_adapter.py
import os
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_ENV", "us-east-1")




#if not (PINECONE_API_KEY and PINECONE_ENV and PINECONE_INDEX):
#    raise RuntimeError("Set PINECONE_API_KEY, PINECONE_ENV, PINECONE_INDEX")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

class PineconeAdapter:
    def __init__(self):
        self.index = index

    async def upsert_vectors(self, namespace: str, vectors: list[dict[str, any]]):
        """
        vectors: list of {id: str, values: List[float], metadata: dict}
        Uses Pinecone namespace = tenant_id
        """
        # pinecone client is sync but fast; call directly
        self.index.upsert(vectors=vectors, namespace=namespace)
        return {"status": "ok"}

    async def query(self, namespace: str, vector: list[float], top_k: int = 5, filter: dict = None):
        # Pinecone query arguments
        q = dict(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            namespace=namespace,
        )
        if filter:
            q["filter"] = filter
        res = self.index.query(**q)
        return res
