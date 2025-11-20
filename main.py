from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os
import logging
import asyncio
from workflow import run_workflow, WorkflowInput
from dotenv import load_dotenv, find_dotenv
from typing import Optional, List, Any, Union

# Configure logging to see detailed errors
logging.basicConfig(level=logging.DEBUG)

load_dotenv(find_dotenv())
app = FastAPI()
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
if not api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable not set")
openai = OpenAI(api_key=api_key)

# Pydantic models for request bodies
class Message(BaseModel):
    session_id: str
    content: Union[str, dict, list]
    user_id: Optional[str] = None

# Fallback model to accept either input_as_text or messages
class ChatFallbackPayload(BaseModel):
    input_as_text: Optional[str] = None
    messages: Optional[List[Any]] = None

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
