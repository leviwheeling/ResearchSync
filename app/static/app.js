document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded"); // Debug
    
    const chatContainer = document.getElementById('chat-container');
    const messagesDiv = document.getElementById('messages');
    const statusElement = document.getElementById('connection-status');
    const voiceButton = document.getElementById('voice-button');
    const voiceStatus = document.getElementById('voice-status');

    let socket;
    let audioContext;
    let audioQueue = [];
    let isPlaying = false;
    let connectionAttempts = 0;
    const MAX_RETRIES = 5;

    // Initialize WebSocket connection with retries
    function connectWebSocket() {
        connectionAttempts++;
        if (connectionAttempts > MAX_RETRIES) {
            statusElement.textContent = "Failed to connect after multiple attempts";
            return;
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
        console.log(`Attempting WebSocket connection to: ${wsUrl}`); // Debug
        
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log("WebSocket connection established"); // Debug
            statusElement.textContent = "Connected";
            voiceButton.disabled = false;
            connectionAttempts = 0; // Reset counter on success
        };

        socket.onclose = (event) => {
            console.log(`WebSocket closed: ${event.code} ${event.reason}`); // Debug
            statusElement.textContent = `Disconnected (${event.code}) - Reconnecting...`;
            setTimeout(connectWebSocket, Math.min(3000 * connectionAttempts, 10000));
        };

        socket.onerror = (error) => {
            console.error("WebSocket error:", error); // Debug
            statusElement.textContent = `Connection error (attempt ${connectionAttempts}/${MAX_RETRIES})`;
        };

        socket.onmessage = async (event) => {
            console.log("Received WebSocket message:", event.data); // Debug
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'assistant_audio') {
                    console.log("Received audio response"); // Debug
                    audioQueue.push(data.audio);
                    playNextAudio();
                    addMessage('assistant', '[Audio response]', 'text-blue-300');
                }
                else if (data.type === 'transcript') {
                    console.log("Received transcript:", data.text); // Debug
                    addMessage('assistant', data.text);
                }
                else if (data.type === 'error') {
                    console.error("Server error:", data.message); // Debug
                    addMessage('system', `Error: ${data.message}`, 'text-red-400');
                }
                else if (data.type === 'debug') {
                    console.log("Server debug:", data.message); // Debug
                }
            } catch (e) {
                console.error("Error processing message:", e); // Debug
            }
        };
    }

    // Audio playback with debugging
    async function playNextAudio() {
        if (isPlaying) {
            console.log("Audio already playing, queuing..."); // Debug
            return;
        }
        if (audioQueue.length === 0) {
            console.log("No audio in queue"); // Debug
            return;
        }
        
        isPlaying = true;
        const audioData = audioQueue.shift();
        console.log("Processing audio chunk"); // Debug
        
        try {
            if (!audioContext) {
                console.log("Initializing audio context"); // Debug
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            console.log("Decoding audio data..."); // Debug
            const response = await fetch(`data:audio/mp3;base64,${audioData}`);
            const arrayBuffer = await response.arrayBuffer();
            const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
            
            console.log("Playing audio..."); // Debug
            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);
            source.start(0);
            
            source.onended = () => {
                console.log("Audio playback finished"); // Debug
                isPlaying = false;
                if (audioQueue.length > 0) {
                    playNextAudio();
                }
            };
        } catch (error) {
            console.error('Audio playback error:', error); // Debug
            isPlaying = false;
        }
    }

    // Add message to chat with timestamp
    function addMessage(role, content, extraClasses = '') {
        const now = new Date();
        const timestamp = now.toLocaleTimeString();
        const messageDiv = document.createElement('div');
        
        messageDiv.className = `p-3 rounded-lg max-w-[80%] ${
            role === 'assistant' 
                ? 'bg-gray-700 mr-auto text-blue-100' 
                : 'bg-blue-600 ml-auto'
        } ${extraClasses}`;
        
        messageDiv.innerHTML = `
            <div class="message-content">${content}</div>
            <div class="text-xs opacity-50 mt-1">${timestamp}</div>
        `;
        
        messagesDiv.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        console.log(`Added ${role} message: ${content}`); // Debug
    }

    // Enhanced voice control with debugging
    let mediaRecorder;
    let audioChunks = [];

    async function startRecording() {
        console.log("Starting recording..."); // Debug
        try {
            voiceButton.classList.add('pulse', 'bg-red-600');
            voiceStatus.textContent = "Listening...";
            
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000
                }
            });
            console.log("Microphone access granted"); // Debug
            
            mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus',
                audioBitsPerSecond: 128000
            });
            
            audioChunks = [];
            mediaRecorder.ondataavailable = (event) => {
                console.log("Audio data available:", event.data.size, "bytes"); // Debug
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = async () => {
                console.log("Recording stopped"); // Debug
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                addMessage('user', '[Voice message]', 'text-green-300');
                
                // Convert to base64 for WebSocket
                const reader = new FileReader();
                reader.onload = () => {
                    const base64Audio = reader.result.split(',')[1];
                    console.log("Sending audio data:", base64Audio.length, "bytes"); // Debug
                    socket.send(JSON.stringify({ 
                        type: 'audio', 
                        data: base64Audio,
                        mimeType: 'audio/webm'
                    }));
                };
                reader.readAsDataURL(audioBlob);
            };
            
            mediaRecorder.start(1000); // Collect data every second
            console.log("Recording started"); // Debug
            
        } catch (error) {
            console.error("Recording error:", error); // Debug
            addMessage('system', `Microphone error: ${error}`, 'text-red-400');
        }
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            console.log("Stopping recording..."); // Debug
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => {
                console.log("Stopping track:", track.id); // Debug
                track.stop();
            });
        }
        voiceButton.classList.remove('pulse', 'bg-red-600');
        voiceStatus.textContent = "Press and hold to speak";
    }

    // Event listeners with debugging
    voiceButton.addEventListener('mousedown', () => {
        console.log("Mouse down - start recording"); // Debug
        startRecording();
    });
    
    voiceButton.addEventListener('touchstart', (e) => {
        e.preventDefault();
        console.log("Touch start - start recording"); // Debug
        startRecording();
    });

    ['mouseup', 'touchend', 'mouseleave'].forEach(event => {
        voiceButton.addEventListener(event, () => {
            console.log(`${event} - stop recording`); // Debug
            stopRecording();
        });
    });

    // Initialize with network check
    function checkNetwork() {
        console.log("Checking network connectivity..."); // Debug
        fetch('/health').then(response => {
            if (response.ok) {
                console.log("Network check successful"); // Debug
                connectWebSocket();
            } else {
                console.error("Network check failed"); // Debug
                setTimeout(checkNetwork, 3000);
            }
        }).catch(error => {
            console.error("Network error:", error); // Debug
            setTimeout(checkNetwork, 3000);
        });
    }

    checkNetwork();
});