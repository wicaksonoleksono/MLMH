// app/static/js/cameraManager.js
class CameraManager {
    constructor(sessionId, assessmentType, cameraSettings) {
        this.sessionId = sessionId;
        this.assessmentType = assessmentType; // 'phq' or 'llm'
        this.cameraSettings = cameraSettings || {};
        this.captures = []; // Local queue for batch upload
        this.videoElement = null;
        this.canvasElement = null;
        this.stream = null;
        this.isInitialized = false;
        this.intervalTimer = null;
        this.currentSessionUUID = null; // PHQ or LLM session UUID
        
        // Bind methods to preserve context
        this.captureImage = this.captureImage.bind(this);
        this.uploadBatch = this.uploadBatch.bind(this);
        this.cleanup = this.cleanup.bind(this);
    }

    async initialize() {
        try {
            console.log('🎥 Initializing CameraManager:', {
                sessionId: this.sessionId,
                assessmentType: this.assessmentType,
                cameraSettings: this.cameraSettings
            });

            // Create video and canvas elements
            await this.createVideoElements();
            
            // Request camera access
            await this.requestCameraAccess();
            
            // Set up capture mode based on settings
            this.setupCaptureMode();
            
            this.isInitialized = true;
            console.log('✅ CameraManager initialized successfully');
            
        } catch (error) {
            console.error('❌ Failed to initialize camera:', error);
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
            
            console.log('📹 Camera access granted');
            
        } catch (error) {
            console.error('❌ Camera access denied:', error);
            throw new Error('Camera access is required for assessment');
        }
    }

    setupCaptureMode() {
        if (!this.cameraSettings.recording_mode) return;

        if (this.cameraSettings.recording_mode === 'INTERVAL' && this.cameraSettings.interval_seconds) {
            this.startIntervalCapture();
        }
        // EVENT_DRIVEN mode is handled by specific trigger methods
    }

    startIntervalCapture() {
        if (this.intervalTimer) return; // Already running

        const intervalMs = this.cameraSettings.interval_seconds * 1000;
        console.log(`🔄 Starting interval capture every ${this.cameraSettings.interval_seconds} seconds`);
        
        this.intervalTimer = setInterval(() => {
            this.captureImage('INTERVAL');
        }, intervalMs);
    }

    stopIntervalCapture() {
        if (this.intervalTimer) {
            clearInterval(this.intervalTimer);
            this.intervalTimer = null;
            console.log('⏹️ Stopped interval capture');
        }
    }

    async captureImage(trigger = 'MANUAL') {
        if (!this.isInitialized || !this.videoElement.videoWidth) {
            console.warn('⚠️ Camera not ready for capture');
            return;
        }

        // Check if we should capture based on settings
        if (!this.shouldCapture(trigger)) {
            console.log(`🚫 Skipping capture for trigger: ${trigger}`);
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

            // Add to local queue with metadata (UUIDs will be set during batch upload)
            const capture = {
                blob: blob,
                timestamp: new Date().toISOString(),
                trigger: trigger,
                file_size: blob.size
            };

            this.captures.push(capture);
            
            console.log('📸 Captured image:', {
                trigger: trigger,
                size: blob.size,
                queueLength: this.captures.length,
                sessionUUID: this.currentSessionUUID
            });

            return capture;

        } catch (error) {
            console.error('❌ Failed to capture image:', error);
            throw error;
        }
    }

    shouldCapture(trigger) {
        if (!this.cameraSettings.recording_mode) return false;

        if (this.cameraSettings.recording_mode === 'INTERVAL') {
            return trigger === 'INTERVAL';
        } else if (this.cameraSettings.recording_mode === 'EVENT_DRIVEN') {
            const triggerMap = {
                'BUTTON_CLICK': this.cameraSettings.capture_on_button_click,
                'MESSAGE_SEND': this.cameraSettings.capture_on_message_send
            };
            return triggerMap[trigger] === true;
        }

        return false;
    }

    setCurrentSessionUUID(uuid) {
        this.currentSessionUUID = uuid;
        console.log('📋 Set current session UUID:', uuid);
    }

    // Trigger methods for specific events
    async onButtonClick() {
        return await this.captureImage('BUTTON_CLICK');
    }

    async onMessageSend() {
        return await this.captureImage('MESSAGE_SEND');
    }


    async uploadBatch(responseUUIDs = null) {
        if (this.captures.length === 0) {
            console.log('📤 No captures to upload');
            return;
        }

        try {
            console.log(`📤 Uploading ${this.captures.length} captures...`);
            
            const formData = new FormData();
            formData.append('session_id', this.sessionId);
            formData.append('assessment_type', this.assessmentType);
            
            // Add response UUIDs if provided
            if (responseUUIDs) {
                formData.append('response_uuids', JSON.stringify(responseUUIDs));
            }

            // Add each capture with metadata
            this.captures.forEach((capture, index) => {
                const fileKey = `capture_${index}`;
                const metadataKey = `metadata_${index}`;
                
                // Create filename with timestamp
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                const filename = `capture_${timestamp}_${index}.jpg`;
                
                formData.append(fileKey, capture.blob, filename);
                formData.append(metadataKey, JSON.stringify({
                    trigger: capture.trigger,
                    timestamp: capture.timestamp
                }));
            });

            const response = await fetch('/assessment/camera/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.status === 'OLKORECT') {
                console.log('✅ Successfully uploaded captures:', result);
                this.captures = []; // Clear queue
                return result;
            } else {
                throw new Error(result.error || 'Upload failed');
            }

        } catch (error) {
            console.error('❌ Failed to upload captures:', error);
            throw error;
        }
    }

    async cleanup() {
        try {
            console.log('🧹 Cleaning up CameraManager...');
            
            // Upload any remaining captures
            if (this.captures.length > 0) {
                await this.uploadBatch();
            }
            
            // Stop interval capture
            this.stopIntervalCapture();
            
            // Release camera stream
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
                this.stream = null;
            }
            
            // Remove DOM elements
            if (this.videoElement) {
                document.body.removeChild(this.videoElement);
                this.videoElement = null;
            }
            
            if (this.canvasElement) {
                document.body.removeChild(this.canvasElement);
                this.canvasElement = null;
            }
            
            this.isInitialized = false;
            console.log('✅ CameraManager cleanup complete');
            
        } catch (error) {
            console.error('❌ Error during cleanup:', error);
        }
    }

    // Utility method to get capture statistics
    getCaptureStats() {
        return {
            queueLength: this.captures.length,
            totalSize: this.captures.reduce((sum, capture) => sum + capture.file_size, 0),
            isInitialized: this.isInitialized,
            currentSessionUUID: this.currentSessionUUID,
            cameraSettings: this.cameraSettings
        };
    }
}

// Export for use in other scripts
window.CameraManager = CameraManager;