import os
import json
import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import openai
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = "asst_F5NLC8GjoWIo6vBG903g53JJ"
MAX_MESSAGE_LENGTH = 4096  # Characters
WEBSOCKET_TIMEOUT = 300.0  # 5 minutes
PING_INTERVAL = 30.0  # 30 seconds

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.thread_map: Dict[str, str] = {}  # Maps connection_id to thread_id

    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        logger.info(f"Connection {connection_id} established")

    def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            if connection_id in self.thread_map:
                del self.thread_map[connection_id]
            logger.info(f"Connection {connection_id} removed")

manager = ConnectionManager()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "connections": len(manager.active_connections)
    }

@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    logger.info("Serving frontend")
    with open("app/static/index.html") as f:
        return HTMLResponse(content=f.read())

async def handle_assistant_stream(websocket: WebSocket, thread_id: str, user_input: str):
    client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=30.0)
    
    try:
        # Add user message to thread
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )
        logger.info(f"Message added to thread {thread_id}: {message.id}")

        # Create and stream run
        stream = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
            stream=True
        )
        
        full_response = ""
        for event in stream:
            if event.event == "thread.message.delta":
                for delta in event.data.delta.content:
                    if delta.type == "text":
                        text = delta.text.value
                        full_response += text
                        await websocket.send_text(json.dumps({
                            "type": "partial_response",
                            "content": text
                        }))
        
        logger.info(f"Completed response for thread {thread_id}")
        await websocket.send_text(json.dumps({
            "type": "final_response",
            "content": full_response
        }))
        
    except Exception as e:
        logger.error(f"Assistant error in thread {thread_id}: {str(e)}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Assistant processing error: {str(e)}"
        }))
        raise

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = str(id(websocket))
    await manager.connect(websocket, connection_id)
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=30.0)
        
        # Create new thread for this connection
        thread = client.beta.threads.create()
        manager.thread_map[connection_id] = thread.id
        logger.info(f"Created thread {thread.id} for connection {connection_id}")

        await websocket.send_text(json.dumps({
            "type": "debug",
            "message": f"Connected to thread {thread.id}",
            "connection_id": connection_id
        }))

        # Start ping task
        async def send_pings():
            while True:
                await asyncio.sleep(PING_INTERVAL)
                try:
                    await websocket.send_text(json.dumps({
                        "type": "ping",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                except:
                    break

        ping_task = asyncio.create_task(send_pings())

        while True:
            try:
                # Wait for message with timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=WEBSOCKET_TIMEOUT
                )
                
                try:
                    message_data = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }))
                    continue

                # Validate message
                if not isinstance(message_data, dict) or not message_data.get("content"):
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid message format"
                    }))
                    continue

                if len(message_data["content"]) > MAX_MESSAGE_LENGTH:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Message exceeds {MAX_MESSAGE_LENGTH} character limit"
                    }))
                    continue

                # Process message
                if message_data.get("type") == "audio":
                    logger.info(f"Received audio message in thread {thread.id}")
                    await websocket.send_text(json.dumps({
                        "type": "debug",
                        "message": "Audio processing placeholder"
                    }))
                else:
                    await handle_assistant_stream(
                        websocket,
                        thread.id,
                        message_data["content"]
                    )

            except asyncio.TimeoutError:
                logger.warning(f"Connection {connection_id} timeout")
                await websocket.send_text(json.dumps({
                    "type": "warning",
                    "message": "Connection timeout - sending ping"
                }))
                continue

            except WebSocketDisconnect:
                logger.info(f"Client {connection_id} disconnected")
                break

            except Exception as e:
                logger.error(f"Error in connection {connection_id}: {str(e)}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Processing error: {str(e)}"
                }))
                break

    except Exception as e:
        logger.error(f"Connection error {connection_id}: {str(e)}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Connection error: {str(e)}"
        }))
    finally:
        ping_task.cancel()
        manager.disconnect(connection_id)
        try:
            await websocket.close()
        except:
            pass
        logger.info(f"Connection {connection_id} closed")

@app.on_event("startup")
async def startup():
    logger.info("Starting server...")
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        models = client.models.list()
        logger.info(f"OpenAI connection verified, {len(models.data)} models available")
        
        # Verify assistant exists
        assistant = client.beta.assistants.retrieve(ASSISTANT_ID)
        logger.info(f"Assistant loaded: {assistant.name} (ID: {assistant.id})")
        
    except Exception as e:
        logger.error(f"Startup verification failed: {str(e)}")
        raise