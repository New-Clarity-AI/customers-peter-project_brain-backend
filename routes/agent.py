# back_end/routes/agent.py
from typing import Union, Optional, List, Dict
from fastapi import APIRouter, HTTPException
from openai import OpenAI
from .vector import query_vector
from pydantic import BaseModel
from dotenv import load_dotenv
from services.embeddings import embed_text
from services.pinecone_client import index
import os



load_dotenv()
list=List
dict=Dict

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



# Define the request model
class Message(BaseModel):
    session_id: str
    content: Union[str, Dict, List]
    user_id: Optional[str] = None


@router.post("/agent/answer")
def agent_answer(req: Message):
    q = req.content
    user_ns = req.user_id
    #if not user_ns:
       # raise HTTPException(status_code=400, detail="user_id is required")


    # 1) query embedding
    q_emb = embed_text(q)

    # 2) pinecone search (filter by user_id if desired)
    # include_metadata True to get stored snippet
    results = index.query(
        vector=q_emb,
        top_k=5,
        include_metadata=True,
        namespace=user_ns   # ← ADD THIS
    )


    # 3) build context (concatenate top matches)
    matches = results.get("matches", [])
    context = "\n\n".join([m["metadata"].get("text", "") for m in matches])

    # 4) prompt the LLM (GPT-5.1)
    system_prompt = (
        "You are a helpful assistant. Use ONLY the provided context to answer. "
        "If the answer is not present, say \"I don't see this in uploaded documents.\""
        " Answer concisely and don't include **markdown** formatting."
    )
    prompt = f"{system_prompt}\n\nCONTEXT:\n{context}\n\nQUESTION:\n{q}"

    response = client.responses.create(model="gpt-5.1", input=prompt)

    return {
        "session_id": req.session_id,
        "message": response.output_text
    }