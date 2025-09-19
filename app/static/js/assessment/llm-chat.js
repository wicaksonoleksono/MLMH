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

    // Assessment timing variables
    assessmentStartTime: null,
    currentMessageStartTime: null,

    // Initialization guard
    isInitialized: false,

    // Initialize
    async init() {
      // Prevent double initialization
      if (this.isInitialized) {
        return;
      }

      this.isInitialized = true;
      this.assessmentStartTime = Date.now();
      this.startConversationTimer();
      await this.initCamera();
      await this.loadProgress(); // Use new progress endpoint instead
      this.setupAbandonTracking();
      // No more greeting message - will be loaded from progress if needed
    },

    // Removed addGreetingMessage - greeting now comes from backend LangChain template

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
          cameraSettings,
          this.conversationId  // Pass conversation ID as assessment ID
        );
        await this.cameraManager.initialize();
        
        // Give camera extra time to be fully ready before any captures
        await new Promise(resolve => setTimeout(resolve, 1000));
      } catch (error) {
        // Camera initialization failed - continue without camera
      }
    },

    setupAbandonTracking() {
      // Only handle camera cleanup on completion - no abandon tracking
      this.markAsCompleted = () => {
        // Clean up camera when assessment completes
        if (this.cameraManager) {
          this.cameraManager.cleanup();
        }
      };
    },

    async loadProgress() {
      try {
        const result = await apiCall(`/assessment/llm/progress/${this.sessionId}`);
        
        if (result && result.status === "OLKORECT") {
          // Get conversation state from backend
          this.conversationId = result.data.conversation_id;
          this.conversationEnded = result.data.conversation_ended;
          this.exchangeCount = result.data.exchange_count;
          
          // Load existing conversation messages
          this.messages = result.data.conversation_messages.map(msg => ({
            id: msg.id,
            type: msg.type,
            content: msg.content,
            streaming: msg.streaming || false,
            timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
            turn_number: msg.turn_number,
            is_greeting: msg.is_greeting || false
          }));
          
          // Set messageId counter to be higher than existing messages
          const existingIds = this.messages.map(m => m.id).filter(id => typeof id === 'number');
          this.messageId = existingIds.length > 0 ? Math.max(...existingIds) + 1 : 1;
          
          
          // If conversation is not active and can start, initialize it
          if (result.data.can_start) {
            await this.initializeConversation();
          } else if (result.data.can_continue) {
            // Conversation can continue - no need to initialize
          } else {
          }
          
        } else {
          alert("Error loading conversation: " + (result?.error || "Unknown error"));
        }
      } catch (error) {
        alert("Error loading conversation. Please refresh the page.");
      } finally {
        this.loading = false;
        this.scrollToBottom();
      }
    },

    async initializeConversation() {
      try {
        // Start chat session using the existing endpoint
        const url = `/assessment/llm/start-chat/${this.sessionId}`;
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });

        const result = await response.json();

        if (result.status !== "success") {
        } else {
          // Update conversation_id if needed
          if (result.conversation_id) {
            this.conversationId = result.conversation_id;
            
          }
        }
      } catch (error) {
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

    async sendMessage() {
      
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
          `/assessment/get-stream-token/${this.sessionId}`
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

        // Build stream URL with parameters
        const params = new URLSearchParams({
          session_id: this.sessionId,
          message: userMessage,
          user_token: tokenData.token,
        });
        // Add timing data separately to ensure proper encoding
        params.append("user_timing", JSON.stringify(userTiming));

        const streamUrl = `/assessment/stream/?${params}`;
        const eventSource = new EventSource(streamUrl);

        // Get reference to the bot message we just added
        const botMessage = this.messages[this.messages.length - 1];
        let aiStartTime = null;
        let aiEndTime = null;

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
      } catch (error) {
      }
    },

    async finishConversation() {
      if (this.isFinishing || this.isTyping) return;

      this.isFinishing = true;

      try {
        // Link camera captures to conversation first
        if (this.cameraManager && this.conversationId) {
          try {
            const linkResult = await apiCall(
              `/assessment/camera/link-to-assessment/${this.sessionId}`,
              "POST",
              {
                assessment_id: this.conversationId,
                assessment_type: "LLM",
              }
            );
          } catch (error) {
            // console.log("Camera linking failed:", error);
          }
        }

        // Use new completion endpoint
        const result = await apiCall(
          `/assessment/llm/complete/${this.sessionId}`,
          "POST"
        );

        if (result && result.status === "OLKORECT") {
          this.markAsCompleted();
          window.location.href = result.data.next_redirect;
        } else {
          alert(
            "Error completing conversation: " +
              (result?.error || "Unknown error")
          );
          this.isFinishing = false;
        }
      } catch (error) {
        alert("Error completing conversation. Please try again.");
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
      timerInterval = setInterval(() => {
        conversationTimer++;
        const minutes = Math.floor(conversationTimer / 60);
        const seconds = conversationTimer % 60;
        document.getElementById("conversation-timer").textContent = `${minutes
          .toString()
          .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
      }, 1000);
    },

    stopConversationTimer() {
      if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
      }
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
          } else {
          }
        }
      } catch (error) {
      }
    },

  };
}

// Removed refresh detection - users can now continue where they left off
