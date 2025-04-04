import os
import json
import uuid
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import openai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Serve frontend files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Realtime API config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = "asst_F5NLC8GjoWIo6vBG903g53JJ"
REALTIME_MODEL = "gpt-4o-realtime-preview-2024-12-17"

@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    with open("app/static/index.html") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    try:
        # Step 1: Create ephemeral session for Realtime API
        session = client.beta.realtime.sessions.create(
            model=REALTIME_MODEL,
            voice="echo",  # Choose from: alloy, echo, fable, onyx, nova, shimmer
            assistant_id=ASSISTANT_ID  # Your custom assistant
        )

        # Step 2: Connect to Realtime API WebSocket
        async with openai.OpenAI(api_key=OPENAI_API_KEY).beta.realtime.connect(
            session_id=session.id,
            assistant_id=ASSISTANT_ID
        ) as realtime_connection:

            # Step 3: Forward messages between client and Realtime API
            while True:
                # Receive from client (browser)
                client_data = await websocket.receive_text()
                await realtime_connection.send(json.dumps({
                    "type": "user_message",
                    "content": client_data
                }))

                # Stream responses from Assistant
                async for event in realtime_connection:
                    if event["type"] == "assistant_message":
                        await websocket.send_text(json.dumps({
                            "type": "assistant_audio",
                            "audio": event["audio"]  # Base64 encoded audio
                        }))
                    elif event["type"] == "transcript":
                        await websocket.send_text(json.dumps({
                            "type": "transcript",
                            "text": event["text"]
                        }))

    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))
    finally:
        await websocket.close()