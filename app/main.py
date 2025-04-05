# app/main.py
import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from tempfile import NamedTemporaryFile
import openai

# Set API key directly (avoids SDK proxy bug)
openai.api_key = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_F5NLC8GjoWIo6vBG903g53JJ")

app = FastAPI()

# Serve static assets
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def index():
    return FileResponse("app/static/index.html")

# Store threads per session
thread_store = {}

@app.post("/chat/audio")
async def chat_audio(file: UploadFile = File(...), session_id: str = Form(...)):
    # Save uploaded audio
    with NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # Transcribe audio with Whisper (OpenAI 1.x API)
    with open(tmp_path, "rb") as audio_file:
        transcription = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        user_input = transcription.text

    # Create or get thread for this session
    if session_id not in thread_store:
        thread = openai.beta.threads.create()
        thread_store[session_id] = thread.id

    # Add user message
    openai.beta.threads.messages.create(
        thread_id=thread_store[session_id],
        role="user",
        content=user_input
    )

    # Run assistant and wait for reply
    run = openai.beta.threads.runs.create_and_poll(
        thread_id=thread_store[session_id],
        assistant_id=ASSISTANT_ID
    )

    # Get assistant reply
    messages = openai.beta.threads.messages.list(thread_id=thread_store[session_id])
    reply = messages.data[0].content[0].text.value

    # Convert text reply to speech
    tts_audio = openai.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=reply
    )

    return StreamingResponse(
        tts_audio.iter_bytes(),
        media_type="audio/mpeg",
        headers={"X-Transcript": reply}
    )
