# services/agent_tools.py

from openai import OpenAI
import os
from services.embeddings import chunk_text
from services.vector_adapter import adapter
from dotenv import load_dotenv
load_dotenv()

async def query_user_documents(user_id: str, query: str, top_k: int = 5):
    # 1️⃣ Embed the query
    qvec = (await chunk_text([query]))[0]

    # 2️⃣ Query vector DB for top relevant chunks
    res = await adapter.query(namespace=user_id, vector=qvec, top_k=top_k)

    # 3️⃣ Fetch actual text content if needed
    documents = []
    for item in res["matches"]:
        # item["metadata"] contains storage_ref, chunk_index, excerpt
        documents.append(item["metadata"]["excerpt"])
    return documents





openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def agent_answer(user_id: str, question: str):
    docs = await query_user_documents(user_id, question, top_k=5)
    context = "\n\n".join(docs)

    # Pass context + question to your LLM
    prompt = f"Context:\n{context}\n\nQuestion: {question}"
    response = await openai.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content
