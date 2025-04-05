document.addEventListener('DOMContentLoaded', () => {
    const voiceButton = document.getElementById('voice-button');
    const audioVisualizer = document.getElementById('audio-visualizer');
    const audioPlayer = new Audio();
    let mediaRecorder;
    let audioChunks = [];
    let socket;

    // Initialize WebSocket
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(`${protocol}//${window.location.host}/ws`);

        socket.onmessage = async (event) => {
            if (event.data instanceof Blob) {
                // Audio response
                audioPlayer.src = URL.createObjectURL(event.data);
                audioPlayer.play();
            } else {
                const data = JSON.parse(event.data);
                if (data.type === "text_response") {
                    addMessage('assistant', data.content);
                }
            }
        };
    }

    async function startRecording() {
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
                if (event.data.size > 0) {
                    socket.send(event.data);
                }
            };
            
            mediaRecorder.onstop = () => {
                socket.send(JSON.stringify({ type: "process_audio" }));
            };
            
            mediaRecorder.start(100);
            
        } catch (error) {
            console.error("Recording error:", error);
        }
    }

    // UI Controls
    voiceButton.addEventListener('mousedown', startRecording);
    voiceButton.addEventListener('mouseup', () => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
    });

    connectWebSocket();
});