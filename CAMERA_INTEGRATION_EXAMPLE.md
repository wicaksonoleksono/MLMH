# 🎥 Camera Assessment Integration - Now Agnostic!

## ✅ **What We Just Created:**

### **New Assessment Camera Routes:**
```
GET  /assessment/camera/settings/<session_id>     # Fetch camera settings (like PHQ/LLM)
POST /assessment/camera/batch-upload/<session_id> # Enhanced batch upload with JWT 
GET  /assessment/camera/status/<session_id>       # Get camera capture status
GET  /assessment/camera/captures/<session_id>     # Get all captures for session
```

## 🚀 **How Frontend Should Be Updated:**

### **Before (Template-based - ❌):**
```javascript
// PHQ/LLM templates currently do this:
const cameraSettings = {{ camera_settings | tojson | safe }} || {};
this.cameraManager = new CameraManager(this.sessionId, 'phq', cameraSettings);
```

### **After (API-based - ✅):**
```javascript
// Should become agnostic like PHQ/LLM:
const settingsResult = await apiCall(`/assessment/camera/settings/${this.sessionId}`);
const cameraSettings = settingsResult?.data?.settings || {};
this.cameraManager = new CameraManager(this.sessionId, 'phq', cameraSettings);
```

## 📊 **Enhanced Upload with JSON Stacking:**

### **CameraManager.js Update:**
```javascript
async uploadBatch(responseIds = null) {
    // Stack filename, timestamp as JSON metadata
    const capturesMetadata = this.captures.map((capture, index) => ({
        timestamp: capture.timestamp,
        trigger: capture.trigger,
        file_size: capture.file_size,
        phq_response_id: responseIds?.[index], // Link to PHQ response
        llm_conversation_id: this.currentResponseId // Link to LLM turn
    }));
    
    const formData = new FormData();
    formData.append('session_id', this.sessionId);
    formData.append('captures_metadata', JSON.stringify(capturesMetadata)); // ✅ JSON Stack!
    
    // Add files
    this.captures.forEach((capture, index) => {
        formData.append(`capture_${index}`, capture.blob, `capture_${index}.jpg`);
    });
    
    // Upload to new agnostic endpoint
    const result = await fetch(`/assessment/camera/batch-upload/${this.sessionId}`, {
        method: 'POST',
        body: formData,
        headers: {
            'Authorization': `Bearer ${getJWTToken()}` // ✅ JWT validation
        }
    });
}
```

## 🎯 **Perfect Architecture Now:**

### **Assessment Routes Structure:**
```
/routes/assessment/
├── phq_routes.py        ✅ PHQ-specific endpoints
├── llm_routes.py        ✅ LLM-specific endpoints  
├── camera_routes.py     ✅ Camera-specific endpoints (NEW!)
└── __init__.py          ✅ All registered
```

### **Frontend Integration:**
```javascript
// PHQ Assessment
const phqQuestions = await apiCall('/assessment/phq/start/session_id');
const cameraSettings = await apiCall('/assessment/camera/settings/session_id');

// LLM Assessment  
const llmStatus = await apiCall('/assessment/llm/start/session_id');
const cameraSettings = await apiCall('/assessment/camera/settings/session_id');
```

## 🔗 **Session FK Linking (Still Perfect):**

```sql
-- All using same session_id FK:
assessment_sessions.id (UUID)
    ↓
phq_responses.session_id           ✅
llm_conversations.session_id       ✅  
llm_analysis_results.session_id    ✅
camera_captures.session_id         ✅ (Enhanced with response linking!)
```

## ⚡ **Key Benefits Achieved:**

1. **✅ Agnostic Architecture** - Camera now has its own assessment routes like PHQ/LLM
2. **✅ Settings Endpoint** - Dynamic fetching instead of Jinja template injection  
3. **✅ JWT Token Support** - Proper authentication for uploads
4. **✅ JSON Stacking** - Metadata bundled as JSON before sending
5. **✅ Enhanced Linking** - Links camera captures to specific PHQ/LLM responses
6. **✅ Consistent API** - Same patterns as PHQ/LLM endpoints
7. **✅ Session FK** - Still uses session_id as the master foreign key

Camera is now a **first-class assessment citizen** just like PHQ and LLM! 🎯