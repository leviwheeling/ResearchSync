# app/main.py
import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from tempfile import NamedTemporaryFile
from openai import OpenAI
from openai._base_client import SyncHttpxClientWrapper

# ✅ Safe client with Assistant v2 opt-in and no proxy bug
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    default_headers={"OpenAI-Beta": "assistants=v2"},
    http_client=SyncHttpxClientWrapper()
)

ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_F5NLC8GjoWIo6vBG903g53JJ")

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("app/static/index.html")

# Store thread per session
thread_store = {}

@app.post("/chat/audio")
async def chat_audio(file: UploadFile = File(...), session_id: str = Form(...)):
    try:
        # Save audio
        with NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # Transcribe with Whisper
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            user_input = transcription.text.strip()
            print(f"[DEBUG] Transcription: {user_input}")

        if not user_input:
            return JSONResponse(content={"error": "Empty transcription"}, status_code=400)

        # Thread management
        if session_id not in thread_store:
            thread = client.beta.threads.create()
            thread_store[session_id] = thread.id

        client.beta.threads.messages.create(
            thread_id=thread_store[session_id],
            role="user",
            content=user_input
        )

        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_store[session_id],
            assistant_id=ASSISTANT_ID
        )

        # Get response
        messages = client.beta.threads.messages.list(thread_id=thread_store[session_id])
        reply = messages.data[0].content[0].text.value.strip()
        print(f"[DEBUG] Assistant reply: {reply}")

        if not reply:
            return JSONResponse(content={"error": "Empty assistant reply"}, status_code=400)

        # Convert to speech
        try:
            tts_audio = client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=reply
            )
        except Exception as e:
            print(f"[ERROR] TTS failed: {e}")
            return JSONResponse(content={"error": "TTS failed"}, status_code=500)

        return StreamingResponse(
            tts_audio.iter_bytes(),
            media_type="audio/mpeg",
            headers={"X-Transcript": reply}
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)
