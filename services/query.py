# services/query.py
from .pinecone_client import index
from .embeddings import embed_text
from routes.agent import Message    

user_id = Message.user_id  # Example user_id, replace with actual user context if needed

def search_documents(query: str, top_k: int = 5):
    q_emb = embed_text(query)

    results = index.query(
        vector=q_emb,
        top_k=top_k,
        include_metadata=True,
        namespace=user_id 
    )

    return results
