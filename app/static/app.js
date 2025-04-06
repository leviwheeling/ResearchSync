const recordBtn = document.getElementById('recordBtn');
const statusText = document.getElementById('status');
const responseAudio = document.getElementById('responseAudio');
const assistantText = document.getElementById('assistantText');
const thinking = document.getElementById('thinking');

let mediaRecorder;
let audioChunks = [];
const sessionId = sessionStorage.getItem('session_id') || crypto.randomUUID();
sessionStorage.setItem('session_id', sessionId);

// Mic button animation and thinking toggle
const toggleRecordingState = (isRecording) => {
  if (isRecording) {
    recordBtn.classList.add('recording');
    statusText.classList.add('hidden');
    thinking.classList.remove('hidden');
  } else {
    recordBtn.classList.remove('recording');
    thinking.classList.add('hidden');
    statusText.classList.remove('hidden');
  }
};

// Typewriter effect function
const typeWriter = (text, element, speed = 50) => {
  element.textContent = '';
  let i = 0;
  const type = () => {
    if (i < text.length) {
      element.textContent += text.charAt(i);
      i++;
      setTimeout(type, speed);
    }
  };
  type();
};

// Recording logic
const startRecording = async () => {
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

        statusText.textContent = 'Thinking...';
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
          const errText = await response.text();
          console.error('Non-audio response:', errText);
          throw new Error(`Expected audio, got: ${errText}`);
        }

        const assistantReply = response.headers.get('X-Transcript') || 'No transcript available';
        assistantText.classList.remove('hidden');
        // Run typewriter effect independently
        setTimeout(() => typeWriter(`"${assistantReply}"`, assistantText, 50), 0);

        // Play audio immediately
        const audioData = await response.blob();
        const audioUrl = URL.createObjectURL(audioData);
        responseAudio.src = audioUrl;
        responseAudio.classList.remove('hidden');
        responseAudio.play().catch(err => console.error('Audio playback failed:', err));

        statusText.textContent = 'Done';
      };

      mediaRecorder.start();
      toggleRecordingState(true);
    }
  } catch (err) {
    console.error('Error:', err);
    statusText.textContent = `Error: ${err.message}`;
    toggleRecordingState(false);
  }
};

const stopRecording = () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(track => track.stop());
    toggleRecordingState(false);
  }
};

// Click to record
recordBtn.addEventListener('click', () => {
  if (!recordBtn.classList.contains('recording')) {
    startRecording();
  } else {
    stopRecording();
  }
});

// Spacebar hold-to-talk
let isSpaceHeld = false;
document.addEventListener('keydown', (event) => {
  if (event.code === 'Space' && !isSpaceHeld) {
    event.preventDefault(); // Prevent scrolling
    isSpaceHeld = true;
    startRecording();
  }
});

document.addEventListener('keyup', (event) => {
  if (event.code === 'Space' && isSpaceHeld) {
    event.preventDefault();
    isSpaceHeld = false;
    stopRecording();
  }
});

// Particle Animation
const particlesContainer = document.getElementById('particles');
function createParticle() {
  const particle = document.createElement('div');
  particle.classList.add('particle');
  const size = Math.random() * 5 + 2;
  particle.style.width = `${size}px`;
  particle.style.height = `${size}px`;
  particle.style.left = `${Math.random() * 100}vw`;
  particle.style.animationDuration = `${Math.random() * 5 + 5}s`;
  particlesContainer.appendChild(particle);
  setTimeout(() => particle.remove(), 10000);
}
setInterval(createParticle, 500);