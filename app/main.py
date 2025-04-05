import os
import json
import logging
import asyncio
import base64
import tempfile
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import openai
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

# Serve static files from app/static
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VAD_THRESHOLD = 500  # Medium sensitivity
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB

class ConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.audio_buffers = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        conn_id = id(websocket)
        self.active_connections[conn_id] = websocket
        self.audio_buffers[conn_id] = b''
        logger.info(f"Connected: {conn_id}")
        return conn_id

    async def disconnect(self, conn_id: str):
        if conn_id in self.active_connections:
            del self.active_connections[conn_id]
        if conn_id in self.audio_buffers:
            del self.audio_buffers[conn_id]
        logger.info(f"Disconnected: {conn_id}")

    async def process_audio(self, websocket: WebSocket, audio_data: bytes):
        try:
            if len(audio_data) > MAX_AUDIO_SIZE:
                raise ValueError("Audio too large")
                
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            with tempfile.NamedTemporaryFile(suffix=".webm") as tmp:
                tmp.write(audio_data)
                tmp.flush()
                
                # Get text response
                completion = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": [{
                            "type": "audio_url",
                            "audio_url": {
                                "url": f"data:audio/webm;base64,{base64.b64encode(audio_data).decode()}"
                            }
                        }]
                    }],
                    max_tokens=1000
                )
                
                response_text = completion.choices[0].message.content
                await websocket.send_json({
                    "type": "text_response",
                    "content": response_text
                })
                
                # Get audio response
                speech = client.audio.speech.create(
                    model="tts-1-hd",
                    voice="nova",
                    input=response_text,
                    response_format="opus"
                )
                
                await websocket.send_bytes(speech.content)
                
        except Exception as e:
            logger.error(f"Processing error: {str(e)}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
            except:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    conn_id = await manager.connect(websocket)
    
    try:
        while True:
            try:
                data = await websocket.receive()
                
                if data.get("type") == "websocket.receive.bytes":
                    manager.audio_buffers[conn_id] += data["bytes"]
                    
                elif data.get("type") == "websocket.receive.text":
                    message = json.loads(data["text"])
                    if message.get("type") == "process_audio":
                        await manager.process_audio(
                            websocket,
                            manager.audio_buffers[conn_id]
                        )
                        manager.audio_buffers[conn_id] = b''
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Connection error: {str(e)}")
                break
                
    finally:
        await manager.disconnect(conn_id)

@app.get("/")
async def get_index():
    return FileResponse("app/static/index.html")

@app.on_event("startup")
async def startup():
    logger.info("GPT-4o Assistant Ready")