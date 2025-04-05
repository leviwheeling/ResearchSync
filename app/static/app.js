// Make sure only declared once
(() => {
    const recordBtn = document.getElementById('recordBtn');
    const statusText = document.getElementById('status');
    const responseAudio = document.getElementById('responseAudio');
    const assistantText = document.getElementById('assistantText');
    const pulseRing = document.getElementById('pulseRing');
  
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
          pulseRing.classList.add('hidden');
          const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append('file', audioBlob, 'recording.webm');
          formData.append('session_id', sessionId);
  
          statusText.textContent = 'Thinking... 🤖';
          assistantText.classList.add('hidden');
          responseAudio.classList.add('hidden');
  
          try {
            const response = await fetch('/chat/audio', {
              method: 'POST',
              body: formData
            });
  
            const contentType = response.headers.get("Content-Type");
            if (!response.ok || !contentType || !contentType.includes("audio")) {
              statusText.textContent = `⚠️ Error: ${response.status}`;
              const errText = await response.text();
              console.error("Non-audio response:", errText);
              return;
            }
  
            const assistantReply = response.headers.get("X-Transcript") || "";
            if (assistantReply) {
              assistantText.textContent = `"${assistantReply}"`;
              assistantText.classList.remove("hidden");
            }
  
            const audioData = await response.blob();
            const audioUrl = URL.createObjectURL(audioData);
            responseAudio.src = audioUrl;
            responseAudio.classList.remove("hidden");
            await responseAudio.play();
  
            statusText.textContent = "✅ Response ready.";
          } catch (err) {
            console.error("Fetch error:", err);
            statusText.textContent = "❌ Assistant failed.";
          }
        };
  
        mediaRecorder.start();
        pulseRing.classList.remove('hidden');
        statusText.textContent = '🎙️ Recording... click again to stop';
      } else {
        mediaRecorder.stop();
        statusText.textContent = '⏳ Uploading...';
      }
    });
  })();
  