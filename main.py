from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv, find_dotenv


app = FastAPI()
# Load the nearest .env file (searches parent directories)
load_dotenv(find_dotenv())

# Read the API key from environment (will be populated from .env if present)
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY environment variable is not set. "
        "Set it in PowerShell with: $env:OPENAI_API_KEY='your_key' "
        "then restart the terminal and run the server."
    )

openai = OpenAI(api_key=api_key)

@app.post("/api/chatkit/session")
def create_chatkit_session():
    session = openai.chatkit.sessions.create({
      # ...
    })
    return { client_secret: session.client_secret }
