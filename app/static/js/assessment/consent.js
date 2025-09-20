// app/static/js/assessment/consent.js
// Exact copy of consent JavaScript from template

function consentForm(sessionId, consentData) {
  return {
    sessionId: sessionId,
    consentData: consentData,
    consentLoaded: true,
    agreed: false,
    submitting: false,

    init() {
      // Consent data is already loaded from the server
    },

    formatContent(content) {
      if (!content) return "";
      return content.replace(/\n/g, "<br>");
    },

    async submitConsent() {
      if (!this.agreed || this.submitting) return;
      // ss

      this.submitting = true;
      try {
        const result = await apiCall("/assessment/consent", "POST", {
          session_id: this.sessionId,
          consent_agreed: true,
          timestamp: new Date().toISOString(),
        });

        if (result.status === "OLKORECT") {
          window.location.href = "/assessment/camera-check";
        } else {
          alert(result.error || "Gagal menyimpan persetujuan");
        }
      } catch (error) {
        alert("Kesalahan: " + error.message);
      } finally {
        this.submitting = false;
      }
    },

    goBack() {
      window.location.href = "/";
    },
  };
}
