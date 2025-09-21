Now I understand! Let me document the complete
lifecycle and camera handling differences:

📋 ASSESSMENT LIFECYCLE ANALYSIS

🔵 PHQ Assessment Lifecycle:

1. Initialization:

// PHQ Frontend
this.cameraManager = new CameraManager(sessionId,
"phq", cameraSettings, this.assessmentId);

2. Camera Trigger Events:

- ✅ onQuestionStart(): Captures when new question
  loads
- ❌ No onMessageSend(): PHQ doesn't send messages

3. Data Structure:

- Question-Based: User answers questions
  sequentially
- Assessment ID: PHQResponse.id (stable across
  refresh)
- Timing: Per-question timing data

4. Camera Behavior:

// When question loads
await this.cameraManager.onQuestionStart(timing);

🟢 LLM Assessment Lifecycle:

1. Initialization:

// LLM Frontend  
 this.cameraManager = new CameraManager(sessionId,
"llm", cameraSettings, this.conversationId);

2. Camera Trigger Events:

- ✅ onMessageSend(): Captures when user sends
  message to AI
- ❌ No onQuestionStart(): LLM doesn't have discrete
  questions

3. Data Structure:

- Conversation-Based: User chats with AI freely
- Assessment ID: LLMConversation.id (stable across
  refresh)
- Timing: Per-message timing data

4. Camera Behavior:

// When user sends message
await this.cameraManager.onMessageSend(timing);

🔄 CAMERA HANDLING DIFFERENCES

🎯 Core Difference:

| Aspect | PHQ | LLM
|
|-----------------|---------------------------|-----
--------------------|
| Trigger Event | onQuestionStart() |
onMessageSend() |
| Data Pattern | Question-Response pairs |
Conversation flow |
| Timing | Per-question |
Per-message |
| Assessment ID | PHQResponse.id |
LLMConversation.id |
| Camera Settings | capture_on_question_start |
capture_on_message_send |

🛠️ Camera Manager Logic:

Event-Driven Mode:

// PHQ: Triggers on question start
async onQuestionStart(timing = null) {
if (this.cameraSettings.recording_mode ===
"EVENT_DRIVEN" &&
this.cameraSettings.capture_on_question_start)
{
return await this.captureImage("question_start",
timing);
}
}

// LLM: Triggers on message send  
 async onMessageSend(timing = null) {
if (this.cameraSettings.recording_mode ===
"EVENT_DRIVEN" &&
this.cameraSettings.capture_on_message_send) {
return await this.captureImage("message_send",
timing);
}
}

📡 Upload Difference:

PHQ:

- Captures linked to PHQResponse.id (assessment_id)
- Each question = potential capture
- Sequential, predictable timing

LLM:

- Captures linked to LLMConversation.id
  (assessment_id)
- Each user message = potential capture
- Dynamic, conversation-based timing

🎯 WHY THE DIFFERENCE?

Assessment Nature:

1. PHQ: Structured questionnaire → Camera captures
   user's facial expressions when viewing questions
2. LLM: Free conversation → Camera captures user's
   facial expressions when responding to AI

Data Consistency:

- Both use same camera infrastructure
  (CameraManager)
- Both link to stable assessment IDs (reuse strategy
  preserves these)
- Both support resumability via assessment-first
  approach

The difference is purely event-based - PHQ captures
on question events, LLM captures on message events,
but the underlying camera system and data linking is
identical!

● 🎉 Assessment Lifecycle Analysis Complete!

The camera handling difference is intentional and
correct - PHQ captures during question viewing, LLM
captures during message sending, but both use the
same underlying infrastructure with stable
assessment IDs for proper resumability! 🚀V=
