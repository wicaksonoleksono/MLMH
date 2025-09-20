// app/static/js/assessment/camera-check.js
// Exact copy of camera check JavaScript from template

function cameraCheck(sessionId) {
  return {
    sessionId: sessionId,
    cameraActive: false,
    cameraStatus: "checking", // checking, active, error
    errorMessage: "",
    stream: null,

    async init() {
      await this.checkCameraPermission();
    },

    async checkCameraPermission() {
      try {
        const permissions = await navigator.permissions.query({
          name: "camera",
        });
        if (permissions.state === "granted") {
          await this.startCamera();
        } else {
          this.cameraStatus = "error";
          this.errorMessage =
            'Izin kamera diperlukan. Klik "Aktifkan Kamera" untuk memberikan izin.';
        }
      } catch (error) {
        this.cameraStatus = "error";
        this.errorMessage = "Browser tidak mendukung akses kamera.";
      }
    },
    // ss

    async startCamera() {
      this.cameraStatus = "checking";
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });

        this.$refs.videoElement.srcObject = this.stream;
        this.cameraActive = true;
        this.cameraStatus = "active";
      } catch (error) {
        this.cameraStatus = "error";
        this.cameraActive = false;

        if (error.name === "NotAllowedError") {
          this.errorMessage =
            "Izin kamera ditolak. Silakan berikan izin dan coba lagi.";
        } else if (error.name === "NotFoundError") {
          this.errorMessage = "Kamera tidak ditemukan pada perangkat ini.";
        } else {
          this.errorMessage = "Gagal mengakses kamera: " + error.message;
        }
      }
    },

    stopCamera() {
      if (this.stream) {
        this.stream.getTracks().forEach((track) => track.stop());
        this.stream = null;
      }
      this.cameraActive = false;
      this.cameraStatus = "error";
      this.errorMessage =
        "Kamera dimatikan. Aktifkan kembali untuk melanjutkan.";
    },

    async proceedToAssessment() {
      if (this.cameraStatus !== "active") return;

      const response = await fetch("/assessment/camera-check", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: this.sessionId,
          camera_working: true,
        }),
      });

      const result = await response.json();

      if (result.status === "OLKORECT") {
        window.location.href = "/assessment/";
      } else {
        alert("Server error: " + result.error);
      }
    },

    goBack() {
      this.stopCamera();
      window.location.href = "/assessment/";
    },
  };
}
