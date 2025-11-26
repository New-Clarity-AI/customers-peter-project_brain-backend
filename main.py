from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os
import logging
import asyncio
from workflow import run_workflow, WorkflowInput
from dotenv import load_dotenv, find_dotenv
from typing import Optional, List, Any, Union
import uuid
from middleware.auth import SupabaseAuthMiddleware, auth_user
from utils.chunker import char_chunk
#from services.embeddings import embed_texts
from services.vector_adapter import adapter
from utils.storage import store_full_text
from utils.chunker import char_chunk
#from services.embeddings import embed_texts
from services.vector_adapter import adapter
import httpx
from services.agent_tools import agent_answer
from fastapi import FastAPI, UploadFile, File, HTTPException
import uuid
from utils.storage import store_full_text
from utils.chunker import char_chunk
from services.embeddings import chunk_text, create_embeddings, store_chunks_in_pinecone
from services.vector_adapter import adapter
from supabase import create_client, Client
from routes.vector import router as vector_router
from routes.agent import router as agent_router
from routes.documents import router as documents_router


# Configure logging to see detailed errors
logging.basicConfig(level=logging.DEBUG)

load_dotenv(find_dotenv())
app = FastAPI()
app.add_middleware(SupabaseAuthMiddleware)
Port = 8001


#Enable CORS for frontend in (adjust domains in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # replace with ["https://yourdomain.com"] in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
openai = OpenAI(api_key=api_key)

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))


# Pydantic models for request bodies
class Message(BaseModel):
    session_id: str
    content: Union[str, dict, list]
    user_id: Optional[str] = None


# Fallback model to accept either input_as_text or messages
class ChatFallbackPayload(BaseModel):
    input_as_text: Optional[str] = None
    messages: Optional[List[Any]] = None


# Document upload via file URL(alternate openai agent method)
class UploadDocumentToolInput(BaseModel):
    file_url: str
    user_id: str


# Include routers
app.include_router(documents_router)
app.include_router(vector_router)
app.include_router(agent_router)
   


@app.post("/agent/query")
async def query_agent(question: str):
    user_id = "test-user"
    answer = await agent_answer(user_id, question)
    return {"answer": answer}



@app.post("/tools/upload_document")
async def upload_document_tool(input: UploadDocumentToolInput):
    # 1. Fetch the file from file_url
    async with httpx.AsyncClient() as client:
        resp = await client.get(input.file_url)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch file")
        content = resp.text  # For PDFs you may need PDF parsing

    # 2. Chunk content
    chunks = char_chunk(content)

    # 3. Embed each chunk
    vectors = []
    embeddings = await chunk_text(chunks)
    for i, emb in enumerate(embeddings):
        vectors.append({
            "id": str(uuid.uuid4()),
            "values": emb,
            "metadata": {
                "user_id": input.user_id,
                "chunk_index": i,
                "excerpt": chunks[i][:500]
            }
        })

    # 4. Upsert into vector DB (e.g., Pinecone)
    await adapter.upsert_vectors(namespace=input.user_id, vectors=vectors)

    return {"status": "ok", "chunks_uploaded": len(chunks)}


# Main chat endpoint supporting flexible input formats
@app.post("/chat")
async def chat(payload: ChatFallbackPayload):
    try:
        # Accept either {"input_as_text": "..."} or {"messages": [...]}
        if payload.input_as_text:
            text = payload.input_as_text
        elif payload.messages:
            # Try to extract the most recent user message
            text = ""
            for m in reversed(payload.messages):
                if isinstance(m, dict) and m.get("role") == "user":
                    content = m.get("content")
                    # content may be a string, dict, or list
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, dict):
                        # support {"type":"text","text":"..."} or similar
                        if content.get("text"):
                            text = content.get("text")
                        else:
                            # fallback: join string values
                            vals = [v for v in content.values() if isinstance(v, str)]
                            text = vals[0] if vals else ""
                    elif isinstance(content, list):
                        # support messages where content is a list of content items
                        for c in content:
                            if isinstance(c, dict) and (c.get("type") in ("input_text", "text") or c.get("text")):
                                text = c.get("text") or c.get("value") or ""
                                break
                    if text:
                        break
            if not text:
                # fallback: join string parts
                parts = []
                for m in payload.messages:
                    if isinstance(m, dict):
                        c = m.get("content")
                        if isinstance(c, str):
                            parts.append(c)
                        elif isinstance(c, dict) and c.get("text"):
                            parts.append(c.get("text"))
                text = " ".join(parts)
        else:
            raise HTTPException(status_code=422, detail="Missing 'input_as_text' or 'messages' in request body")

        # Build WorkflowInput and call the workflow
        workflow_input = WorkflowInput(input_as_text=text)
        my_agent_result = await run_workflow(workflow_input)
        output_text = my_agent_result.get("output_text", "No response generated")
        logging.info(f"Chat response: {output_text}")
        return {"message": str(output_text)}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


# Alias for backward compatibility with frontend expecting /api/chat
@app.post("/api/chat")
async def api_chat(payload: ChatFallbackPayload):
    """Alias for backward compatibility with frontend expecting /api/chat."""
    # Forward to the main chat handler
    return await chat(payload)


# ChatKit message endpoint
@app.post("/api/chatkit/message")
async def send_message(message: Message):
    try:
        logging.info(f"Received message for session {message.session_id}")

        # Normalize content to a simple string for the completion API
        content = message.content
        if isinstance(content, dict):
            content_text = content.get("text") or content.get("value") or ""
        elif isinstance(content, list):
            # find first text-like entry
            content_text = ""
            for c in content:
                if isinstance(c, dict) and (c.get("text") or c.get("value")):
                    content_text = c.get("text") or c.get("value")
                    break
                elif isinstance(c, str):
                    content_text = c
                    break
        else:
            content_text = str(content)

        response = openai.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": content_text}],
            temperature=0,
            max_tokens=2048,
            store=True,
        )

        result = response.choices[0].message.content

        logging.info(f"Response generated for session {message.session_id}")

        return {"message": result}

    except Exception as e:
        logging.error(f"Error handling message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ChatKit session creation endpoint
@app.post("/api/chatkit/session")
def create_chatkit_session():
    try:
        logging.info("Creating ChatKit session...")
        
        # Pass workflow as an object with id property
        session = openai.beta.chatkit.sessions.create(
            user="auto",
            #workflow as an object with id property
            workflow={
                "id": "wf_69135893f40c819095704afbaed0bf0e0d3e74f0b6d2392c"
            }
        )
        
        logging.info(f"Session created: {session.id}")
        return {"client_secret": session.client_secret}
    except Exception as e:
        logging.error(f"Error creating ChatKit session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")


# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=Port)



#=================================================#
#    Previous document upload implementations     #
#=================================================#


#@app.post("/documents/upload")
#async def upload_document(
#    request: Request,
#    file: UploadFile = File(...),
#    #tenant_id: str = Form(...),
#    user_id: str = Depends(auth_user)
#        
#):
#    #tenant_id = request.state.tenant_id
#    user_id = request.state.user_id
#
#    #if not tenant_id:
#    #    raise HTTPException(status_code=401, detail="tenant_id not found")
#
#    
#    content = (await file.read()).decode("utf-8")
#
#    if file and not content:
#        content = (await file.read()).decode("utf-8")
#    if not content:
#        raise HTTPException(status_code=400, detail="No text or file provided")
#
#    # store full text in Supabase Storage (path: tenant/uuid-filename.txt)
#    object_name = f"anonymous/{uuid.uuid4()}-{file.filename or 'upload'}.txt"
#    file_type = file.content_type or 'txt'
#    storage_ref = await store_full_text(object_name, content)
#
#    # chunk content
#    chunks: List[str] = char_chunk(content)
#
#    # embed in batches and build upsert vectors
#    vectors = []
#    batch_size = int(os.getenv("EMBED_BATCH_SIZE", "8"))
#    for i in range(0, len(chunks), batch_size):
#        batch = chunks[i:i + batch_size]
#        embeddings = await embed_texts(batch)
#        for j, emb in enumerate(embeddings):
#            vectors.append({
#                "id": str(uuid.uuid4()),
#                "values": emb,
#                "metadata": {
#                    "tenant_id": tenant_id,
#                    "user_id": user_id,
#                    "file_type": file_type,
#                    "chunk_index": i + j,
#                    "storage_ref": storage_ref,
#                    "excerpt": batch[j][:500]
#                }
#            })
#
#    # Upsert to Pinecone namespace = tenant_id
#    await adapter.upsert_vectors(namespace=tenant_id, vectors=vectors)
#
#    return {"status": "ok", "file": file.filename}
#
#@app.post("/documents/upload")
#async def upload_document(
#    request: Request,
#    file: UploadFile = File(...),
#    # user_id: str = Depends(auth_user)  # Remove auth for testing
#):
#    # Optional: skip user_id for now
#    # user_id = request.state.user_id if hasattr(request.state, "user_id") else "anonymous"
#    
#    content = (await file.read()).decode("utf-8")
#
#    if not content:
#        raise HTTPException(status_code=400, detail="No text or file provided")
#
#    # For testing: just save file locally
#    test_path = f"uploads/{file.filename}"
#    os.makedirs("uploads", exist_ok=True)
#    with open(test_path, "w", encoding="utf-8") as f:
#        f.write(content)
#
#    # Skip embeddings and vector storage completely
#    # chunks = char_chunk(content)
#    # vectors = ...
#    # await adapter.upsert_vectors(...)
#
#    return {"status": "ok", "file": file.filename, "saved_to": test_path}



# In-memory cache for testing real-time queries (optional)
#user_file_chunks = {}  # {user_id: List[dict]}
#
#@app.post("/documents/upload")
#async def upload_document(file: UploadFile = File(...), user_id: str = "anonymous"):
#    if not file:
#        raise HTTPException(status_code=400, detail="No file uploaded")
#
#    content = (await file.read()).decode("utf-8")
#    if not content:
#        raise HTTPException(status_code=400, detail="Empty file")
#
#    # Save full text to Supabase
#    object_name = f"{user_id}/{uuid.uuid4()}-{file.filename}"
#    storage_ref = await store_full_text(object_name, content)
#
#    # Chunk the text
#    chunks = char_chunk(content)
#
#    # Generate embeddings
#    embeddings = await embed_texts(chunks)
#    vectors = []
#    for i, emb in enumerate(embeddings):
#        vectors.append({
#            "id": str(uuid.uuid4()),
#            "values": emb,
#            "metadata": {
#                "user_id": user_id,
#                "chunk_index": i,
#                "storage_ref": storage_ref,
#                "excerpt": chunks[i][:500]
#            }
#        })
#
#    # Upsert to vector DB
#    await adapter.upsert_vectors(namespace=user_id, vectors=vectors)
#
#    # Cache in memory for fast testing (optional)
#    user_file_chunks[user_id] = [{"text": chunks[i], "embedding": emb} for i, emb in enumerate(embeddings)]
#
#    return {"status": "ok", "file": file.filename, "storage_ref": storage_ref}


#@app.post("/documents/upload")
#async def upload_document(file: UploadFile = File(...)):
#    file_content = await file.read()
#
#    supabase.storage.from_("documents").upload(
#        file.filename,
#        file_content,
#        {"content-type": file.content_type, "cache-control": "3600"}
#    )
#
#    public_url = supabase.storage.from_("documents").get_public_url(file.filename)
#
#    return {"status": "uploaded", "url": public_url, "filename": file.filename}



#=================================================#
#        Previous vector query implementation     #
#=================================================#

#@app.post("/vector/query")
#async def vector_query(request: Request, body: dict):
#    tenant_id = request.state.tenant_id
#    if not tenant_id:
#        raise HTTPException(status_code=401, detail="tenant_id missing")
#
#    qtext = body.get("query")
#    if not qtext:
#        raise HTTPException(status_code=400, detail="Missing query")
#
#    top_k = int(body.get("topK", 5))
#    filters = body.get("filters", None)  # optional metadata filter
#
#    qvecs = await chunk_text([qtext])
#    qvec = qvecs[0]
#
#    res = await adapter.query(namespace=tenant_id, vector=qvec, top_k=top_k, filter=filters)
#    return res