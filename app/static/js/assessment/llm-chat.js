// app/static/js/assessment/llm-chat.js
// Exact copy of LLM chat JavaScript from template

// Global timer variables need to be declared outside the function
let timerInterval;
let conversationTimer = 0;

function chatInterface(sessionId) {
  return {
    // State
    messages: [],
    currentMessage: "",
    isTyping: false,
    isFinishing: false,
    conversationEnded: false,
    loading: true,

    // Session data
    sessionId: sessionId,
    conversationId: null, // For assessment-first camera approach
    exchangeCount: 0,
    messageId: 1,
    cameraManager: null,

    // Initialize
    async init() {
      // console.log("Chat interface initializing...");
      this.startConversationTimer();
      await this.initCamera();
      // console.log("About to initialize chat...");
      await this.initializeChat();
      this.setupAbandonTracking();
      // console.log("Chat interface initialized");
    },

    async initCamera() {
      try {
        const cameraResult = await apiCall(
          `/assessment/camera/settings/${this.sessionId}`
        );
        const cameraSettings = cameraResult?.data?.data?.settings || {};
        // console.log("LLM Camera settings loaded:", cameraSettings);

        this.cameraManager = new CameraManager(
          this.sessionId,
          "llm",
          cameraSettings
        );
        await this.cameraManager.initialize();
        // console.log("LLM Camera initialized successfully");
      } catch (error) {
        console.error("LLM Camera initialization failed:", error);
        // Camera initialization failed - continue without camera
      }
    },

    setupAbandonTracking() {
      // Track when user leaves the page
      let assessmentCompleted = false;
      window.addEventListener("beforeunload", () => {
        if (!assessmentCompleted && !this.conversationEnded) {
          // Use sendBeacon for reliable tracking when page unloads
          navigator.sendBeacon(
            `/assessment/abandon/${this.sessionId}`,
            JSON.stringify({ reason: "User left LLM assessment page" })
          );
        }
      });

      // Track when user navigates away
      window.addEventListener("pagehide", () => {
        if (!assessmentCompleted && !this.conversationEnded) {
          fetch(`/assessment/abandon/${this.sessionId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              reason: "User navigated away from LLM assessment",
            }),
            keepalive: true,
          }).catch(() => {}); // Ignore errors
        }
      });

      // Set completion flag to prevent abandon calls on successful redirect
      this.markAsCompleted = () => {
        assessmentCompleted = true;
        // Clean up camera when assessment completes
        if (this.cameraManager) {
          this.cameraManager.cleanup();
        }
      };
    },

    async initializeChat() {
      // console.log("Initializing chat with session ID:", this.sessionId);
      try {
        // Start chat session
        const url = `/assessment/llm/start-chat/${this.sessionId}`;
        // console.log("Calling start chat endpoint:", url);

        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });

        // console.log("Start chat response status:", response.status);
        const result = await response.json();
        // console.log("Start chat response:", result);

        if (result.status !== "success") {
          console.error("Start chat failed:", result.message);
        } else {
          // Get conversation_id for assessment-first camera approach
          this.conversationId = result.conversation_id;

          // Update camera manager with conversation_id
          if (this.cameraManager) {
            this.cameraManager.assessmentId = this.conversationId;
          }
        }

        this.loading = false;
        this.scrollToBottom();
      } catch (error) {
        console.error("Error initializing chat:", error);
        this.loading = false;
        alert("Error starting conversation. Please refresh the page.");
      }
    },

    async sendMessage() {
      if (
        !this.currentMessage.trim() ||
        this.isTyping ||
        this.conversationEnded
      )
        return;

      // Capture on message send
      if (this.cameraManager) {
        try {
          const result = await this.cameraManager.onMessageSend();
          // console.log("Camera onMessageSend result:", result);
        } catch (error) {
          console.error("Camera onMessageSend error:", error);
        }
      }

      const userMessage = this.currentMessage.trim();
      this.currentMessage = "";

      // Add user message to UI
      this.messages.push({
        id: this.messageId++,
        type: "user",
        content: userMessage,
        timestamp: new Date(),
      });

      // Add AI response placeholder
      this.messages.push({
        id: this.messageId++,
        type: "ai",
        content: "",
        streaming: true,
        timestamp: new Date(),
      });

      this.isTyping = true;
      this.scrollToBottom();

      // Add immediate visual feedback when sending message
      const botMessage = this.messages[this.messages.length - 1];
      botMessage.content = '<span class="typing-cursor">|</span>';
      this.scrollToBottom();

      try {
        // Get stream token for authentication
        const tokenResponse = await fetch(
          `/assessment/get-stream-token/${this.sessionId}`
        );
        const tokenResult = await tokenResponse.json();
        const tokenData =
          tokenResult.status === "OLKORECT" ? tokenResult.data : tokenResult;

        if (!tokenData.token) {
          throw new Error("Failed to get stream token");
        }

        // Build stream URL with parameters
        const params = new URLSearchParams({
          session_id: this.sessionId,
          message: userMessage,
          user_token: tokenData.token,
        });

        const streamUrl = `/assessment/stream/?${params}`;
        const eventSource = new EventSource(streamUrl);

        // Get reference to the bot message we just added
        const botMessage = this.messages[this.messages.length - 1];

        // Add timeout handling
        const timeoutId = setTimeout(() => {
          botMessage.content = `SSE Timeout after 30s`;
          botMessage.streaming = false;
          this.isTyping = false;
          eventSource.close();
        }, 30000);

        eventSource.onmessage = (event) => {
          let data;
          try {
            data = JSON.parse(event.data);
          } catch (parseError) {
            botMessage.content = `Error: Invalid server response`;
            botMessage.streaming = false;
            this.isTyping = false;
            return;
          }

          if (data.type === "chunk") {
            // Clear typing indicator on first chunk
            if (botMessage.content.includes('<span class="typing-cursor">')) {
              botMessage.content = "";
            }
            botMessage.content += data.data;
            this.scrollToBottom();

            // Check conversation_ended flag from backend (immediate detection)
            if (data.conversation_ended) {
              // End conversation immediately when backend detects the tag
              this.conversationEnded = true;
              // Don't wait - finish conversation right now
              eventSource.close();
              this.isTyping = false;
              botMessage.streaming = false;
              this.finishConversation();
            }
          } else if (data.type === "complete") {
            clearTimeout(timeoutId);
            botMessage.streaming = false;
            this.isTyping = false;
            this.exchangeCount++;
            eventSource.close();

            // Check if conversation ended after every message delivery
            this.checkConversationStatus();
          } else if (data.type === "error") {
            clearTimeout(timeoutId);
            botMessage.content = data.message;
            botMessage.streaming = false;
            this.isTyping = false;
            eventSource.close();
          } else if (data.type === "stream_start") {
            // Stream started - clear loading message and show AI is typing
            botMessage.content = '<span class="typing-cursor">|</span>';
            this.scrollToBottom();
          }
        };

        eventSource.onerror = (error) => {
          clearTimeout(timeoutId);
          const botMessage = this.messages[this.messages.length - 1];
          botMessage.content = `<span style="color: red;">Connection error. Please try again.</span>`;
          botMessage.streaming = false;
          this.isTyping = false;
          eventSource.close();
        };
      } catch (error) {
        const botMessage = this.messages[this.messages.length - 1];
        botMessage.content = `Error: ${error.stack || error.toString()}`;
        botMessage.streaming = false;
        this.isTyping = false;
      }
    },

    async finishConversation() {
      if (this.isFinishing || this.isTyping) return;

      this.isFinishing = true;

      try {
        // Add timeout for the finish request
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

        const response = await fetch(
          `/assessment/llm/finish-chat/${this.sessionId}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: controller.signal,
          }
        );

        clearTimeout(timeoutId); // Clear timeout on success
        const result = await response.json();

        // Handle API response wrapper
        const actualResult =
          result.status === "OLKORECT" ? result.data : result;

        if (result.status === "OLKORECT" && actualResult.next_redirect) {
          this.markAsCompleted();

          // console.log("LLM finish result:", actualResult);

          // Camera captures are automatically linked by backend - no frontend action needed

          window.location.href = actualResult.next_redirect;
        } else {
          alert(
            "Error finishing conversation: " +
              (actualResult.message || "Unknown error")
          );
          this.isFinishing = false;
        }
      } catch (error) {
        if (error.name === "AbortError") {
          alert(
            "Waktu koneksi habis saat menyelesaikan percakapan. Silakan coba lagi."
          );
        } else {
          alert("Error finishing conversation. Please try again.");
        }
        this.isFinishing = false;
      }
    },

    async checkConversationStatus() {
      try {
        // console.log(
        //   `Checking conversation status for session ${this.sessionId}`
        // );
        const response = await fetch(
          `/assessment/llm/check/${this.sessionId}`,
          {
            method: "GET",
            headers: { "Content-Type": "application/json" },
          }
        );

        const result = await response.json();
        // console.log("Raw API response:", result);

        const actualResult =
          result.status === "OLKORECT" ? result.data : result;
        // console.log("Processed result:", actualResult);
        // console.log(
        //   `conversation_complete: ${actualResult.conversation_complete}`
        // );

        if (actualResult.conversation_complete) {
          // console.log(" CONVERSATION COMPLETE - triggering end");
          this.handleConversationEnd();
        } else {
          // console.log("Conversation not complete yet");
        }
      } catch (error) {
        // console.log(" Error checking conversation status:", error);
      }
    },

    handleConversationEnd() {
      this.conversationEnded = true;

      // Auto-finish immediately when conversation ends
      this.finishConversation();
    },

    startConversationTimer() {
      timerInterval = setInterval(() => {
        conversationTimer++;
        const minutes = Math.floor(conversationTimer / 60);
        const seconds = conversationTimer % 60;
        document.getElementById("conversation-timer").textContent = `${minutes
          .toString()
          .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
      }, 1000);
    },

    scrollToBottom() {
      this.$nextTick(() => {
        this.$refs.chatContainer.scrollTop =
          this.$refs.chatContainer.scrollHeight;
      });
    },

    async linkCameraToConversations(capture_id, conversation_ids) {
      try {
        // Link camera batch to first conversation record
        if (conversation_ids.length > 0) {
          const linkData = {
            assessment_id: conversation_ids[0],
            assessment_type: "LLM",
          };

          const response = await fetch(
            `/assessment/camera/link-batch/${capture_id}`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(linkData),
            }
          );

          const result = await response.json();
          if (result.status === "OLKORECT") {
            // console.log("Camera batch linked to conversations successfully");
          } else {
            console.error("Failed to link camera batch:", result);
          }
        }
      } catch (error) {
        console.error("Error linking camera to conversations:", error);
      }
    },

    async resetAssessment() {
      if (
        confirm(
          "Apakah Anda yakin ingin mereset assessment ini dan memulai dari awal? Semua jawaban yang belum disimpan akan hilang."
        )
      ) {
        try {
          const response = await fetch(
            `/assessment/reset-session-on-refresh/${this.sessionId}`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
            }
          );

          // Redirect to main menu
          window.location.href = "/";
        } catch (error) {
          alert("Gagal mereset assessment: " + error.message);
        }
      }
    },
  };
}

// Initialize refresh detection for this session
function initializeLLMRefreshDetection(sessionId) {
  setupRefreshDetection(sessionId);
}
