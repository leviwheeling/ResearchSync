# app/main.py
import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from tempfile import NamedTemporaryFile
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# Ensure the OpenAI API key is set
# Load API config
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_F5NLC8GjoWIo6vBG903g53JJ")

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("app/static/index.html")

# Store threads per session
thread_store = {}

@app.post("/chat/audio")
async def chat_audio(file: UploadFile = File(...), session_id: str = Form(...)):
    # Save incoming audio to temp file
    with NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # Transcribe audio to text using Whisper (OpenAI SDK v1.x)
    with open(tmp_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        user_input = transcription.text

    # Thread per session
    if session_id not in thread_store:
        thread = client.beta.threads.create()
        thread_store[session_id] = thread.id

    # Submit message to assistant thread
    client.beta.threads.messages.create(
        thread_id=thread_store[session_id],
        role="user",
        content=user_input
    )

    # Run assistant and wait for completion
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_store[session_id],
        assistant_id=ASSISTANT_ID
    )

    # Fetch the assistant's reply
    messages = client.beta.threads.messages.list(thread_id=thread_store[session_id])
    reply = messages.data[0].content[0].text.value

    # Convert reply text to TTS audio
    tts_audio = client.audio.speech.create(
        model="tts-1",
        voice="nova",  # Options: shimmer, echo, fable, etc.
        input=reply
    )

    # Return audio stream + transcript for frontend display
    return StreamingResponse(
        tts_audio.iter_bytes(),
        media_type="audio/mpeg",
        headers={"X-Transcript": reply}
    )
