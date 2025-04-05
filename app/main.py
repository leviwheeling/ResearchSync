import os
import json
import logging
import asyncio
import base64
import tempfile
import audioop
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import openai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VAD_THRESHOLD = 500  # Medium sensitivity for background noise
VAD_WINDOW = 15      # 150ms analysis window

class ConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.audio_buffers = {}
        self.vad_states = {}  # Voice Activity Detection states

    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.audio_buffers[connection_id] = b''
        self.vad_states[connection_id] = {
            'buffer': deque(maxlen=VAD_WINDOW),
            'speaking': False
        }

    async def process_audio_chunk(self, connection_id: str, chunk: bytes):
        # VAD processing
        rms = audioop.rms(chunk, 2)  # 16-bit samples
        vad_state = self.vad_states[connection_id]
        vad_state['buffer'].append(rms > VAD_THRESHOLD)
        
        # Detect voice activity (60% of window)
        voice_detected = sum(vad_state['buffer']) / VAD_WINDOW > 0.6
        
        if voice_detected and not vad_state['speaking']:
            vad_state['speaking'] = True
            await self.active_connections[connection_id].send_json({
                "type": "vad_status",
                "status": "speaking"
            })
        elif not voice_detected and vad_state['speaking']:
            vad_state['speaking'] = False
            await self.handle_audio_completion(connection_id)
            await self.active_connections[connection_id].send_json({
                "type": "vad_status",
                "status": "waiting"
            })

    async def handle_audio_completion(self, connection_id: str):
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        audio_data = self.audio_buffers.get(connection_id, b'')
        
        if not audio_data:
            return

        try:
            # Stream audio to GPT-4o and get both text and audio response
            with tempfile.NamedTemporaryFile(suffix=".webm") as tmp:
                tmp.write(audio_data)
                tmp.seek(0)
                
                response = client.chat.completions.create(
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
                    stream=True
                )

                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        full_response += text
                        
                        # Send text updates
                        await self.active_connections[connection_id].send_json({
                            "type": "response.delta",
                            "content": text
                        })
                
                # Get audio response
                tts = client.audio.speech.create(
                    model="tts-1-hd",
                    voice="nova",
                    input=full_response,
                    response_format="opus"
                )
                
                # Send audio response
                await self.active_connections[connection_id].send_bytes(
                    tts.content
                )

        except Exception as e:
            logging.error(f"Error: {str(e)}")
            await self.active_connections[connection_id].send_json({
                "type": "error",
                "message": str(e)
            })
        finally:
            self.audio_buffers[connection_id] = b''

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = str(id(websocket))
    await manager.connect(websocket, connection_id)
    
    try:
        while True:
            data = await websocket.receive()
            
            if isinstance(data, str):
                message = json.loads(data)
                if message.get("type") == "ping":
                    continue
                    
            elif data.type == "websocket.receive.bytes":
                await manager.process_audio_chunk(connection_id, data)
                manager.audio_buffers[connection_id] += data
                
    except WebSocketDisconnect:
        logging.info(f"Client disconnected: {connection_id}")
    finally:
        del manager.active_connections[connection_id]
        del manager.audio_buffers[connection_id]
        del manager.vad_states[connection_id]

@app.on_event("startup")
async def startup():
    logging.info("GPT-4o Assistant Ready")