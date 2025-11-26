from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os
import logging
from dotenv import load_dotenv, find_dotenv
from typing import Optional, List, Any, Union
from middleware.auth import SupabaseAuthMiddleware
from supabase import create_client, Client
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
#app.include_router(vector_router)
app.include_router(agent_router)
   


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



