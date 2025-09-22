// app/static/js/assessment/llm-chat.js
// Exact copy of LLM chat JavaScript from template

// Timer variables moved inside chatInterface to prevent global leaks

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

    // Assessment timing variables
    assessmentStartTime: null,
    currentMessageStartTime: null,

    // Timer variables (per instance to prevent memory leaks)
    timerInterval: null,
    conversationTimer: 0,
    // ss
    // EventSource tracking to prevent connection leaks
    currentEventSource: null,

    // Initialization guard
    isInitialized: false,

    // Initialize (ASYNC VERSION)
    async initAsync() {
      // Prevent double initialization
      if (this.isInitialized) {
        return;
      }

      this.isInitialized = true;
      this.assessmentStartTime = Date.now();
      this.startConversationTimer();
      await this.initCamera();
      await this.initializeChatAsync();
      this.setupAbandonTracking();
      // Use greeting from API response
      this.addGreetingMessage(this.greetingMessage);
    },

    // Initialize (ORIGINAL SYNC VERSION)
    async init() {
      // Prevent double initialization
      if (this.isInitialized) {
        return;
      }

      this.isInitialized = true;
      this.assessmentStartTime = Date.now();
      this.startConversationTimer();
      await this.initCamera();
      await this.initializeChat();
      this.setupAbandonTracking();
      // Use greeting from API response
      this.addGreetingMessage(this.greetingMessage);
    },

    addGreetingMessage(greetingText = null) {
      // Add initial greeting from API response or fallback
      const greetingContent =
        greetingText || "Halo aku Sindi, bagaimana kabar kamu ?";
      this.messages.push({
        id: this.messageId++,
        type: "ai",
        content: greetingContent,
        streaming: true,
        timestamp: new Date(),
      });
      this.scrollToBottom();
    },

    onMessageInput() {
      // Track when user starts typing for accurate timing
      if (!this.currentMessageStartTime && this.currentMessage.trim()) {
        this.currentMessageStartTime = Date.now();
      }
    },

    async initCamera() {
      try {
        const cameraResult = await apiCall(
          `/assessment/camera/settings/${this.sessionId}`
        );
        const cameraSettings = cameraResult?.data?.data?.settings || {};

        this.cameraManager = new CameraManager(
          this.sessionId,
          "llm",
          cameraSettings
        );
        await this.cameraManager.initialize();

        // Give camera extra time to be fully ready before any captures
        await new Promise((resolve) => setTimeout(resolve, 1000));
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
          // Close any active EventSource connections to prevent server-side leaks
          if (this.currentEventSource) {
            this.currentEventSource.close();
            this.currentEventSource = null;
          }
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
          // Close any active EventSource connections to prevent server-side leaks
          if (this.currentEventSource) {
            this.currentEventSource.close();
            this.currentEventSource = null;
          }
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
        // Clean up timer to prevent memory leaks
        this.stopConversationTimer();
      };
    },

    // ASYNC VERSION of initializeChat
    async initializeChatAsync() {
      try {
        // Start chat session using ASYNC route
        const url = `/assessment/llm/start-chat-async/${this.sessionId}`;

        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });

        const result = await response.json();

        if (result.status !== "success") {
          console.error("Start chat async failed:", result.message);
        } else {
          // Get conversation_id for assessment-first camera approach
          this.conversationId = result.conversation_id;

          // Update camera manager with conversation_id
          if (this.cameraManager) {
            this.cameraManager.setConversationId(this.conversationId);
          }

          // Store greeting from API response for proper usage
          this.greetingMessage = result.greeting_message;
        }

        this.loading = false;
        this.scrollToBottom();
      } catch (error) {
        console.error("Error initializing chat async:", error);
        this.loading = false;
        alert("Error starting conversation. Please refresh the page.");
      }
    },

    // ORIGINAL SYNC VERSION of initializeChat
    async initializeChat() {
      try {
        // Start chat session
        const url = `/assessment/llm/start-chat/${this.sessionId}`;

        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });

        const result = await response.json();

        if (result.status !== "success") {
          console.error("Start chat failed:", result.message);
        } else {
          // Get conversation_id for assessment-first camera approach
          this.conversationId = result.conversation_id;

          // Update camera manager with conversation_id
          if (this.cameraManager) {
            this.cameraManager.setConversationId(this.conversationId);
          }

          // Store greeting from API response for proper usage
          this.greetingMessage = result.greeting_message;
        }

        this.loading = false;
        this.scrollToBottom();
      } catch (error) {
        console.error("Error initializing chat:", error);
        this.loading = false;
        alert("Error starting conversation. Please refresh the page.");
      }
    },

    // Utility methods
    scrollToBottom() {
      setTimeout(() => {
        const container = this.$refs.chatContainer;
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      }, 100);
    },

    // ASYNC VERSION of sendMessage
    async sendMessageAsync() {
      if (
        !this.currentMessage.trim() ||
        this.isTyping ||
        this.conversationEnded
      )
        return;

      const userMessage = this.currentMessage.trim();
      this.currentMessage = "";

      // Set message start time if not already set (when user started typing)
      if (!this.currentMessageStartTime) {
        this.currentMessageStartTime = Date.now();
      }

      // Capture on message send with timing data
      if (this.cameraManager) {
        try {
          // Calculate timing before capture
          const captureTime = Date.now();
          const messageStart = Math.floor(
            (this.currentMessageStartTime - this.assessmentStartTime) / 1000
          );
          const messageEnd = Math.floor(
            (captureTime - this.assessmentStartTime) / 1000
          );
          const timing = {
            start: messageStart,
            end: messageEnd,
            duration: messageEnd - messageStart,
          };

          await this.cameraManager.onMessageSend(timing);
        } catch (error) {
          console.error("Camera onMessageSend error:", error);
        }
      }

      // Add user message
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

      try {
        // Get stream token for authentication
        const tokenResponse = await fetch(
          `/assessment/llm/get-stream-token/${this.sessionId}`
        );
        const tokenResult = await tokenResponse.json();
        const tokenData =
          tokenResult.status === "OLKORECT" ? tokenResult.data : tokenResult;

        if (!tokenData.token) {
          throw new Error("Failed to get stream token");
        }

        // Calculate user timing
        const messageEndTime = Date.now();
        const userStart = Math.floor(
          (this.currentMessageStartTime - this.assessmentStartTime) / 1000
        );
        const userEnd = Math.floor(
          (messageEndTime - this.assessmentStartTime) / 1000
        );
        const userTiming = {
          start: userStart,
          end: userEnd,
          duration: userEnd - userStart,
        };

        // Build stream URL with parameters (ASYNC VERSION)
        const params = new URLSearchParams({
          session_id: this.sessionId,
          message: userMessage,
          user_token: tokenData.token,
        });
        // Add timing data separately to ensure proper encoding
        params.append("user_timing", JSON.stringify(userTiming));

        const streamUrl = `/assessment/llm/stream-async/?${params}`;
        const eventSource = new EventSource(streamUrl);
        this.currentEventSource = eventSource; // Track for cleanup

        // Get reference to the bot message we just added
        const botMessage = this.messages[this.messages.length - 1];
        let aiStartTime = null;
        let aiEndTime = null;

        // Add timeout handling
        const timeoutId = setTimeout(() => {
          botMessage.content = `Maaf, sistem sedang mengalami gangguan. Silakan coba lagi.`;
          botMessage.streaming = false;
          this.isTyping = false;
          eventSource.close();
          this.currentEventSource = null; // Clear reference
        }, 99999999999999);

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
            // Record AI start time on first chunk
            if (aiStartTime === null) {
              aiStartTime = Date.now();
            }

            botMessage.content += data.data;
            this.scrollToBottom();

            // Check conversation_ended flag from backend (immediate detection)
            if (data.conversation_ended) {
              this.conversationEnded = true;
              if (aiEndTime === null) {
                aiEndTime = Date.now();
              }
              // Send AI timing before finishing conversation
              this.sendAiTiming(
                userMessage,
                userTiming,
                aiStartTime,
                aiEndTime
              );
              eventSource.close();
              this.currentEventSource = null; // Clear reference
              this.isTyping = false;
              botMessage.streaming = false;
              this.finishConversation();
            }
          } else if (data.type === "complete") {
            clearTimeout(timeoutId);
            if (aiEndTime === null) {
              aiEndTime = Date.now();
            }
            botMessage.streaming = false;
            this.isTyping = false;
            this.exchangeCount++;
            eventSource.close();
            this.currentEventSource = null; // Clear reference

            // Send AI timing to backend
            this.sendAiTiming(userMessage, userTiming, aiStartTime, aiEndTime);

            // Reset timing for next message
            this.currentMessageStartTime = null;

            // Check if conversation ended after every message delivery
            this.checkConversationStatus();
          } else if (data.type === "error") {
            clearTimeout(timeoutId);
            botMessage.content = data.message;
            botMessage.streaming = false;
            this.isTyping = false;
            eventSource.close();
            this.currentEventSource = null; // Clear reference
          } else if (data.type === "stream_start") {
            // Stream started - record AI start time
            if (aiStartTime === null) {
              aiStartTime = Date.now();
            }
            this.scrollToBottom();
          }
        };

        eventSource.onerror = (error) => {
          clearTimeout(timeoutId);
          // Show the actual error instead of generic message
          const errorMessage =
            error.message || error.toString() || "Unknown connection error";
          botMessage.content = `<span style="color: red;">Connection error: ${errorMessage}</span>`;
          botMessage.streaming = false;
          this.isTyping = false;
          eventSource.close();
          this.currentEventSource = null; // Clear reference
        };
      } catch (error) {
        const botMessage = this.messages[this.messages.length - 1];
        botMessage.content = `Error: ${error.stack || error.toString()}`;
        botMessage.streaming = false;
        this.isTyping = false;
      }
    },

    async sendAiTiming(userMessage, userTiming, aiStartTime, aiEndTime) {
      if (!aiStartTime || !aiEndTime) {
        console.log("No AI timing - missing start/end time");
        return;
      }

      // Calculate AI timing
      const aiStart = Math.floor(
        (aiStartTime - this.assessmentStartTime) / 1000
      );
      const aiEnd = Math.floor((aiEndTime - this.assessmentStartTime) / 1000);
      const aiTiming = {
        start: aiStart,
        end: aiEnd,
        duration: aiEnd - aiStart,
      };

      console.log("Sending AI timing:", {
        userMessage: userMessage.substring(0, 20),
        turn: this.exchangeCount,
        userTiming,
        aiTiming,
      });

      try {
        const response = await fetch(
          `/assessment/llm/save-timing/${this.sessionId}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              user_message: userMessage,
              user_timing: userTiming,
              ai_timing: aiTiming,
              turn_number: this.exchangeCount,
            }),
          }
        );
        const result = await response.json();
        console.log("AI timing response:", result);
      } catch (error) {
        console.error("Failed to send AI timing:", error);
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
        const actualResult =
          result.status === "OLKORECT" ? result.data : result;
        if (result.status === "OLKORECT" && actualResult.next_redirect) {
          this.markAsCompleted();
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
        const response = await fetch(
          `/assessment/llm/check/${this.sessionId}`,
          {
            method: "GET",
            headers: { "Content-Type": "application/json" },
          }
        );

        const result = await response.json();

        const actualResult =
          result.status === "OLKORECT" ? result.data : result;

        if (actualResult.conversation_complete) {
          this.handleConversationEnd();
        }
      } catch (error) {
        // Silently ignore errors
      }
    },

    handleConversationEnd() {
      this.conversationEnded = true;

      // Auto-finish immediately when conversation ends
      this.finishConversation();
    },

    // Timer functions
    startConversationTimer() {
      this.timerInterval = setInterval(() => {
        this.conversationTimer++;
        const minutes = Math.floor(this.conversationTimer / 60);
        const seconds = this.conversationTimer % 60;
        document.getElementById("conversation-timer").textContent = `${minutes
          .toString()
          .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
      }, 1000);
    },

    stopConversationTimer() {
      if (this.timerInterval) {
        clearInterval(this.timerInterval);
        this.timerInterval = null;
      }
    },

    async resetAssessment() {
      if (
        confirm(
          "Apakah Anda yakin ingin mereset assessment ini dan memulai dari awal? Semua jawaban yang belum disimpan akan hilang."
        )
      ) {
        try {
          await fetch(
            `/assessment/reset-session-on-refresh/${this.sessionId}`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
            }
          );
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
