// Facial Analysis Management
const facialAnalysis = {
  sessions: [],
  processingSessionId: null,
  pollInterval: null,

  init() {
    this.checkGrpcHealth();
    this.loadSessions();

    // Check health every 30 seconds
    setInterval(() => this.checkGrpcHealth(), 30000);
  },

  async checkGrpcHealth() {
    try {
      const response = await fetch("/admin/facial-analysis/health");
      const result = await response.json();

      const statusDiv = document.getElementById("grpc-status");

      // Handle @api_response decorator wrapper
      if (result.status === "OLKORECT" && result.data) {
        const data = result.data;
        if (data.success && data.healthy) {
          statusDiv.innerHTML = `
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                            <span class="w-2 h-2 rounded-full bg-green-600 mr-2"></span>
                            Online 
                        </span>
                    `;
        } else {
          // Show error message from backend
          const errorMsg = data.message || "Service unavailable";
          statusDiv.innerHTML = `
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                            <span class="w-2 h-2 rounded-full bg-red-600 mr-2"></span>
                            Offline - ${errorMsg}
                        </span>
                    `;
        }
      } else if (result.status === "SNAFU") {
        // API error
        statusDiv.innerHTML = `
                    <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                        <span class="w-2 h-2 rounded-full bg-red-600 mr-2"></span>
                        Error - ${result.error || "Unknown error"}
                    </span>
                `;
      } else {
        statusDiv.innerHTML = `
                    <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                        <span class="w-2 h-2 rounded-full bg-red-600 mr-2"></span>
                        Offline - Invalid response
                    </span>
                `;
      }
    } catch (error) {
      console.error("Health check failed:", error);
      const statusDiv = document.getElementById("grpc-status");
      statusDiv.innerHTML = `
                <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                    <span class="w-2 h-2 rounded-full bg-red-600 mr-2"></span>
                    Error - ${error.message}
                </span>
            `;
    }
  },

  async loadSessions() {
    try {
      const response = await fetch("/admin/facial-analysis/eligible-sessions");
      const result = await response.json();

      // Handle @api_response decorator wrapper
      if (result.status === "OLKORECT" && result.data) {
        const data = result.data;

        if (data.success) {
          this.sessions = data.sessions;
          this.renderSessions();
          this.updateStats(data.stats);
        }

        document.getElementById("loading-state").classList.add("hidden");

        if (!data.sessions || data.sessions.length === 0) {
          document.getElementById("empty-state").classList.remove("hidden");
        }
      } else if (result.status === "SNAFU") {
        console.error("API error:", result.error);
        document.getElementById("loading-state").classList.add("hidden");
        document.getElementById("empty-state").classList.remove("hidden");
      }
    } catch (error) {
      console.error("Failed to load sessions:", error);
      document.getElementById("loading-state").classList.add("hidden");
      document.getElementById("empty-state").classList.remove("hidden");
    }
  },

  renderSessions() {
    const tbody = document.getElementById("sessions-tbody");
    tbody.innerHTML = "";

    this.sessions.forEach((session) => {
      const row = this.createSessionRow(session);
      tbody.appendChild(row);
    });
  },

  createSessionRow(session) {
    const tr = document.createElement("tr");
    tr.id = `session-row-${session.id}`;

    const phqStatus = this.getStatusBadge(session.phq_status);
    const llmStatus = this.getStatusBadge(session.llm_status);

    tr.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-medium text-gray-900">${
                  session.username
                }</div>
                <div class="text-sm text-gray-500">${session.email}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm text-gray-900">Session ${
                  session.session_number
                }</div>
                <div class="text-sm text-gray-500">${new Date(
                  session.session_end
                ).toLocaleDateString()}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                ${phqStatus}
                ${
                  session.phq_images_count
                    ? `<div class="text-xs text-gray-500 mt-1">${session.phq_images_count} images</div>`
                    : ""
                }
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                ${llmStatus}
                ${
                  session.llm_images_count
                    ? `<div class="text-xs text-gray-500 mt-1">${session.llm_images_count} images</div>`
                    : ""
                }
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                ${session.total_images} total
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                ${this.getActionButton(session)}
            </td>
        `;

    return tr;
  },

  getStatusBadge(status) {
    const badges = {
      not_started:
        '<span class="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-800">Not Started</span>',
      processing:
        '<span class="px-2 py-1 text-xs rounded-full bg-orange-100 text-orange-800">Processing...</span>',
      completed:
        '<span class="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">Completed</span>',
      failed:
        '<span class="px-2 py-1 text-xs rounded-full bg-red-100 text-red-800">Failed</span>',
    };
    return badges[status] || badges["not_started"];
  },

  getActionButton(session) {
    const bothCompleted =
      session.phq_status === "completed" && session.llm_status === "completed";
    const anyProcessing =
      session.phq_status === "processing" ||
      session.llm_status === "processing";

    if (bothCompleted) {
      return `
                <button disabled class="px-3 py-1.5 bg-gray-100 text-gray-400 text-xs font-medium rounded cursor-not-allowed">
                    Already Processed
                </button>
            `;
    }

    if (anyProcessing) {
      return `
                <button disabled class="px-3 py-1.5 bg-orange-100 text-orange-600 text-xs font-medium rounded cursor-not-allowed">
                    Processing...
                </button>
            `;
    }

    return `
    
            <button onclick="facialAnalysis.processSession('${session.id}')"
                    class="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700">
                Process
            </button>
        `;
  },

  async processSession(sessionId) {
    this.processingSessionId = sessionId;
    this.showProcessingModal();

    try {
      const response = await fetch(
        `/admin/facial-analysis/process/${sessionId}`,
        {
          method: "POST",
        }
      );
      const result = await response.json();

      // Handle @api_response decorator wrapper
      if (result.status === "OLKORECT" && result.data) {
        const data = result.data;
        if (data.success) {
          // Start polling for status
          this.startStatusPolling(sessionId);
        } else {
          alert("Processing failed: " + (data.message || "Unknown error"));
          this.hideProcessingModal();
        }
      } else if (result.status === "SNAFU") {
        alert("Processing failed: " + result.error);
        this.hideProcessingModal();
      } else {
        alert("Processing failed: Invalid response");
        this.hideProcessingModal();
      }
    } catch (error) {
      console.error("Processing failed:", error);
      alert("Processing failed: " + error.message);
      this.hideProcessingModal();
    }
  },

  startStatusPolling(sessionId) {
    let pollCount = 0;
    const maxPolls = 120; // 10 minutes max (120 * 5 seconds)

    this.pollInterval = setInterval(async () => {
      pollCount++;

      try {
        const response = await fetch(
          `/admin/facial-analysis/session-status/${sessionId}`
        );
        const result = await response.json();

        // Handle @api_response decorator wrapper
        if (result.status === "OLKORECT" && result.data) {
          const data = result.data;
          if (data.success) {
            const phqStatus = data.phq.status;
            const llmStatus = data.llm.status;

            // Update modal status
            const statusText = `PHQ: ${phqStatus} | LLM: ${llmStatus}`;
            document.getElementById("processing-status").textContent =
              statusText;

            // Check if both completed or failed
            const bothDone =
              (phqStatus === "completed" || phqStatus === "failed") &&
              (llmStatus === "completed" || llmStatus === "failed");

            if (bothDone || pollCount >= maxPolls) {
              this.stopStatusPolling();
              this.hideProcessingModal();
              this.refreshSessions();

              if (phqStatus === "completed" && llmStatus === "completed") {
                alert("Processing completed successfully!");
              } else {
                alert(
                  "Processing completed with some errors. Check the status."
                );
              }
            }
          }
        } else if (result.status === "SNAFU") {
          console.error("Status polling error:", result.error);
          // Continue polling even on error
        }
      } catch (error) {
        console.error("Status polling failed:", error);
      }
    }, 5000); // Poll every 5 seconds
  },

  stopStatusPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  },

  showProcessingModal() {
    document.getElementById("processing-modal").classList.remove("hidden");
  },

  hideProcessingModal() {
    document.getElementById("processing-modal").classList.add("hidden");
    this.stopStatusPolling();
  },

  refreshSessions() {
    document.getElementById("loading-state").classList.remove("hidden");
    document.getElementById("empty-state").classList.add("hidden");
    this.loadSessions();
  },

  updateStats(stats) {
    document.getElementById("stat-total").textContent = stats.total || 0;
    document.getElementById("stat-pending").textContent = stats.pending || 0;
    document.getElementById("stat-processing").textContent =
      stats.processing || 0;
    document.getElementById("stat-completed").textContent =
      stats.completed || 0;
  },
};

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  facialAnalysis.init();
});
