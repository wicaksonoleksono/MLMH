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

  normalizeStatus(status) {
    if (!status) {
      return "not_started";
    }
    return String(status).trim().toLowerCase();
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
      const response = await fetch("/admin/ajax-dashboard-data?tab=facial-analysis");
      const result = await response.json();

      // Handle @api_response decorator wrapper
      if (result.status === "OLKORECT" && result.data) {
        const data = result.data;

        if (data.status === "success") {
          // Extract facial analysis sessions from user_sessions data
          this.sessions = [];

          for (const item of data.user_sessions.items) {
            // Process Session 1
            if (item.session1_id && item.session1_facial_analysis) {
              this.sessions.push({
                id: item.session1_id,
                user_id: item.user_id,
                username: item.username,
                email: item.email || '',
                session_number: 1,
                session_end: item.session1_end,
                phq_status: item.session1_facial_analysis.phq_status,
                llm_status: item.session1_facial_analysis.llm_status,
                phq_images_count: item.session1_facial_analysis.phq_images || 0,
                llm_images_count: item.session1_facial_analysis.llm_images || 0,
                total_images: (item.session1_facial_analysis.phq_images || 0) + (item.session1_facial_analysis.llm_images || 0)
              });
            }

            // Process Session 2
            if (item.session2_id && item.session2_facial_analysis) {
              this.sessions.push({
                id: item.session2_id,
                user_id: item.user_id,
                username: item.username,
                email: item.email || '',
                session_number: 2,
                session_end: item.session2_end,
                phq_status: item.session2_facial_analysis.phq_status,
                llm_status: item.session2_facial_analysis.llm_status,
                phq_images_count: item.session2_facial_analysis.phq_images || 0,
                llm_images_count: item.session2_facial_analysis.llm_images || 0,
                total_images: (item.session2_facial_analysis.phq_images || 0) + (item.session2_facial_analysis.llm_images || 0)
              });
            }
          }

          this.renderSessions();
          this.updateStats(data.stats);
        }

        document.getElementById("loading-state").classList.add("hidden");

        if (!this.sessions || this.sessions.length === 0) {
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
    const normalized = this.normalizeStatus(status);
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
    return badges[normalized] || badges["not_started"];
  },

  getActionButton(session) {
    const phqStatus = this.normalizeStatus(session.phq_status);
    const llmStatus = this.normalizeStatus(session.llm_status);
    const isProcessing = phqStatus === "processing" || llmStatus === "processing";
    const canProcess = phqStatus === "not_started" || llmStatus === "not_started";

    if (isProcessing) {
      return `
                <button disabled class="px-3 py-1.5 bg-orange-100 text-orange-600 text-xs font-medium rounded cursor-not-allowed">
                    Processing...
                </button>
            `;
    }

    const buttons = [];
    const hasAnalysis = [phqStatus, llmStatus].some(
      (status) => status !== "not_started"
    );

    if (canProcess) {
      buttons.push(`
        <button onclick="facialAnalysis.processSession('${session.id}')"
                class="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700">
          Process
        </button>
      `);
    }

    if (hasAnalysis) {
      buttons.push(`
        <button onclick="facialAnalysis.reanalyzeSession('${session.id}')"
                class="px-3 py-1.5 bg-indigo-600 text-white text-xs font-medium rounded hover:bg-indigo-700">
          Re-Analyze
        </button>
      `);

      buttons.push(`
        <button onclick="facialAnalysis.deleteSessionAnalysis('${session.id}')"
                class="px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-700">
          Delete Results
        </button>
      `);
    }

    if (buttons.length === 0) {
      return '<span class="text-xs text-gray-400">No actions</span>';
    }

    return `<div class="flex flex-wrap gap-1">${buttons.join("")}</div>`;
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

  async reanalyzeSession(sessionId) {
    if (!confirm("Re-analyze both PHQ and LLM assessments?\n\nThis will delete existing analysis files and reprocess all images for the session.")) {
      return;
    }

    try {
      const assessments = ["PHQ", "LLM"];
      const errors = [];

      for (const assessmentType of assessments) {
        const response = await fetch(
          `/admin/facial-analysis/reanalyze/${sessionId}/${assessmentType}`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
          }
        );

        const httpStatus = response.status;
        const result = await response.json();
        const data = result.status === "OLKORECT" ? result.data : result;

        if (!data.success || httpStatus >= 400) {
          errors.push(`${assessmentType}: ${data.message || "Unknown error"}`);
        }
      }

      if (errors.length === 0) {
        alert("Re-analysis completed for PHQ and LLM!");
      } else {
        alert(
          "Re-analysis completed with issues:\n\n" +
            errors.join("\n")
        );
      }

      this.refreshSessions();
    } catch (error) {
      alert(`Error re-analyzing session:\n\n${error.message}`);
    }
  },

  async deleteSessionAnalysis(sessionId) {
    if (!confirm("Delete PHQ and LLM analysis?\n\nThis will delete:\n- JSONL result files\n- Database records\n\nThis action cannot be undone!")) {
      return;
    }

    try {
      const assessments = ["PHQ", "LLM"];
      const errors = [];

      for (const assessmentType of assessments) {
        const response = await fetch(
          `/admin/facial-analysis/delete/${sessionId}/${assessmentType}`,
          {
            method: "DELETE",
            headers: {
              "Content-Type": "application/json",
            },
          }
        );

        const httpStatus = response.status;
        const result = await response.json();
        const data = result.status === "OLKORECT" ? result.data : result;

        if (!data.success && httpStatus !== 404) {
          errors.push(
            `${assessmentType}: ${data.message || "Delete failed"}`
          );
        }
      }

      if (errors.length === 0) {
        alert("PHQ and LLM analysis deleted successfully!");
      } else if (errors.length < assessments.length) {
        alert(
          "Some analysis deleted, but issues occurred:\n\n" +
            errors.join("\n")
        );
      } else {
        alert("Delete failed:\n\n" + errors.join("\n"));
      }

      this.refreshSessions();
    } catch (error) {
      alert(`Error deleting session analysis:\n\n${error.message}`);
    }
  },
};

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  facialAnalysis.init();
});
