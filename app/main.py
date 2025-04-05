# app/main.py
import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import openai
from tempfile import NamedTemporaryFile

openai.api_key = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_F5NLC8GjoWIo6vBG903g53JJ")

app = FastAPI()

# Serve static frontend files (index.html, app.js)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def read_index():
    return FileResponse("app/static/index.html")

# In-memory thread tracking
thread_store = {}

@app.post("/chat/audio")
async def chat_audio(file: UploadFile = File(...), session_id: str = Form(...)):
    # Save audio to temp file
    with NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # Transcribe using Whisper
    with open(tmp_path, "rb") as audio_file:
        transcription = openai.Audio.transcribe("whisper-1", audio_file)
        user_input = transcription["text"]

    # Thread logic
    if session_id not in thread_store:
        thread = openai.beta.threads.create()
        thread_store[session_id] = thread.id

    # Add message to assistant thread
    openai.beta.threads.messages.create(
        thread_id=thread_store[session_id],
        role="user",
        content=user_input
    )

    # Run assistant and poll for result
    run = openai.beta.threads.runs.create_and_poll(
        thread_id=thread_store[session_id],
        assistant_id=ASSISTANT_ID
    )

    # Fetch assistant reply
    messages = openai.beta.threads.messages.list(thread_id=thread_store[session_id])
    reply = messages.data[0].content[0].text.value

    # Convert text reply to TTS audio
    tts_audio = openai.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=reply
    )

    return StreamingResponse(tts_audio.iter_bytes(), media_type="audio/mpeg")
