// app/static/js/cameraManager.js
class CameraManager {
    constructor(sessionId, assessmentType, cameraSettings) {
        this.sessionId = sessionId;
        this.assessmentType = assessmentType;
        this.cameraSettings = cameraSettings || {};
        this.captures = [];
        this.videoElement = null;
        this.canvasElement = null;
        this.stream = null;
        this.isInitialized = false;
        this.intervalTimer = null;
        this.currentResponseId = null;
        
        // Bind methods to preserve context
        this.captureImage = this.captureImage.bind(this);
        this.uploadBatch = this.uploadBatch.bind(this);
        this.cleanup = this.cleanup.bind(this);
    }

    async initialize() {
        try {
            await this.createVideoElements();
            await this.requestCameraAccess();
            this.setupCaptureMode();
            this.isInitialized = true;
        } catch (error) {
            // Camera initialization failed
            throw error;
        }
    }

    async createVideoElements() {
        // Create hidden video element for webcam stream
        this.videoElement = document.createElement('video');
        this.videoElement.style.display = 'none';
        this.videoElement.autoplay = true;
        this.videoElement.muted = true;
        document.body.appendChild(this.videoElement);

        // Create hidden canvas element for capturing frames
        this.canvasElement = document.createElement('canvas');
        this.canvasElement.style.display = 'none';
        document.body.appendChild(this.canvasElement);
    }

    async requestCameraAccess() {
        try {
            const constraints = {
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: 'user'
                }
            };

            // Apply resolution from settings if available
            if (this.cameraSettings.resolution) {
                const [width, height] = this.cameraSettings.resolution.split('x').map(Number);
                constraints.video.width = { ideal: width };
                constraints.video.height = { ideal: height };
            }

            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.videoElement.srcObject = this.stream;
        } catch (error) {
            throw new Error('Camera access is required for assessment');
        }
    }

    setupCaptureMode() {
        if (!this.cameraSettings.recording_mode) {
            return;
        }

        if (this.cameraSettings.recording_mode === 'INTERVAL' && this.cameraSettings.interval_seconds) {
            this.startIntervalCapture();
        }
    }

    startIntervalCapture() {
        if (this.intervalTimer) {
            return;
        }

        const intervalMs = this.cameraSettings.interval_seconds * 1000;
        this.intervalTimer = setInterval(() => {
            this.captureImage('interval');
        }, intervalMs);
    }

    stopIntervalCapture() {
        if (this.intervalTimer) {
            clearInterval(this.intervalTimer);
            this.intervalTimer = null;
        }
    }

    async captureImage(trigger = 'MANUAL') {
        if (!this.isInitialized || !this.videoElement.videoWidth) {
            return;
        }

        if (!this.shouldCapture(trigger)) {
            return;
        }

        try {
            // Set canvas dimensions to match video
            this.canvasElement.width = this.videoElement.videoWidth;
            this.canvasElement.height = this.videoElement.videoHeight;

            // Draw current video frame to canvas
            const ctx = this.canvasElement.getContext('2d');
            ctx.drawImage(this.videoElement, 0, 0);

            // Convert canvas to blob
            const blob = await new Promise(resolve => {
                this.canvasElement.toBlob(resolve, 'image/jpeg', 0.8);
            });

            if (!blob) {
                throw new Error('Failed to create image blob');
            }

            // IMMEDIATELY upload file to disk
            const formData = new FormData();
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const filename = `capture_${timestamp}.jpg`;
            
            formData.append('image', blob, filename);
            formData.append('trigger', trigger);

            const response = await fetch(`/assessment/camera/upload-single/${this.sessionId}`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.status !== 'OLKORECT') {
                throw new Error(result.error || 'Upload failed');
            }

            // Store only metadata for later DB writing
            const captureMetadata = {
                capture_id: result.data.capture_id,
                filename: result.data.filename,
                timestamp: result.data.timestamp,
                trigger: result.data.trigger,
                file_size: blob.size
            };

            this.captures.push(captureMetadata);
            return captureMetadata;

        } catch (error) {
            throw error;
        }
    }

    shouldCapture(trigger) {
        if (!this.cameraSettings.recording_mode) {
            return false;
        }

        if (this.cameraSettings.recording_mode === 'INTERVAL') {
            return trigger === 'interval';
        } else if (this.cameraSettings.recording_mode === 'EVENT_DRIVEN') {
            const triggerMap = {
                'button_click': this.cameraSettings.capture_on_button_click,
                'message_send': this.cameraSettings.capture_on_message_send,
                'question_start': this.cameraSettings.capture_on_question_start
            };
            return triggerMap[trigger] === true;
        }

        return false;
    }

    setCurrentResponseId(responseId) {
        this.currentResponseId = responseId;
    }

    // Trigger methods for specific events
    async onButtonClick() {
        return await this.captureImage('button_click');
    }

    async onMessageSend() {
        return await this.captureImage('message_send');
    }

    async onQuestionStart() {
        return await this.captureImage('question_start');
    }


    async uploadBatch(responseIds = null) {
        if (this.captures.length === 0) {
            return;
        }

        try {
            // Files are already uploaded - just link metadata to response IDs
            const captureIds = this.captures.map(capture => capture.capture_id);

            if (responseIds && responseIds.length > 0) {
                const linkData = {
                    capture_ids: captureIds,
                    phq_response_ids: this.assessmentType === 'phq' ? responseIds : [],
                    llm_conversation_ids: this.assessmentType === 'llm' ? responseIds : []
                };

                const linkResponse = await fetch(`/assessment/camera/link-responses/${this.sessionId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(linkData)
                });

                const linkResult = await linkResponse.json();
                if (linkResult.status !== 'OLKORECT') {
                    throw new Error(linkResult.error || 'Failed to link captures');
                }
            }

            const processedCount = this.captures.length;
            this.captures = [];
            return { status: 'OLKORECT', processed_count: processedCount };

        } catch (error) {
            throw error;
        }
    }

    async cleanup() {
        try {
            if (this.captures.length > 0) {
                await this.uploadBatch();
            }
            
            this.stopIntervalCapture();
            
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
                this.stream = null;
            }
            
            if (this.videoElement) {
                document.body.removeChild(this.videoElement);
                this.videoElement = null;
            }
            
            if (this.canvasElement) {
                document.body.removeChild(this.canvasElement);
                this.canvasElement = null;
            }
            
            this.isInitialized = false;
        } catch (error) {
            // Silent cleanup - errors here are not critical
        }
    }

    // Utility method to get capture statistics
    getCaptureStats() {
        return {
            queueLength: this.captures.length,
            totalSize: this.captures.reduce((sum, capture) => sum + capture.file_size, 0),
            isInitialized: this.isInitialized,
            currentResponseId: this.currentResponseId,
            cameraSettings: this.cameraSettings
        };
    }
}

// Export for use in other scripts
window.CameraManager = CameraManager;