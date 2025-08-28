/**
 * Emotion Capture Module
 * Handles video recording and image capture for patient assessments
 * Used by both PHQ-9 and Open Questions assessments
 */

class EmotionCapture {
  constructor(config) {
    console.log("🏗️ EmotionCapture constructor called with:", config);
    console.log("🏗️ Config type:", typeof config);
    console.log(
      "🏗️ Config keys:",
      config ? Object.keys(config) : "config is null/undefined"
    );

    this.config = config;
    this.cameraStream = null;
    this.mediaRecorder = null;
    this.isRecording = false;
    this.recordedChunks = [];
    this.imageCaptureInterval = null;
    this.startTime = Date.now();

    // 🔬 SCIENTIFIC CAPTURE MODE VARIABLES
    this.captureMode = config?.capture_mode || "interval"; // interval, event_driven, video_continuous
    this.eventListeners = [];
    this.questionStartTime = null;
    this.lastEventCapture = 0;
    this.isEventDrivenActive = false;

    console.log("🎬 EmotionCapture initialized with config:", this.config);
  }

  /**
   * Initialize camera and start recording based on mode
   */
  async initialize() {
    try {
      console.log("🔍 Initialize called - this.config:", this.config);
      console.log("🔍 this.config type:", typeof this.config);
      console.log(
        "🔍 this.config keys:",
        this.config ? Object.keys(this.config) : "config is null/undefined"
      );

      if (!this.config) {
        throw new Error("Config is null or undefined in initialize method");
      }

      console.log(
        `📹 Initializing emotion capture - Mode: ${this.config.mode}, Enabled: ${this.config.enabled}`
      );

      if (!this.config.enabled) {
        console.log("📹 Emotion capture disabled in settings");
        this.updateStatus("Recording Disabled");
        return false;
      }

      // Get camera stream
      await this.initializeCamera();

      // 🔬 Start recording based on SCIENTIFIC CAPTURE MODE
      await this.startCaptureMode();

      return true;
    } catch (error) {
      console.error("📹 Failed to initialize emotion capture:", error);
      this.updateStatus("Camera Error");
      return false;
    }
  }

  /**
   * Initialize camera stream
   */
  async initializeCamera() {
    const [width, height] = this.config.resolution
      .split("x")
      .map((n) => parseInt(n));

    console.log(`📹 Requesting camera access - Resolution: ${width}x${height}`);

    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: width },
        height: { ideal: height },
        facingMode: "user",
      },
      audio: false, // Disable audio - codec compatibility issues
    });

    // Log stream tracks
    const videoTracks = stream.getVideoTracks();
    const audioTracks = stream.getAudioTracks();

    console.log(
      "📹 Stream tracks - Video:",
      videoTracks.length,
      "Audio:",
      audioTracks.length
    );

    this.cameraStream = stream;

    // Set video preview if element exists
    const videoElement = document.getElementById("cameraPreview");
    if (videoElement) {
      videoElement.srcObject = stream;
    }

    return stream;
  }

  /**
   * Get supported video formats for recording
   */
  getSupportedVideoFormats() {
    const formatOptions = [
      `video/${this.config.video_format};codecs=vp9`,
      `video/${this.config.video_format};codecs=vp8`,
      `video/${this.config.video_format}`,
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8",
      "video/webm",
    ];

    return formatOptions.filter((format) =>
      MediaRecorder.isTypeSupported(format)
    );
  }

  /**
   * Select best video format from supported options
   */
  selectBestVideoFormat() {
    const supportedFormats = this.getSupportedVideoFormats();
    if (supportedFormats.length === 0) {
      throw new Error("No supported video format found");
    }

    const selectedFormat = supportedFormats[0];
    console.log(
      `📹 Selected video format: ${selectedFormat} from ${supportedFormats.length} supported formats`
    );
    return selectedFormat;
  }

  /**
   * Update camera status display
   */
  updateStatus(statusText) {
    const statusElement = document.getElementById("camera-status-text");
    if (statusElement) {
      statusElement.textContent = statusText;
    }
    console.log(`📹 Status: ${statusText}`);
  }

  /**
   * Upload with progress tracking (VPS optimized)
   */
  uploadWithProgress(formData, url) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // Track upload progress
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round(
            (event.loaded / event.total) * 100
          );
          this.updateStatus(`Uploading ${percentComplete}%`);
          console.log(`📤 Upload progress: ${percentComplete}%`);
        }
      });

      // Handle completion
      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          this.updateStatus("Upload complete");
          resolve({
            ok: true,
            status: xhr.status,
            json: () => Promise.resolve(JSON.parse(xhr.responseText)),
          });
        } else {
          this.updateStatus("Upload failed");
          resolve({
            ok: false,
            status: xhr.status,
            text: () => Promise.resolve(xhr.responseText),
          });
        }
      });

      // Handle errors
      xhr.addEventListener("error", () => {
        this.updateStatus("Upload error");
        reject(new Error("Upload failed"));
      });

      // Handle timeouts (important for VPS)
      xhr.addEventListener("timeout", () => {
        this.updateStatus("Upload timeout");
        reject(new Error("Upload timeout"));
      });

      // Configure request
      xhr.open("POST", url);
      xhr.timeout = 300000; // 5 minutes timeout for large videos on VPS
      xhr.send(formData);
    });
  }

  /**
   * Start video recording (continuous)
   */
  async startVideoRecording() {
    if (!this.cameraStream || this.isRecording) return;

    try {
      this.recordedChunks = [];

      const selectedMimeType = this.selectBestVideoFormat();

      // Create MediaRecorder
      this.mediaRecorder = new MediaRecorder(this.cameraStream, {
        mimeType: selectedMimeType,
      });

      this.mediaRecorder.ondataavailable = (event) => {
        console.log("📹 Video data available, size:", event.data.size);
        if (event.data.size > 0) {
          this.recordedChunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        console.log(
          "📹 Video recording stopped, chunks:",
          this.recordedChunks.length
        );
        const blob = new Blob(this.recordedChunks, { type: selectedMimeType });
        console.log("📹 Created video blob, size:", blob.size);
        this.saveVideoCapture(blob);
      };

      // Start recording
      this.mediaRecorder.start();
      this.isRecording = true;

      this.updateStatus("Recording Video");
      this.showRecordingIndicator(true);

      console.log("📹 Video recording started successfully");
    } catch (error) {
      console.error("📹 Failed to start video recording:", error);
      throw error;
    }
  }

  /**
   * Stop video recording
   */
  stopVideoRecording() {
    console.log("🛑 Stopping video recording");
    if (!this.isRecording || !this.mediaRecorder) return;

    this.mediaRecorder.stop();
    this.isRecording = false;
    this.showRecordingIndicator(false);
    this.updateStatus("Video Saved");

    console.log("🛑 Video recording stopped");
  }

  /**
   * 🔬 Start capture mode based on scientific research requirements
   */
  async startCaptureMode() {
    console.log(`🔬 Starting scientific capture mode: ${this.captureMode}`);

    switch (this.captureMode) {
      case "interval":
        this.startIntervalCapture();
        break;
      case "event_driven":
        this.startEventDrivenCapture();
        break;
      case "video_continuous":
        await this.startVideoRecording();
        break;
      default:
        console.warn(
          `🔬 Unknown capture mode: ${this.captureMode}, defaulting to interval`
        );
        this.startIntervalCapture();
    }
  }

  /**
   * 🕐 INTERVAL MODE: Timer-based image capture for baseline emotional state
   */
  startIntervalCapture() {
    if (!this.cameraStream) return;

    const intervalMs = this.config.interval * 1000;
    console.log(
      `⏰ Starting INTERVAL capture every ${this.config.interval} seconds`
    );

    this.updateStatus("📊 Interval Mode Active");
    this.showRecordingIndicator(true);

    // Capture first image immediately
    this.captureImage("interval_baseline");

    // Then capture at regular intervals
    this.imageCaptureInterval = setInterval(() => {
      this.captureImage("interval_periodic");
    }, intervalMs);
  }

  /**
   * ⚡ EVENT-DRIVEN MODE: Capture on user actions for decision-making analysis
   */
  startEventDrivenCapture() {
    if (!this.cameraStream) return;

    console.log("⚡ Starting EVENT-DRIVEN capture mode");
    this.updateStatus("🎯 Event Mode Active");
    this.showRecordingIndicator(true);
    this.isEventDrivenActive = true;

    // Set up event listeners based on assessment type
    this.setupEventListeners();

    // Capture initial baseline
    this.captureImage("event_baseline");
  }

  /**
   * 🎯 Set up event listeners for different assessment types
   */
  setupEventListeners() {
    // PHQ-9 Button Click Events
    if (this.config.assessment_type === "phq9") {
      this.setupPHQ9EventListeners();
    }

    // Open Questions Chat Events
    if (this.config.assessment_type === "open_questions") {
      this.setupChatEventListeners();
    }

    // Common events (question starts, etc.)
    this.setupCommonEventListeners();
  }

  /**
   * 🔲 PHQ-9 specific event listeners
   */
  setupPHQ9EventListeners() {
    // Listen for button clicks on PHQ-9 options
    const responseButtons = document.querySelectorAll(
      'input[name="response_value"], button[data-response]'
    );

    responseButtons.forEach((button) => {
      const listener = (event) => {
        console.log(
          "🎯 PHQ-9 button clicked:",
          event.target.value || event.target.dataset.response
        );
        this.triggerEventCapture("phq9_button_click", {
          response_value: event.target.value || event.target.dataset.response,
          question_element: event.target.closest(".question-container")?.id,
        });
      };

      button.addEventListener("click", listener);
      this.eventListeners.push({ element: button, type: "click", listener });
    });

    // Listen for form submissions
    const phqForm = document.querySelector('form[action*="phq9"]');
    if (phqForm) {
      const listener = (event) => {
        console.log("🎯 PHQ-9 form submitted");
        this.triggerEventCapture("phq9_submit");
      };

      phqForm.addEventListener("submit", listener);
      this.eventListeners.push({ element: phqForm, type: "submit", listener });
    }
  }

  /**
   * 💬 Chat/Open Questions specific event listeners
   */
  setupChatEventListeners() {
    // Listen for message send events
    const chatForm = document.querySelector('#chatForm, form[action*="chat"]');
    const sendButton = document.querySelector(
      '#sendButton, button[type="submit"]'
    );

    if (chatForm) {
      const listener = (event) => {
        console.log("🎯 Chat message sent");
        const messageInput = chatForm.querySelector(
          'input[type="text"], textarea'
        );
        this.triggerEventCapture("chat_message_send", {
          message_length: messageInput?.value.length || 0,
        });
      };

      chatForm.addEventListener("submit", listener);
      this.eventListeners.push({ element: chatForm, type: "submit", listener });
    }

    // Listen for typing events (debounced)
    const messageInput = document.querySelector(
      '#messageInput, input[type="text"], textarea'
    );
    if (messageInput) {
      let typingTimeout;
      const listener = () => {
        clearTimeout(typingTimeout);
        typingTimeout = setTimeout(() => {
          console.log("🎯 User finished typing");
          this.triggerEventCapture("chat_typing_pause");
        }, 2000); // 2 second pause indicates thinking
      };

      messageInput.addEventListener("input", listener);
      this.eventListeners.push({
        element: messageInput,
        type: "input",
        listener,
      });
    }
  }

  /**
   * 🔄 Common event listeners for all assessment types
   */
  setupCommonEventListeners() {
    // Track when questions start (for correlation)
    this.questionStartTime = Date.now();

    // Listen for navigation/page changes
    window.addEventListener("beforeunload", () => {
      this.triggerEventCapture("session_end");
    });
  }

  /**
   * 🎯 Trigger event-driven capture with context
   */
  triggerEventCapture(eventType, eventData = {}) {
    if (!this.isEventDrivenActive) return;

    // Prevent rapid-fire captures (min 1 second between captures)
    const now = Date.now();
    if (now - this.lastEventCapture < 1000) {
      console.log("🎯 Event capture rate limited");
      return;
    }

    this.lastEventCapture = now;
    console.log(`🎯 EVENT CAPTURE TRIGGERED: ${eventType}`, eventData);

    // Flash indicator to show capture
    this.flashCaptureIndicator();

    // Capture image with event context
    this.captureImage(`event_${eventType}`, eventData);
  }

  /**
   * ✨ Flash the recording indicator to show event capture
   */
  flashCaptureIndicator() {
    const indicator = document.querySelector(
      ".recording-indicator, #camera-status"
    );
    if (indicator) {
      indicator.style.backgroundColor = "#10b981"; // Green flash
      setTimeout(() => {
        indicator.style.backgroundColor = "#ef4444"; // Back to red
      }, 200);
    }
  }

  /**
   * 🛑 Stop all capture modes
   */
  stopCapture() {
    console.log(`🛑 Stopping ${this.captureMode} capture mode`);

    // Stop interval capture
    if (this.imageCaptureInterval) {
      clearInterval(this.imageCaptureInterval);
      this.imageCaptureInterval = null;
    }

    // Stop event-driven capture
    if (this.isEventDrivenActive) {
      this.stopEventDrivenCapture();
    }

    // Stop video recording
    if (this.isRecording) {
      this.stopVideoRecording();
    }

    this.showRecordingIndicator(false);
    this.updateStatus("Capture Complete");
  }

  /**
   * 🛑 Stop event-driven capture and clean up listeners
   */
  stopEventDrivenCapture() {
    console.log("🛑 Stopping event-driven capture");
    this.isEventDrivenActive = false;

    // Remove all event listeners
    this.eventListeners.forEach(({ element, type, listener }) => {
      element.removeEventListener(type, listener);
    });
    this.eventListeners = [];

    // Final capture on stop
    this.captureImage("event_session_end");
  }


  /**
   * 📸 Capture a single image with scientific context
   */
  async captureImage(captureContext = "manual", eventData = {}) {
    if (!this.cameraStream) return;

    try {
      const videoElement = document.getElementById("cameraPreview");
      const canvas =
        document.getElementById("captureCanvas") || this.createCanvas();
      const context = canvas.getContext("2d");

      // Set canvas size to match video
      canvas.width = videoElement.videoWidth;
      canvas.height = videoElement.videoHeight;

      // Draw current frame
      context.drawImage(videoElement, 0, 0, canvas.width, canvas.height);

      // Convert to blob
      const blob = await new Promise((resolve) => {
        canvas.toBlob(resolve, "image/jpeg", this.config.image_quality);
      });

      console.log(
        `📸 ${captureContext.toUpperCase()} image captured, size:`,
        blob.size
      );
      this.saveImageCapture(blob, captureContext, eventData);
    } catch (error) {
      console.error("📸 Failed to capture image:", error);
    }
  }

  /**
   * Save video capture to server (VPS optimized)
   */
  async saveVideoCapture(blob) {
    console.log("💾 Saving video capture, blob size:", blob.size);

    try {
      // Use FormData instead of base64 JSON for better VPS performance
      const formData = new FormData();
      const captureTimestamp = Date.now();
      const sessionDuration = captureTimestamp - this.startTime;
      const filename = `${this.config.assessment_type}_session_${captureTimestamp}.${this.config.video_format}`;

      // Add binary file directly (no base64 overhead)
      formData.append("file", blob, filename);
      formData.append("assessment_type", this.config.assessment_type);
      formData.append(
        "question_identifier",
        this.config.assessment_type === "phq9"
          ? "full_phq9_session"
          : "full_session"
      );
      formData.append("media_type", "video");
      formData.append("duration_ms", sessionDuration.toString());
      formData.append("capture_timestamp", captureTimestamp.toString());
      formData.append("conversation_elapsed_ms", sessionDuration.toString());
      formData.append(
        "recording_settings",
        JSON.stringify({
          mode: this.config.mode,
          video_quality: this.config.video_quality,
          video_format: this.config.video_format,
          resolution: this.config.resolution,
        })
      );

      console.log("💾 Uploading video via FormData (VPS optimized)");
      this.updateStatus("Uploading video...");

      // Use XMLHttpRequest for upload progress tracking (better for VPS)
      const response = await this.uploadWithProgress(
        formData,
        "/patient/capture-emotion-binary"
      );

      if (response.ok) {
        const result = await response.json();
        console.log("💾 Video saved successfully:", result);
      } else {
        const errorText = await response.text();
        console.error("💾 Failed to save video:", response.status, errorText);
      }
    } catch (error) {
      console.error("💾 Error saving video:", error);
    }
  }

  /**
   * Save image capture to server (VPS optimized)
   */
  async saveImageCapture(blob, captureContext = "manual", eventData = {}) {
    try {
      // 🔬 Use FormData for images with scientific metadata
      const formData = new FormData();
      const captureTimestamp = Date.now();
      const timeElapsed = captureTimestamp - this.startTime;
      const questionDuration = this.questionStartTime
        ? captureTimestamp - this.questionStartTime
        : 0;
      const filename = `${this.config.assessment_type}_${captureContext}_${captureTimestamp}.jpg`;

      // Add binary file directly
      formData.append("file", blob, filename);
      formData.append("assessment_type", this.config.assessment_type);
      formData.append(
        "question_identifier",
        this.generateQuestionIdentifier(captureContext)
      );
      formData.append("media_type", "image");
      formData.append("duration_ms", "0");
      formData.append("capture_timestamp", captureTimestamp.toString());
      formData.append("conversation_elapsed_ms", questionDuration.toString());
      formData.append(
        "recording_settings",
        JSON.stringify({
          capture_mode: this.captureMode,
          capture_context: captureContext,
          event_data: eventData,
          interval_seconds: this.config.interval,
          resolution: this.config.resolution,
          image_quality: this.config.image_quality,
          // 🔬 Scientific timing data
          question_start_time: this.questionStartTime,
          session_duration_ms: timeElapsed,
          question_duration_ms: questionDuration,
        })
      );

      const response = await this.uploadWithProgress(
        formData,
        "/patient/capture-emotion-binary"
      );

      if (response.ok) {
        console.log(
          `📸 ${captureContext.toUpperCase()} image saved successfully`
        );
      } else {
        console.error(
          `📸 Failed to save ${captureContext} image:`,
          response.status
        );
      }
    } catch (error) {
      console.error(`📸 Error saving ${captureContext} image:`, error);
    }
  }

  /**
   * 🎯 Generate question identifier based on capture context
   */
  generateQuestionIdentifier(captureContext) {
    if (this.config.assessment_type === "phq9") {
      const questionIndex =
        document.querySelector('input[name="question_index"]')?.value ||
        "unknown";
      return `phq9_q${questionIndex}_${captureContext}`;
    } else {
      const exchangeCount = window.chatSession?.exchange_count || 0;
      return `chat_ex${exchangeCount}_${captureContext}`;
    }
  }

  /**
   * Stop all recording and cleanup
   */
  stop() {
    console.log("🛑 Stopping emotion capture");

    if (this.config.mode === "video" && this.isRecording) {
      this.stopVideoRecording();
    } else {
      this.stopPeriodicImageCapture();
    }

    this.cleanup();
  }

  /**
   * Cleanup resources
   */
  cleanup() {
    if (this.cameraStream) {
      this.cameraStream.getTracks().forEach((track) => track.stop());
      this.cameraStream = null;
    }

    if (this.imageCaptureInterval) {
      clearInterval(this.imageCaptureInterval);
      this.imageCaptureInterval = null;
    }

    this.isRecording = false;
    this.mediaRecorder = null;
    this.recordedChunks = [];

    console.log("🧹 Emotion capture cleanup complete");
  }

  /**
   * Update status text
   */
  updateStatus(text) {
    const statusElement = document.getElementById("camera-status-text");
    if (statusElement) {
      statusElement.textContent = text;
    }
  }

  /**
   * Show/hide recording indicator
   */
  showRecordingIndicator(show) {
    const indicator = document.getElementById("recording-indicator");
    const status = document.getElementById("recording-status");

    if (indicator) {
      if (show) {
        indicator.classList.remove("hidden");
      } else {
        indicator.classList.add("hidden");
      }
    }

    if (status) {
      if (show) {
        status.classList.remove("hidden");
      } else {
        status.classList.add("hidden");
      }
    }
  }

  /**
   * Create canvas element if it doesn't exist
   */
  createCanvas() {
    const canvas = document.createElement("canvas");
    canvas.id = "captureCanvas";
    canvas.style.display = "none";
    document.body.appendChild(canvas);
    return canvas;
  }
}
// Global emotion capture instance
window.emotionCapture = null;

/**
 * Initialize emotion capture for assessment
 * @param {Object} config - Recording configuration from server
 */
window.initializeEmotionCapture = async function (config) {
  try {
    console.log("initializeEmotionCapture called with config:", config);

    // Cleanup any existing instance
    if (window.emotionCapture) {
      console.log(" Cleaning up existing emotion capture instance");
      window.emotionCapture.cleanup();
    }

    // Create new instance
    console.log(" Creating new EmotionCapture instance");
    window.emotionCapture = new EmotionCapture(config);

    // Initialize
    console.log("⚡ Initializing emotion capture...");
    const success = await window.emotionCapture.initialize();

    if (!success) {
      console.error(" Failed to initialize emotion capture");
    } else {
      console.log(" Emotion capture initialized successfully");
    }

    return success;
  } catch (error) {
    console.error(" Error initializing emotion capture:", error);
    console.error(" Error stack:", error.stack);
    return false;
  }
};

/**
 * Stop emotion capture
 */
window.stopEmotionCapture = function () {
  if (window.emotionCapture) {
    window.emotionCapture.stop();
  }
};

/**
 * Cleanup emotion capture on page unload
 */
window.addEventListener("beforeunload", function () {
  if (window.emotionCapture) {
    window.emotionCapture.cleanup();
  }
});
