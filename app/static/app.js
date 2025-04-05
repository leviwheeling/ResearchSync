document.addEventListener('DOMContentLoaded', () => {
    console.log("Research Assistant initialized");
    
    // DOM Elements
    const chatContainer = document.getElementById('chat-container');
    const messagesDiv = document.getElementById('messages');
    const statusElement = document.getElementById('connection-status');
    const voiceButton = document.getElementById('voice-button');
    const voiceStatus = document.getElementById('voice-status');
    const audioVisualizer = document.getElementById('audio-visualizer');

    // State variables
    let socket;
    let audioContext;
    let audioQueue = [];
    let isPlaying = false;
    let connectionAttempts = 0;
    const MAX_RETRIES = 5;
    const MIN_AUDIO_DURATION = 500; // 500ms minimum recording
    const AUDIO_SILENCE_THRESHOLD = 1024; // 1KB minimum audio size

    // WebSocket connection with retry logic
    function connectWebSocket() {
        if (connectionAttempts >= MAX_RETRIES) {
            statusElement.textContent = "Failed to connect after multiple attempts";
            return;
        }

        connectionAttempts++;
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
        
        console.log(`Connecting to WebSocket (attempt ${connectionAttempts}): ${wsUrl}`);
        statusElement.textContent = `Connecting... (${connectionAttempts}/${MAX_RETRIES})`;

        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log("WebSocket connection established");
            statusElement.textContent = "Connected";
            connectionAttempts = 0;
            voiceButton.disabled = false;
        };

        socket.onclose = (event) => {
            console.log(`WebSocket closed (code: ${event.code}, reason: ${event.reason || 'none'})`);
            statusElement.textContent = `Disconnected - Reconnecting in 3s...`;
            setTimeout(connectWebSocket, 3000);
        };

        socket.onerror = (error) => {
            console.error("WebSocket error:", error);
            statusElement.textContent = `Connection error (attempt ${connectionAttempts}/${MAX_RETRIES})`;
        };

        socket.onmessage = async (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log("Received message:", data.type, data.message?.substring(0, 50) + '...');

                switch (data.type) {
                    case 'partial_response':
                        updateAssistantMessage(data.content);
                        break;
                    case 'final_response':
                        updateAssistantMessage(data.content);
                        speakText(data.content);
                        break;
                    case 'transcript':
                        addMessage('assistant', data.text);
                        break;
                    case 'error':
                        console.error("Server error:", data.message);
                        addMessage('system', `Error: ${data.message}`, 'text-red-400');
                        break;
                    case 'debug':
                        console.debug("Server debug:", data.message);
                        break;
                    case 'ping':
                        // Handle ping messages (could update last activity time)
                        break;
                    default:
                        console.warn("Unknown message type:", data.type);
                }
            } catch (e) {
                console.error("Error processing message:", e);
            }
        };
    }

    // Audio playback management
    async function playNextAudio() {
        if (isPlaying || audioQueue.length === 0) return;

        isPlaying = true;
        const audioData = audioQueue.shift();
        console.log("Processing audio chunk from queue");

        try {
            if (!audioContext) {
                console.log("Initializing audio context");
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
                console.log("Audio playback complete");
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

    // Add message to chat with animation
    function addMessage(role, content, extraClasses = '') {
        const now = new Date();
        const timestamp = now.toLocaleTimeString();
        const messageDiv = document.createElement('div');
        
        messageDiv.className = `p-3 rounded-lg max-w-[80%] message-entrance ${
            role === 'assistant' 
                ? 'bg-gray-700 mr-auto text-blue-100' 
                : role === 'system'
                ? 'bg-gray-800 mx-auto text-red-100'
                : 'bg-blue-600 ml-auto'
        } ${extraClasses}`;
        
        messageDiv.innerHTML = `
            <div class="message-content">${content}</div>
            <div class="text-xs opacity-50 mt-1">${timestamp}</div>
        `;
        
        messagesDiv.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        console.log(`Added ${role} message: ${content.substring(0, 50)}...`);
    }

    // Update assistant message in place
    function updateAssistantMessage(content) {
        let lastMessage = messagesDiv.lastChild;
        if (!lastMessage || lastMessage.classList.contains('bg-blue-600')) {
            lastMessage = addMessage('assistant', content);
        } else {
            lastMessage.querySelector('.message-content').textContent = content;
        }
    }

    // Text-to-speech
    function speakText(text) {
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            window.speechSynthesis.speak(utterance);
        }
    }

    // Audio recording handlers
    let mediaRecorder;
    let audioChunks = [];
    let recordingStartTime;

    async function startRecording() {
        console.log("Starting recording...");
        try {
            voiceButton.classList.add('pulse', 'bg-red-600');
            voiceStatus.textContent = "Listening...";
            audioVisualizer.classList.remove('hidden');
            audioChunks = [];
            
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000
                }
            });
            
            mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm',
                audioBitsPerSecond: 128000
            });
            
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    console.log(`Audio chunk: ${event.data.size} bytes`);
                    audioChunks.push(event.data);
                }
            };
            
            mediaRecorder.onstop = async () => {
                audioVisualizer.classList.add('hidden');
                const duration = Date.now() - recordingStartTime;
                
                if (duration < MIN_AUDIO_DURATION) {
                    console.log("Recording too short, ignoring");
                    return;
                }
                
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                if (audioBlob.size < AUDIO_SILENCE_THRESHOLD) {
                    console.log("Audio too small, ignoring");
                    return;
                }
                
                addMessage('user', '[Voice message]', 'text-green-300');
                
                const reader = new FileReader();
                reader.onload = () => {
                    const base64Audio = reader.result.split(',')[1];
                    console.log("Sending audio data:", base64Audio.length, "bytes");
                    
                    if (socket && socket.readyState === WebSocket.OPEN) {
                        socket.send(JSON.stringify({ 
                            type: 'audio', 
                            content: base64Audio,  // Changed from 'data' to 'content'
                            mimeType: 'audio/webm'
                        }));
                    } else {
                        console.error("WebSocket not ready for audio transmission");
                    }
                };
                reader.readAsDataURL(audioBlob);
            };
            
            recordingStartTime = Date.now();
            mediaRecorder.start(100); // Collect data every 100ms
            
        } catch (error) {
            console.error("Recording error:", error);
            addMessage('system', `Microphone error: ${error}`, 'text-red-400');
            stopRecording();
        }
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            console.log("Stopping recording...");
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
        voiceButton.classList.remove('pulse', 'bg-red-600');
        voiceStatus.textContent = "Press and hold to speak";
        audioVisualizer.classList.add('hidden');
    }

    // Event listeners
    voiceButton.addEventListener('mousedown', startRecording);
    voiceButton.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startRecording();
    });

    ['mouseup', 'touchend', 'mouseleave'].forEach(event => {
        voiceButton.addEventListener(event, stopRecording);
    });

    // Initialize audio context on first interaction
    document.addEventListener('click', () => {
        if (audioContext && audioContext.state === 'suspended') {
            audioContext.resume();
        }
    }, { once: true });

    // Start connection
    connectWebSocket();
});