const recordBtn = document.getElementById('recordBtn');
const statusText = document.getElementById('status');
const responseAudio = document.getElementById('responseAudio');
const assistantText = document.getElementById('assistantText');

let mediaRecorder;
let audioChunks = [];
const sessionId = sessionStorage.getItem('session_id') || crypto.randomUUID();
sessionStorage.setItem('session_id', sessionId);

recordBtn.addEventListener('click', async () => {
  try {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

      audioChunks = [];
      mediaRecorder.ondataavailable = (event) => audioChunks.push(event.data);

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');
        formData.append('session_id', sessionId);

        statusText.textContent = 'Thinking... 🤖';
        assistantText.classList.add('hidden');
        responseAudio.classList.add('hidden');

        const response = await fetch('/chat/audio', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          const errText = await response.text();
          throw new Error(`Server error: ${response.status} - ${errText}`);
        }

        const contentType = response.headers.get('Content-Type');
        if (!contentType || !contentType.includes('audio')) {
          throw new Error('Invalid response: not an audio file');
        }

        const assistantReply = response.headers.get('X-Transcript') || 'No transcript available';
        assistantText.textContent = `"${assistantReply}"`;
        assistantText.classList.remove('hidden');

        const audioData = await response.blob();
        const audioUrl = URL.createObjectURL(audioData);
        responseAudio.src = audioUrl;
        responseAudio.classList.remove('hidden');
        await responseAudio.play();

        statusText.textContent = '✅ Done';
      };

      mediaRecorder.start();
      statusText.textContent = '🎙️ Recording... click to stop';
    } else {
      mediaRecorder.stop();
      mediaRecorder.stream.getTracks().forEach(track => track.stop()); // Clean up stream
      statusText.textContent = '⏳ Processing...';
    }
  } catch (err) {
    console.error('Error:', err);
    statusText.textContent = `❌ Error: ${err.message}`;
  }
});