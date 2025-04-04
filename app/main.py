import os
import json
import logging
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import openai
from dotenv import load_dotenv
import time
import base64
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = "asst_F5NLC8GjoWIo6vBG903g53JJ"
MAX_MESSAGE_LENGTH = 4096  # Characters

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    logger.info("Serving frontend")
    with open("app/static/index.html") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        # Initialize OpenAI client with timeout
        client = openai.OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=30.0
        )
        logger.info("OpenAI client initialized")

        # Create thread
        thread = client.beta.threads.create()
        logger.info(f"Thread created: {thread.id}")

        # Send debug message
        await websocket.send_text(json.dumps({
            "type": "debug",
            "message": f"Connected to thread {thread.id}"
        }))

        while True:
            try:
                # Receive message with timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=300.0)
                logger.info(f"Received message: {data[:100]}...")  # Log first 100 chars
                
                message_data = json.loads(data)
                
                # Validate message
                if not message_data.get("content"):
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Empty message content"
                    }))
                    continue
                
                if len(message_data["content"]) > MAX_MESSAGE_LENGTH:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Message too long (max {MAX_MESSAGE_LENGTH} chars)"
                    }))
                    continue

                # Handle audio or text input
                if message_data.get("type") == "audio":
                    logger.info("Processing audio message")
                    # In production: Use Whisper API to transcribe
                    await websocket.send_text(json.dumps({
                        "type": "debug",
                        "message": "Audio processing would happen here"
                    }))
                else:
                    # Add message to thread
                    message = client.beta.threads.messages.create(
                        thread_id=thread.id,
                        role="user",
                        content=message_data["content"]
                    )
                    logger.info(f"Message added: {message.id}")

                    # Create run with streaming
                    stream = client.beta.threads.runs.create(
                        thread_id=thread.id,
                        assistant_id=ASSISTANT_ID,
                        stream=True
                    )
                    logger.info("Run created, streaming...")

                    full_response = ""
                    for event in stream:
                        logger.debug(f"Event: {event.event}")
                        if event.event == "thread.message.delta":
                            for delta in event.data.delta.content:
                                if delta.type == "text":
                                    text = delta.text.value
                                    full_response += text
                                    await websocket.send_text(json.dumps({
                                        "type": "partial_response",
                                        "content": text
                                    }))
                    
                    logger.info(f"Final response: {full_response[:100]}...")
                    await websocket.send_text(json.dumps({
                        "type": "final_response",
                        "content": full_response
                    }))

            except asyncio.TimeoutError:
                logger.warning("Connection timeout, sending ping")
                await websocket.send_text(json.dumps({
                    "type": "debug",
                    "message": "ping"
                }))
                continue
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
                continue

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Server error: {str(e)}"
        }))
    finally:
        logger.info("Closing connection")
        await websocket.close()

@app.on_event("startup")
async def startup():
    logger.info("Starting up...")
    # Warm-up OpenAI connection
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        client.models.list()
        logger.info("OpenAI connection verified")
    except Exception as e:
        logger.error(f"OpenAI connection failed: {str(e)}")