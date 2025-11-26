# app/services/vector_adapter.py
import os
from dotenv import load_dotenv

load_dotenv()

VECTOR_DB = os.getenv("VECTOR_DB", "pinecone").lower()
if VECTOR_DB != "pinecone":
    raise RuntimeError("This setup file is for VECTOR_DB=pinecone only. Set VECTOR_DB=pinecone")

from .pinecone_adapter import PineconeAdapter
adapter = PineconeAdapter()
