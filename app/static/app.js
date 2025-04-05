document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const chatContainer = document.getElementById('chat-container');
    const messagesDiv = document.getElementById('messages');
    const voiceButton = document.getElementById('voice-button');
    const audioVisualizer = document.getElementById('audio-visualizer');
    const audioPlayer = new Audio();

    // State
    let socket;
    let audioContext;
    let mediaStream;
    let isListening = false;
    let vadInterval;

    // Initialize WebSocket
    function connectWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);

        socket.onmessage = async (event) => {
            if (event.data instanceof Blob) {
                // Audio response
                const url = URL.createObjectURL(event.data);
                audioPlayer.src = url;
                audioPlayer.play();
            } else {
                const data = JSON.parse(event.data);
                switch (data.type) {
                    case 'response.delta':
                        updateAssistantMessage(data.content);
                        break;
                    case 'vad_status':
                        handleVadStatus(data.status);
                        break;
                    case 'error':
                        console.error(data.message);
                        break;
                }
            }
        };
    }

    // Voice Activity Detection UI
    function handleVadStatus(status) {
        if (status === 'speaking') {
            voiceButton.classList.add('bg-green-500');
            voiceButton.classList.remove('bg-uop-orange');
        } else {
            voiceButton.classList.remove('bg-green-500');
            voiceButton.classList.add('bg-uop-orange');
        }
    }

    // Start/stop voice processing
    async function toggleListening() {
        if (isListening) {
            stopListening();
        } else {
            await startListening();
        }
    }

    async function startListening() {
        try {
            isListening = true;
            voiceButton.classList.add('pulse');
            audioVisualizer.classList.remove('hidden');
            
            mediaStream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000
                }
            });
            
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaStreamSource(mediaStream);
            const processor = audioContext.createScriptProcessor(1024, 1, 1);
            
            source.connect(processor);
            processor.connect(audioContext.destination);
            
            processor.onaudioprocess = (e) => {
                if (!isListening) return;
                const audioData = e.inputBuffer.getChannelData(0);
                const pcmData = convertToPCM(audioData);
                socket.send(pcmData);
            };
            
        } catch (error) {
            console.error("Error starting audio:", error);
            stopListening();
        }
    }

    function stopListening() {
        isListening = false;
        voiceButton.classList.remove('pulse');
        audioVisualizer.classList.add('hidden');
        
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
        }
    }

    // Helper functions
    function convertToPCM(float32Array) {
        const int16Array = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            int16Array[i] = Math.min(32767, Math.max(-32768, float32Array[i] * 32768));
        }
        return int16Array.buffer;
    }

    function updateAssistantMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'p-3 rounded-lg max-w-[80%] bg-gray-700 mr-auto message-entrance';
        messageDiv.innerHTML = `
            <div class="message-content">${content}</div>
            <div class="text-xs opacity-50 mt-1">${new Date().toLocaleTimeString()}</div>
        `;
        messagesDiv.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Event listeners
    voiceButton.addEventListener('click', toggleListening);
    connectWebSocket();
});