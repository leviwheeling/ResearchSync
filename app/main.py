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
    
    try:
        # Initialize client with just the API key
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Create thread with your assistant
        thread = client.beta.threads.create()
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Add message to thread
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=message["content"]
            )
            
            # Create run with streaming
            stream = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=ASSISTANT_ID,
                stream=True
            )
            
            # Stream responses
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
            
            await websocket.send_text(json.dumps({
                "type": "final_response",
                "content": full_response
            }))
            
    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))
    finally:
        await websocket.close()