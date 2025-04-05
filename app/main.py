import os
import re
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from tempfile import NamedTemporaryFile
from openai import OpenAI
import traceback

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_F5NLC8GjoWIo6vBG903g53JJ")
thread_store = {}

# Validate ASSISTANT_ID at startup
if not ASSISTANT_ID or not ASSISTANT_ID.startswith("asst_"):
    raise ValueError("ASSISTANT_ID must be set and start with 'asst_'")

@app.get("/")
async def serve_index():
    return FileResponse("app/static/index.html")

@app.get("/favicon.ico")
async def serve_favicon():
    favicon_path = "app/static/favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return JSONResponse({"error": "Favicon not found"}, status_code=404)

@app.post("/chat/audio")
async def chat_audio(file: UploadFile = File(...), session_id: str = Form(...)):
    try:
        # Save audio temporarily
        with NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        try:
            # Transcribe with Whisper
            with open(tmp_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
                user_input = transcription.strip()
                print(f"Transcribed: {user_input}")

            if not user_input:
                return JSONResponse({"error": "No speech detected"}, status_code=400)

            # Manage conversation thread
            if session_id not in thread_store:
                thread = client.beta.threads.create()
                thread_store[session_id] = thread.id

            # Add user message to thread
            client.beta.threads.messages.create(
                thread_id=thread_store[session_id],
                role="user",
                content=user_input
            )

            # Run Assistant and get response
            try:
                run = client.beta.threads.runs.create_and_poll(
                    thread_id=thread_store[session_id],
                    assistant_id=ASSISTANT_ID
                )
            except client.error.BadRequestError as e:
                return JSONResponse({"error": f"Invalid assistant_id: {str(e)}"}, status_code=400)

            if run.status != "completed":
                return JSONResponse({"error": "Assistant failed to respond"}, status_code=500)

            messages = client.beta.threads.messages.list(thread_id=thread_store[session_id])
            assistant_reply = messages.data[0].content[0].text.value.strip()
            print(f"Assistant reply (raw): {assistant_reply}")

            if not assistant_reply:
                return JSONResponse({"error": "Empty assistant response"}, status_code=500)

            # Sanitize reply: Replace Unicode citation markers with simple [number]
            assistant_reply_sanitized = re.sub(r'[【]([\d]+)[】]', r'[\1]', assistant_reply)
            print(f"Assistant reply (sanitized): {assistant_reply_sanitized}")

            # Generate TTS with sanitized reply
            tts_response = client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=assistant_reply_sanitized
            )

            # Stream audio response
            def generate_audio():
                for chunk in tts_response.iter_bytes():
                    yield chunk

            return StreamingResponse(
                generate_audio(),
                media_type="audio/mpeg",
                headers={"X-Transcript": assistant_reply_sanitized.encode("utf-8").decode("utf-8")}
            )

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except UnicodeEncodeError as e:
        print(f"Unicode error: {str(e)}")
        return JSONResponse({"error": "Response contains unsupported characters"}, status_code=500)
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)