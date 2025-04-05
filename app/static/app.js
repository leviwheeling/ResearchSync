const recordBtn = document.getElementById('recordBtn');
const statusText = document.getElementById('status');
const responseAudio = document.getElementById('responseAudio');
const assistantText = document.getElementById('assistantText');

let mediaRecorder;
let audioChunks = [];
const sessionId = sessionStorage.getItem('session_id') || crypto.randomUUID();
sessionStorage.setItem('session_id', sessionId);

recordBtn.addEventListener('click', async () => {
  if (!mediaRecorder || mediaRecorder.state === 'inactive') {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    audioChunks = [];
    mediaRecorder.ondataavailable = (event) => audioChunks.push(event.data);

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      const formData = new FormData();
      formData.append('file', audioBlob, 'recording.webm');
      formData.append('session_id', sessionId);

      statusText.textContent = 'Transcribing & thinking... 🔄';
      assistantText.classList.add('hidden');
      responseAudio.classList.add('hidden');

      try {
        const response = await fetch('/chat/audio', {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          statusText.textContent = `Server error: ${response.status}`;
          return;
        }

        // Read custom header for transcript if returned
        const assistantReply = response.headers.get('X-Transcript') || '';
        if (assistantReply) {
          assistantText.textContent = `"${assistantReply}"`;
          assistantText.classList.remove('hidden');
        }

        const audioData = await response.blob();
        const audioUrl = URL.createObjectURL(audioData);
        responseAudio.src = audioUrl;
        responseAudio.classList.remove('hidden');
        responseAudio.play();

        statusText.textContent = 'Assistant response:';
      } catch (err) {
        console.error(err);
        statusText.textContent = '⚠️ Connection failed.';
      }
    };

    mediaRecorder.start();
    statusText.textContent = '🎙️ Listening... click again to stop';
  } else {
    mediaRecorder.stop();
    statusText.textContent = '⌛ Processing...';
  }
});
