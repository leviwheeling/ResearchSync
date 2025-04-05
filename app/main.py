# app/main.py
import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from tempfile import NamedTemporaryFile
from openai import OpenAI
from openai._base_client import SyncHttpxClientWrapper

# 🔐 Safe client initialization (avoids proxy bug)
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=SyncHttpxClientWrapper()
)

ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_F5NLC8GjoWIo6vBG903g53JJ")

app = FastAPI()

# Serve static frontend
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("app/static/index.html")

# Session storage for threads
thread_store = {}

@app.post("/chat/audio")
async def chat_audio(file: UploadFile = File(...), session_id: str = Form(...)):
    try:
        # Save audio to disk
        with NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # Transcribe audio with Whisper
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            user_input = transcription.text

        # Create or retrieve thread
        if session_id not in thread_store:
            thread = client.beta.threads.create()
            thread_store[session_id] = thread.id

        # Add message to assistant thread
        client.beta.threads.messages.create(
            thread_id=thread_store[session_id],
            role="user",
            content=user_input
        )

        # Run assistant
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_store[session_id],
            assistant_id=ASSISTANT_ID
        )

        # Retrieve response
        messages = client.beta.threads.messages.list(thread_id=thread_store[session_id])
        reply = messages.data[0].content[0].text.value

        # Convert to audio with TTS
        tts_audio = client.audio.speech.create(
            model="tts-1",
            voice="nova",  # shimmer, echo, fable, etc.
            input=reply
        )

        # Return response
        return StreamingResponse(
            tts_audio.iter_bytes(),
            media_type="audio/mpeg",
            headers={"X-Transcript": reply}
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
