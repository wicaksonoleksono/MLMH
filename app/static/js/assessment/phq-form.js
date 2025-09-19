// app/static/js/assessment/phq-form.js
// Exact copy of PHQ assessment JavaScript from template

function phqAssessment(sessionId) {
  return {
    sessionId: sessionId,
    loading: true,
    submitting: false,
    submitted: false,
    questions: [],
    responses: {},
    currentQuestionIndex: 0,
    currentResponse: null,
    totalScore: 0,
    scoreAnalysis: "",
    cameraManager: null,
    isResuming: false,
    resumedFromQuestion: 0,
    
    // Assessment timing variables
    assessmentStartTime: null,
    questionStartTime: null,

    get currentQuestion() {
      return this.questions[this.currentQuestionIndex] || null;
    },

    async init() {
      this.assessmentStartTime = Date.now();
      this.questionStartTime = Date.now();
      await this.loadProgress(); // Use progress endpoint instead of loadQuestions
      await this.initCamera();
      this.setupAbandonTracking();
    },

    async initCamera() {
      try {
        const cameraResult = await apiCall(
          `/assessment/camera/settings/${this.sessionId}`
        );
        const cameraSettings = cameraResult?.data?.data?.settings || {};

        this.cameraManager = new CameraManager(
          this.sessionId,
          "phq",
          cameraSettings,
          this.assessmentId  // Pass assessment ID to constructor
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
        const result = await apiCall(`/assessment/phq/progress/${this.sessionId}`);
        if (result && result.status === "OLKORECT") {
          
          // Get assessment state from progress endpoint
          this.questions = result.data.questions;
          this.assessmentId = result.data.assessment_id;
          

          // Set resume position from backend calculation
          this.currentQuestionIndex = result.data.current_question_index || 0;
          const completedCount = result.data.completed_responses_count || 0;
          const resumedFromPrevious = result.data.resumed_from_previous || false;

          // Set resume state
          if (resumedFromPrevious && completedCount > 0) {
            this.isResuming = true;
            this.resumedFromQuestion = this.currentQuestionIndex + 1;
          }

          // Populate responses from questions data (questions already include response_value/response_text)
          this.responses = {};
          this.questions.forEach(question => {
            if (question.response_value !== null) {
              this.responses[question.question_id] = {
                question_id: question.question_id,
                question_number: question.question_number,
                response_value: question.response_value,
                response_text: question.response_text,
                response_time_ms: question.response_time_ms
              };
            }
          });

          // If assessment can start (no questions generated yet), initialize it
          if (result.data.can_start) {
            // The progress endpoint already creates the assessment record
            // Just need to load current response
          } else if (result.data.can_continue) {
          }

          await this.loadCurrentResponse();

          // Trigger camera capture when question loads
          if (this.cameraManager) {
            const currentTime = Date.now();
            const questionStart = Math.floor((currentTime - this.assessmentStartTime) / 1000);
            const timing = {
              start: questionStart,
              end: questionStart,
              duration: 0
            };
            await this.cameraManager.onQuestionStart(timing);
          }
        } else {
          alert(
            "Error loading assessment progress: " + (result?.error || "Unknown error")
          );
        }
      } catch (error) {
        alert("Error: " + error.message);
      } finally {
        this.loading = false;
      }
    },

    async loadCurrentResponse() {
      if (this.currentQuestion) {
        this.currentResponse =
          this.responses[this.currentQuestion.question_id] || null;
        
        // Force UI update after setting currentResponse (use setTimeout for Alpine.js)
        setTimeout(() => {
          this.updateFormUI();
        }, 10);
        
        // Trigger camera capture when new question loads
              if (this.cameraManager) {
                // Pass timing data to camera capture
                const currentTime = Date.now();
                const questionStart = Math.floor((currentTime - this.assessmentStartTime) / 1000);
                const timing = {
                  start: questionStart,
                  end: questionStart,
                  duration: 0
                };
                await this.cameraManager.onQuestionStart(timing);
              }
      }
    },

    updateFormUI() {
      // Force radio button update for existing responses
      if (this.currentResponse && this.currentResponse.response_value !== null) {
        const radioButtons = document.querySelectorAll('input[name="current_response"]');
        radioButtons.forEach(radio => {
          radio.checked = (parseInt(radio.value) === this.currentResponse.response_value);
        });
      }
    },


    async updateCurrentResponse(value, text) {
      if (!this.currentQuestion) return;

      // Set current response ID before capturing image
      if (this.cameraManager) {
        // Set the current response ID for association with captures
        this.cameraManager.setCurrentResponseId(
          this.currentQuestion.question_id
        );
        // Pass timing data to camera capture
        const responseTime = Date.now();
        const questionStart = Math.floor((this.questionStartTime - this.assessmentStartTime) / 1000);
        const questionEnd = Math.floor((responseTime - this.assessmentStartTime) / 1000);
        const timing = {
          start: questionStart,
          end: questionEnd,
          duration: questionEnd - questionStart
        };
        await this.cameraManager.onButtonClick(timing);
      }

      const responseValue = parseInt(value);
      if (isNaN(responseValue)) return;
      
      const responseTime = Date.now();
      const questionStart = Math.floor((this.questionStartTime - this.assessmentStartTime) / 1000);
      const questionEnd = Math.floor((responseTime - this.assessmentStartTime) / 1000);

      this.currentResponse = {
        question_id: this.currentQuestion.question_id,
        response_value: responseValue,
        response_text: text,
        response_time_ms: responseTime - this.questionStartTime,
        // Clean timing metadata
        timing: {
          start: questionStart,
          end: questionEnd,
          duration: questionEnd - questionStart
        }
      };

      this.responses[this.currentQuestion.question_id] = this.currentResponse;
    },

    async nextQuestion() {
      if (!this.currentResponse) return;

      // Auto-save current response before moving to next question
      try {
        await apiCall(
          `/assessment/phq/response/${this.sessionId}/${this.currentQuestion.question_id}`,
          "PUT",
          {
            question_id: this.currentQuestion.question_id,
            question_number: this.currentQuestion.question_number,
            response_value: this.currentResponse.response_value,
            response_text: this.currentResponse.response_text,
            response_time_ms: this.currentResponse.response_time_ms,
            timing: this.currentResponse.timing
          }
        );
      } catch (error) {
      }

      if (this.currentQuestionIndex < this.questions.length - 1) {
        this.currentQuestionIndex++;
        this.questionStartTime = Date.now();
        await this.loadCurrentResponse();
      } else {
        await this.submitAllResponses();
      }
    },

    async previousQuestion() {
      if (this.currentQuestionIndex > 0) {
        this.currentQuestionIndex--;
        this.questionStartTime = Date.now();
        await this.loadCurrentResponse();
      }
    },

    async submitAllResponses() {
      if (this.submitting) return;

      this.submitting = true;

      try {
        // STEP 1: Link existing camera captures to assessment (incremental approach)
        // Captures are already in database, just need to link them
        if (this.cameraManager && this.assessmentId) {
          // console.log("Linking existing captures to assessment:", this.assessmentId);
          try {
            const linkResult = await apiCall(
              `/assessment/camera/link-to-assessment/${this.sessionId}`,
              "POST",
              {
                assessment_id: this.assessmentId,
                assessment_type: "PHQ",
              }
            );
            // console.log("Camera linking result:", linkResult);
          } catch (error) {
            // console.log("Camera linking failed:", error);
          }
        } else {
          // console.log("No camera captures to link");
        }

        // STEP 2: Submit PHQ responses (no camera linking needed)
        const responsesArray = Object.values(this.responses);
        const submitData = { responses: responsesArray };

        const result = await apiCall(
          `/assessment/phq/submit/${this.sessionId}`,
          "POST",
          submitData
        );

        if (result && result.status === "OLKORECT") {
          this.submitted = true;
          this.markAsCompleted();

          // console.log('PHQ submit result:', result);

          window.location.href = result.data.next_redirect;
        } else {
          alert(
            "Error submitting responses: " + (result?.error || "Unknown error")
          );
        }
      } catch (error) {
        alert("Error: " + error.message);
      } finally {
        this.submitting = false;
      }
    },

  };
}

