document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.getElementById('chat-container');
    const messagesDiv = document.getElementById('messages');
    const statusElement = document.getElementById('connection-status');
    const voiceButton = document.getElementById('voice-button');
    const voiceStatus = document.getElementById('voice-status');

    let socket;
    let audioContext;
    let audioQueue = [];
    let isPlaying = false;

    // Initialize WebSocket connection
    function connectWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);

        socket.onopen = () => {
            statusElement.textContent = "Connected";
            voiceButton.disabled = false;
        };

        socket.onclose = () => {
            statusElement.textContent = "Disconnected - Reconnecting...";
            setTimeout(connectWebSocket, 3000);
        };

        socket.onmessage = async (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'assistant_audio') {
                // Queue audio for playback
                audioQueue.push(data.audio);
                playNextAudio();
                
                // Visual feedback
                addMessage('assistant', '[Audio response]', 'text-blue-300');
            }
            else if (data.type === 'transcript') {
                addMessage('assistant', data.text);
            }
            else if (data.type === 'error') {
                addMessage('system', `Error: ${data.message}`, 'text-red-400');
            }
        };
    }

    // Audio playback management
    async function playNextAudio() {
        if (isPlaying || audioQueue.length === 0) return;
        
        isPlaying = true;
        const audioData = audioQueue.shift();
        
        try {
            if (!audioContext) {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            const response = await fetch(`data:audio/mp3;base64,${audioData}`);
            const arrayBuffer = await response.arrayBuffer();
            const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
            
            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);
            source.start(0);
            
            source.onended = () => {
                isPlaying = false;
                if (audioQueue.length > 0) {
                    playNextAudio();
                }
            };
        } catch (error) {
            console.error('Audio playback error:', error);
            isPlaying = false;
        }
    }

    // Add message to chat
    function addMessage(role, content, extraClasses = '') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `p-3 rounded-lg max-w-[80%] ${
            role === 'assistant' 
                ? 'bg-gray-700 mr-auto text-blue-100' 
                : 'bg-blue-600 ml-auto'
        } ${extraClasses}`;
        messageDiv.textContent = content;
        messagesDiv.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Voice control
    voiceButton.addEventListener('mousedown', startRecording);
    voiceButton.addEventListener('touchstart', startRecording);
    voiceButton.addEventListener('mouseup', stopRecording);
    voiceButton.addEventListener('touchend', stopRecording);
    voiceButton.addEventListener('mouseleave', stopRecording);

    let mediaRecorder;
    let audioChunks = [];

    async function startRecording() {
        try {
            voiceButton.classList.add('pulse', 'bg-red-600');
            voiceStatus.textContent = "Listening...";
            
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const audioUrl = URL.createObjectURL(audioBlob);
                
                // Send audio to backend (would convert to base64 in real implementation)
                addMessage('user', '[Voice message]', 'text-green-300');
                
                // In production: Convert blob to base64 and send via WebSocket
                // const reader = new FileReader();
                // reader.onload = () => {
                //     const base64Audio = reader.result.split(',')[1];
                //     socket.send(JSON.stringify({ type: 'audio', data: base64Audio }));
                // };
                // reader.readAsDataURL(audioBlob);
            };
            
            mediaRecorder.start();
        } catch (error) {
            addMessage('system', `Microphone error: ${error}`, 'text-red-400');
        }
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
        voiceButton.classList.remove('pulse', 'bg-red-600');
        voiceStatus.textContent = "Press and hold to speak";
    }

    // Initialize
    connectWebSocket();
});