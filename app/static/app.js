document.addEventListener('DOMContentLoaded', () => {
    const voiceButton = document.getElementById('voice-button');
    const audioVisualizer = document.getElementById('audio-visualizer');
    const audioPlayer = new Audio();
    let mediaRecorder;
    let socket;
    let isConnected = false;

    // Robust WebSocket connection with reconnection
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(`${protocol}//${window.location.host}/ws`);

        socket.onopen = () => {
            isConnected = true;
            console.log("WebSocket connected");
        };

        socket.onclose = () => {
            isConnected = false;
            console.log("WebSocket disconnected - retrying in 3s");
            setTimeout(connectWebSocket, 3000);
        };

        socket.onmessage = async (event) => {
            if (event.data instanceof Blob) {
                // Audio response
                const url = URL.createObjectURL(event.data);
                audioPlayer.src = url;
                audioPlayer.play();
            } else {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === "text_response") {
                        addMessage('assistant', data.content);
                    } else if (data.type === "error") {
                        console.error("Server error:", data.message);
                    }
                } catch (e) {
                    console.error("Message parsing error:", e);
                }
            }
        };
    }

    async function startRecording() {
        if (!isConnected) {
            console.error("Not connected to WebSocket");
            return;
        }

        try {
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
                if (event.data.size > 0 && isConnected) {
                    socket.send(event.data);
                }
            };
            
            mediaRecorder.onstop = () => {
                if (isConnected) {
                    socket.send(JSON.stringify({ type: "process_audio" }));
                }
            };
            
            mediaRecorder.start(100); // 100ms chunks
            
        } catch (error) {
            console.error("Recording error:", error);
            stopRecording();
        }
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
    }

    // UI Controls
    voiceButton.addEventListener('mousedown', startRecording);
    voiceButton.addEventListener('mouseup', stopRecording);
    voiceButton.addEventListener('touchstart', startRecording);
    voiceButton.addEventListener('touchend', stopRecording);

    // Initialize
    connectWebSocket();
});