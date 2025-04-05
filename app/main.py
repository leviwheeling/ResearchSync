import os
import json
import logging
import asyncio
import base64
import tempfile
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import openai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Serve static files from app/static
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VAD_THRESHOLD = 500  # Medium sensitivity

@app.get("/")
async def get_index():
    return FileResponse("app/static/index.html")

class ConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.audio_buffers = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[id(websocket)] = websocket
        self.audio_buffers[id(websocket)] = b''

    async def process_audio(self, websocket: WebSocket, audio_data: bytes):
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            # Save to temp file for GPT-4o processing
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
            logging.error(f"Error: {str(e)}")
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive()
            
            if data["type"] == "websocket.receive.bytes":
                manager.audio_buffers[id(websocket)] += data["bytes"]
                
            elif data["type"] == "websocket.receive.text":
                message = json.loads(data["text"])
                if message.get("type") == "process_audio":
                    await manager.process_audio(
                        websocket,
                        manager.audio_buffers[id(websocket)]
                    )
                    manager.audio_buffers[id(websocket)] = b''
                    
    except WebSocketDisconnect:
        del manager.active_connections[id(websocket)]
        del manager.audio_buffers[id(websocket)]