# Mental Health Assessment Application Flow

## Overview
This is a comprehensive mental health assessment platform with admin configuration, user authentication, and multi-modal assessments (PHQ questionnaire + LLM chat).

## Application Architecture Flow

### 1. Entry Points & Authentication

```
Landing Page (/) 
├── Authenticated User
│   ├── Admin → Admin Dashboard (/admin/dashboard)
│   └── Regular User → User Dashboard (/user/dashboard)
└── Unauthenticated → Auth Page (/auth)
    ├── Login Form
    └── Registration Form (with extended profile fields)
```

### 2. User Dashboard Flow

```
User Dashboard (/user/dashboard)
├── Check for Recoverable Session
│   ├── Has Incomplete Session
│   │   ├── Continue Assessment → /assessment/
│   │   ├── Start Fresh → Reset & /assessment/
│   │   └── Dismiss → Hide notification
│   └── No Recoverable Session
│       └── Start New Assessment → /assessment/start (POST)
├── Assessment History Display
│   ├── Show Previous Sessions
│   ├── Progress Indicators
│   ├── Status (Completed/Failed/Abandoned)
│   └── Reset Failed Sessions
└── Session Limits (Max 2 sessions per user)
```

### 3. Assessment Flow (Core Application Logic)

```
Assessment Start (/assessment/start POST)
├── Check Settings Configuration
│   └── Missing Settings → /error/settings-not-configured
├── Check Session Limits (Max 2 per user)
├── Create New Session
│   ├── Random Assessment Order (PHQ-first or LLM-first)
│   ├── Generate Session Token
│   └── Set Initial Status: CREATED
└── Redirect to Assessment Dashboard

Assessment Dashboard (/assessment/)
├── Session Status Routing:
│   ├── No Consent → /assessment/consent
│   ├── No Camera Check → /assessment/camera-check  
│   ├── Ready for Assessment → Direct redirect to first assessment
│   └── Assessment In Progress → Continue where left off

Step 1: Informed Consent (/assessment/consent)
├── Load Consent Form (from admin settings)
├── User Agreement Required
├── Submit Consent (POST)
│   ├── Update Session: consent_completed_at
│   └── Redirect to Camera Check

Step 2: Camera Check (/assessment/camera-check)
├── Browser Camera Permission Request
├── Camera Functionality Test
├── Submit Camera Check (POST)
│   ├── Update Session: camera_completed
│   ├── Set Status: CAMERA_CHECK → Assessment Status
│   └── Redirect to First Assessment (based on session.is_first)

Step 3A: PHQ Assessment (/assessment/phq)
├── Load PHQ Questions (from admin configuration)
├── Single Question Display with Progress
├── Response Collection & Validation
├── Submit All Responses (POST)
│   ├── Calculate Total Score
│   ├── Complete PHQ Assessment
│   ├── Update Session Status
│   └── Auto-redirect to Next Step (LLM or Complete)

Step 3B: LLM Chat Assessment (/assessment/llm)
├── Initialize Chat Session
├── AI Greeting Message (Anisa persona)
├── Real-time Chat Interface
│   ├── User Message Input
│   ├── Streaming AI Responses (SSE)
│   ├── Conversation Timer
│   └── Exchange Counter
├── Conversation End Detection
│   ├── AI detects completion (</end_conversation>)
│   ├── Manual finish button
│   └── Auto-redirect to Next Step

Assessment Completion Flow
├── Single Assessment Complete
│   ├── PHQ Complete → Redirect to LLM
│   ├── LLM Complete → Redirect to PHQ
│   └── Universal Completion Handler (/assessment/complete/<type>/<token>)
└── Both Assessments Complete
    ├── Session Status: COMPLETED
    ├── Calculate Duration
    └── Return to User Dashboard
```

### 4. Admin Panel Flow

```
Admin Dashboard (/admin/dashboard)
├── System Statistics
│   ├── User Counts (Admin/Regular)
│   ├── Assessment Statistics
│   └── Configuration Status
├── Quick Actions
│   ├── Settings Management
│   ├── Assessment Review
│   ├── Media Management
│   └── System Logs
└── Recent Activity Log

Admin Settings (/admin/settings)
├── PHQ Configuration (/admin/phq)
│   ├── Question Categories
│   ├── Scale Configuration
│   ├── Question Management
│   └── Scoring Rules
├── LLM Configuration (/admin/llm)
│   ├── Model Selection
│   ├── System Prompts
│   ├── Conversation Parameters
│   └── API Settings
├── Camera Settings (/admin/camera)
│   ├── Recording Parameters
│   ├── Quality Settings
│   └── Storage Configuration
└── Consent Management (/admin/consent)
    ├── Consent Form Content
    ├── Legal Text
    └── Version Control
```

### 5. Session Management & Recovery

```
Session States:
├── CREATED → Initial state after creation
├── CONSENT → Consent completed, camera check pending
├── CAMERA_CHECK → Camera check done, ready for assessment
├── PHQ_IN_PROGRESS → PHQ assessment active
├── LLM_IN_PROGRESS → LLM chat active
├── BOTH_IN_PROGRESS → Both assessments started
├── COMPLETED → All assessments finished
├── FAILED → Session failed due to error
└── ABANDONED → User quit/left session

Recovery Mechanisms:
├── Automatic Detection of Incomplete Sessions
├── User Choice: Continue vs Start Fresh
├── Session Reset with Version Increment
├── Abandonment Tracking (beforeunload/pagehide events)
└── Maximum Session Limits (2 per user)
```

### 6. Data Flow & Storage

```
User Data:
├── Authentication (JWT + Flask-Login)
├── Extended Profile (age, gender, education, medical info)
├── Session History
└── Assessment Results

Assessment Data:
├── PHQ Responses (question_id, response_value, timing)
├── LLM Chat History (messages, timestamps, analysis)
├── Session Metadata (duration, completion status)
└── Media Data (camera recordings - if configured)

Admin Configuration:
├── PHQ Questions & Scales
├── LLM System Prompts & Models
├── Consent Form Content
├── Camera/Media Settings
└── System Logs
```

### 7. Error Handling & Edge Cases

```
Configuration Errors:
└── Settings Not Configured → /error/settings-not-configured

Session Errors:
├── Session Limit Exceeded → Error message
├── Invalid Session Token → Redirect to dashboard
├── Session Expired → Recovery options
└── Assessment Abandonment → Tracking & recovery

Authentication Errors:
├── Invalid Credentials → Login error
├── Token Expiry → Auto-logout
└── Permission Denied → Redirect to appropriate page

Technical Errors:
├── API Failures → User-friendly error messages
├── Network Issues → Retry mechanisms
└── Browser Compatibility → Graceful degradation
```

### 8. Key Features

**Assessment Features:**
- Randomized assessment order (PHQ-first vs LLM-first)
- Real-time streaming chat with AI
- Progress tracking and session recovery
- Comprehensive user profiling
- Session abandonment detection

**Admin Features:**
- Complete system configuration
- Assessment result monitoring
- User management
- System statistics and logging

**Technical Features:**
- JWT authentication with Flask-Login fallback
- Server-Sent Events (SSE) for real-time chat
- Responsive design with Tailwind CSS
- Alpine.js for interactive components
- Session state management with recovery

### 9. Template Structure & UI Components

```
Base Templates:
├── base.html → Main layout with JWT auth helpers
└── admin/base.html → Admin layout with navigation

Authentication:
└── auth/login_register.html → Combined login/register form

User Interface:
├── landing.html → Public landing page
├── user/dashboard.html → User dashboard with session management
└── error/settings_not_configured.html → Configuration error page

Assessment Flow:
├── assessment/dashboard.html → Assessment progress tracker
├── assessment/consent.html → Informed consent form
├── assessment/camera_check.html → Camera permission test
├── assessment/phq.html → PHQ questionnaire interface
└── assessment/llm.html → Real-time chat interface

Admin Interface:
├── admin/dashboard.html → System overview & statistics
├── admin/settings.html → Configuration hub
├── admin/assessments.html → Assessment results
├── admin/media.html → Media management
├── admin/logs.html → System activity logs
└── admin/settings/[module]/ → Specific configuration pages
    ├── phq/ → PHQ question & scale management
    ├── llm/ → LLM model & prompt configuration
    ├── camera/ → Recording settings
    └── consent/ → Legal form management
```

### 10. API Endpoints & Data Flow

```
Authentication APIs:
├── POST /auth/login → JWT token generation
├── POST /auth/register → User creation with profile
├── GET /auth/logout → Session cleanup
└── GET /auth/profile → User profile data

Assessment APIs:
├── POST /assessment/start → Create new session
├── GET /assessment/ → Session routing logic
├── POST /assessment/consent → Submit consent form
├── POST /assessment/camera-check → Camera validation
├── GET /assessment/phq → PHQ question loading
├── POST /assessment/phq/responses → PHQ submission
├── POST /assessment/llm/start → Initialize chat
├── POST /assessment/llm/stream → Real-time messaging
├── POST /assessment/complete/<type>/<token> → Universal completion
├── GET /assessment/sessions → User session history
├── POST /assessment/recover/<id> → Session recovery
└── POST /assessment/abandon/<id> → Abandonment tracking

Admin APIs:
├── GET /admin/dashboard → System statistics
├── GET/POST /admin/phq → PHQ configuration
├── GET/POST /admin/llm → LLM settings
├── GET/POST /admin/camera → Camera configuration
├── GET/POST /admin/consent → Consent management
└── GET /admin/logs → Activity monitoring
```

This application provides a complete mental health assessment platform with robust session management, comprehensive admin controls, and a user-friendly assessment experience. The flow ensures data integrity, user privacy, and administrative oversight while maintaining a smooth user experience throughout the assessment process.