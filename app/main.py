import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from tempfile import NamedTemporaryFile
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_F5NLC8GjoWIo6vBG903g53JJ")

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def index():
    return FileResponse("app/static/index.html")

thread_store = {}

@app.post("/chat/audio")
async def chat_audio(file: UploadFile = File(...), session_id: str = Form(...)):
    try:
        with NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            transcription = openai.Audio.transcribe("whisper-1", audio_file)
            user_input = transcription["text"]

        if session_id not in thread_store:
            thread = openai.Thread.create()
            thread_store[session_id] = thread["id"]

        openai.ThreadMessage.create(
            thread_id=thread_store[session_id],
            role="user",
            content=user_input
        )

        run = openai.ThreadRun.create_and_poll(
            thread_id=thread_store[session_id],
            assistant_id=ASSISTANT_ID
        )

        messages = openai.ThreadMessage.list(thread_id=thread_store[session_id])
        reply = messages["data"][0]["content"][0]["text"]["value"]

        tts_audio = openai.Audio.speech(
            model="tts-1",
            voice="nova",
            input=reply
        )

        return StreamingResponse(tts_audio, media_type="audio/mpeg", headers={"X-Transcript": reply})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
