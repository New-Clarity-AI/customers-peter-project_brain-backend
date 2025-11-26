from pinecone import Pinecone
import os
from pinecone import ServerlessSpec
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name=os.getenv("PINECONE_INDEX")
index_dim=os.getenv("INDEX_DIM")

INDEX_NAME = index_name
index = pc.Index(INDEX_NAME)

# Create index if not exists
if index_name not in [i["name"] for i in pc.list_indexes()]:
    pc.create_index(
        name=index_name,
        dimension=int(index_dim),
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )

index = pc.Index(index_name)