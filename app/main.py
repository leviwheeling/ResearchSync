# app/main.py
import os
import uuid
import openai
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from tempfile import NamedTemporaryFile

openai.api_key = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_F5NLC8GjoWIo6vBG903g53JJ")

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("app/static/index.html")

thread_store = {}

@app.post("/chat/audio")
async def chat_audio(file: UploadFile = File(...), session_id: str = Form(...)):
    try:
        with NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            transcription = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            user_input = transcription.text.strip()

        if not user_input:
            return JSONResponse(content={"error": "Empty transcription"}, status_code=400)

        # Headers required for v2 assistants
        headers = {"OpenAI-Beta": "assistants=v2"}

        if session_id not in thread_store:
            thread = openai.beta.threads.create(headers=headers)
            thread_store[session_id] = thread.id

        openai.beta.threads.messages.create(
            thread_id=thread_store[session_id],
            role="user",
            content=user_input,
            headers=headers
        )

        run = openai.beta.threads.runs.create_and_poll(
            thread_id=thread_store[session_id],
            assistant_id=ASSISTANT_ID,
            headers=headers
        )

        messages = openai.beta.threads.messages.list(
            thread_id=thread_store[session_id],
            headers=headers
        )
        reply = messages.data[0].content[0].text.value.strip()

        if not reply:
            return JSONResponse(content={"error": "Empty assistant reply"}, status_code=400)

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

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)
