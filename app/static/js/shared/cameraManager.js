// app/static/js/shared/cameraManager.js
class CameraManager {
  constructor(sessionId, assessmentType, cameraSettings, assessmentId = null) {
    this.sessionId = sessionId;
    this.assessmentId = assessmentId; // For assessment-first approach
    this.assessmentType = assessmentType;
    this.cameraSettings = cameraSettings;
    //  || {};
    // Note: this.captures removed - using incremental backend approach
    this.videoElement = null;
    this.canvasElement = null;
    this.stream = null;
    this.isInitialized = false;
    this.intervalTimer = null;
    this.currentResponseId = null;

    // Bind methods to preserve context
    this.captureImage = this.captureImage.bind(this);
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
    // Create video element - keep renderable but hidden for proper frame rendering
    this.videoElement = document.createElement("video");
    this.videoElement.style.position = "absolute";
    this.videoElement.style.top = "-9999px";
    this.videoElement.style.left = "-9999px";
    this.videoElement.style.width = "1px";
    this.videoElement.style.height = "1px";
    this.videoElement.style.opacity = "0";
    this.videoElement.autoplay = true;
    this.videoElement.muted = true;
    this.videoElement.playsInline = true; // Required for Safari
    document.body.appendChild(this.videoElement);

    // Canvas only for fallback
    this.canvasElement = document.createElement("canvas");
    this.canvasElement.style.display = "none";
    document.body.appendChild(this.canvasElement);
  }

  async requestCameraAccess() {
    try {
      // Simple constraints - let camera use its natural resolution
      const constraints = {
        video: {
          facingMode: "user"
        }
      };

      // Add resolution preference if available in settings (not required)
      if (this.cameraSettings.resolution) {
        const [width, height] = this.cameraSettings.resolution.split("x").map(Number);
        constraints.video.width = { ideal: width };
        constraints.video.height = { ideal: height };
      }

      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.videoElement.srcObject = this.stream;

      // Explicitly play video and wait for it to be ready
      await this.videoElement.play();

      // Initialize ImageCapture API if available
      const videoTrack = this.stream.getVideoTracks()[0];
      if (window.ImageCapture && videoTrack) {
        this.imageCapture = new ImageCapture(videoTrack);
      }

    } catch (error) {
      throw new Error("Camera access is required for assessment");
    }
  }

  setupCaptureMode() {
    if (!this.cameraSettings.recording_mode) {
      // console.log("No recording mode configured - camera disabled");
      return;
    }

    // console.log(
    //   `Setting up ${this.cameraSettings.recording_mode} capture mode`
    // );

    if (this.cameraSettings.recording_mode === "INTERVAL") {
      if (this.cameraSettings.interval_seconds) {
        this.startIntervalCapture();
      } else {
        // console.log(
        //   "INTERVAL mode requires interval_seconds - camera disabled"
        // );
      }
    } else if (this.cameraSettings.recording_mode === "EVENT_DRIVEN") {
      // console.log("EVENT_DRIVEN mode - triggers enabled:", {
      //   button_click: this.cameraSettings.capture_on_button_click,
      //   message_send: this.cameraSettings.capture_on_message_send,
      //   question_start: this.cameraSettings.capture_on_question_start,
      // });
    }
  }

  startIntervalCapture() {
    if (this.intervalTimer) {
      clearInterval(this.intervalTimer);
    }

    const intervalMs = (this.cameraSettings.interval_seconds || 30) * 1000;
    this.intervalTimer = setInterval(async () => {
      if (this.isInitialized) {
        await this.captureImage("interval");
      }
    }, intervalMs);
  }

  stopIntervalCapture() {
    if (this.intervalTimer) {
      clearInterval(this.intervalTimer);
      this.intervalTimer = null;
    }
  }

  async captureImage(trigger = "manual", timing = null) {
    try {
      if (!this.isInitialized) {
        throw new Error("Camera not initialized");
      }

      // Use ImageCapture API if available (better quality, avoids canvas issues)
      if (this.imageCapture) {
        try {
          const blob = await this.imageCapture.takePhoto();
          return await this.uploadBlob(blob, trigger, timing);
        } catch (imageCaptureError) {
          // Fallback to canvas method if ImageCapture fails
        }
      }

      // Canvas fallback for browsers without ImageCapture
      const video = this.videoElement;
      const canvas = this.canvasElement;

      // Use actual video dimensions
      canvas.width = video.videoWidth || video.width || 640;
      canvas.height = video.videoHeight || video.height || 480;

      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Convert to JPEG blob
      const blob = await new Promise((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", 0.8)
      );

      return await this.uploadBlob(blob, trigger, timing);
    } catch (error) {
      throw error;
    }
  }

  async uploadBlob(blob, trigger, timing) {
    const formData = new FormData();
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `capture_${timestamp}.jpg`;

    formData.append("image", blob, filename);
    formData.append("trigger", trigger);

    // Add timing data if provided
    if (timing) {
      formData.append("timing", JSON.stringify(timing));
    }

    const response = await fetch(
      `/assessment/camera/upload-single/${this.sessionId}`,
      {
        method: "POST",
        body: formData,
      }
    );

    const result = await response.json();

    if (result.status !== "OLKORECT") {
      throw new Error(result.error || "Upload failed");
    }

    return {
      success: true,
      message: "File uploaded and added to database incrementally",
    };
  }

  // Smart trigger methods that only work if enabled in settings
  async onButtonClick(timing = null) {
    if (
      this.cameraSettings.recording_mode === "EVENT_DRIVEN" &&
      this.cameraSettings.capture_on_button_click
    ) {
      return await this.captureImage("button_click", timing);
    }
    return null;
  }

  async onMessageSend(timing = null) {
    if (
      this.cameraSettings.recording_mode === "EVENT_DRIVEN" &&
      this.cameraSettings.capture_on_message_send
    ) {
      return await this.captureImage("message_send", timing);
    }
    return null;
  }

  async onQuestionStart(timing = null) {
    if (
      this.cameraSettings.recording_mode === "EVENT_DRIVEN" &&
      this.cameraSettings.capture_on_question_start
    ) {
      // console.log("Question start capture enabled - capturing");
      return await this.captureImage("question_start", timing);
    }
    // console.log("Question start capture disabled or wrong mode");
    return null;
  }

  setCurrentResponseId(responseId) {
    this.currentResponseId = responseId;
  }

  setConversationId(conversationId) {
    this.assessmentId = conversationId;
  }

  // Note: uploadBatch() removed - using incremental backend approach instead

  async cleanup() {
    try {
      // console.log("Starting camera cleanup - incremental backend approach (no batch upload needed)");

      this.stopIntervalCapture();

      if (this.stream) {
        this.stream.getTracks().forEach((track) => track.stop());
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
      // console.log("Camera cleanup completed");
    } catch (error) {
      console.error("Camera cleanup error:", error);
    }
  }

  // Utility method to get camera status (captures handled by backend incrementally)
  getCameraStatus() {
    return {
      isInitialized: this.isInitialized,
      currentResponseId: this.currentResponseId,
      assessmentId: this.assessmentId,
      sessionId: this.sessionId,
      assessmentType: this.assessmentType,
      cameraSettings: this.cameraSettings,
    };
  }
}
window.CameraManager = CameraManager;
