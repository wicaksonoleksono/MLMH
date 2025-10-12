# Facial Analysis Service Architecture

## Separation of Concerns (SOC)

This document explains how the facial analysis system is properly separated into independent components.

## Directory Structure

```
/home/wicaksonolxn/Documents/KJ/MH/
│
├── facial_analysis.service/          # gRPC Service (SEPARATE PROCESS)
│   ├── inference.proto               # gRPC contract
│   ├── generated/                    # Generated protobuf code
│   │   ├── inference_pb2.py
│   │   └── inference_pb2_grpc.py
│   ├── server/
│   │   └── inference_server.py       # gRPC server (LibreFace wrapper)
│   ├── client/
│   │   └── inference_client.py       # gRPC client (used by Flask)
│   └── requirements.txt              # LibreFace, grpcio, etc.
│
└── app/                              # Flask Application
    ├── model/assessment/
    │   └── facial_analysis.py        # Database model
    ├── services/facial_analysis/
    │   └── processingService.py      # Business logic
    └── routes/admin/
        └── facial_analysis_routes.py # HTTP endpoints (TODO)
```

## Component Responsibilities

### 1. gRPC Service (`facial_analysis.service/`)

**Purpose**: Stateless image inference using LibreFace

**Runs**: Separate process on port 50051

**Does**:
- Loads LibreFace model (CPU or GPU)
- Accepts image path via gRPC
- Returns facial expression, AUs, head pose, landmarks
- NO database access
- NO Flask knowledge

**Start Command**:
```bash
cd facial_analysis.service
python server/inference_server.py --port 50051 --device cpu --workers 1
```

### 2. Flask Application (`app/`)

**Purpose**: Web application, business logic, database

**Does**:
- HTTP routes for admin dashboard
- Session management
- JSONL file writing
- Database updates
- Calls gRPC service via client
- NO LibreFace import

### 3. Communication Flow

```
User clicks "Process Images"
  ↓
Flask Route (facial_analysis_routes.py)
  ↓
ProcessingService.process_session_assessment()
  ↓
For each image:
  ↓
FacialInferenceClient.analyze_image() → gRPC call
  ↓
FacialInferenceServicer.AnalyzeImage() → LibreFace
  ↓
Returns results
  ↓
ProcessingService writes JSONL file
  ↓
Updates SessionFacialAnalysis in database
  ↓
Returns status to user
```

## Data Flow

### Input
- Session ID + Assessment Type ('PHQ' or 'LLM')
- Images stored in `static/uploads/`
- Timing data in `CameraCapture.capture_metadata`

### Processing
1. ProcessingService fetches images from DB
2. Sorts by `seconds_since_assessment_start`
3. Calls gRPC service for each image
4. Collects results in memory

### Output
**JSONL File** (`facial_analysis/session_{id}_{type}_{timestamp}.jsonl`):
```jsonl
{"filename": "img_001.jpg", "assessment_type": "PHQ", "timing": {...}, "analysis": {...}}
{"filename": "img_002.jpg", "assessment_type": "PHQ", "timing": {...}, "analysis": {...}}
```

**Database Record** (`SessionFacialAnalysis`):
- Links to JSONL file path
- Processing status and metrics
- Summary statistics

## Setup Instructions

### 1. Generate Protobuf Code
```bash
cd /home/wicaksonolxn/Documents/KJ/MH/facial_analysis.service
python -m grpc_tools.protoc -I. \
  --python_out=generated \
  --grpc_python_out=generated \
  inference.proto
```

### 2. Install LibreFace (Separate Conda Env)
```bash
conda create -n libreface python=3.9
conda activate libreface
# Follow: https://github.com/ihp-lab/LibreFace
```

### 3. Start gRPC Server
```bash
conda activate libreface
cd facial_analysis.service
python server/inference_server.py
```

### 4. Start Flask App
```bash
# Different terminal/conda env
conda activate your_flask_env
cd app
flask run
```

## Why This Separation?

### Benefits:
1. **Isolation**: If LibreFace crashes, Flask keeps running
2. **Independent Deployment**: gRPC can run on GPU server, Flask on CPU
3. **Different Environments**: LibreFace needs Python 3.9, Flask can use 3.11
4. **Scalability**: Can add more gRPC workers without touching Flask
5. **Clean Code**: No LibreFace imports pollute Flask codebase
6. **Testing**: Can mock gRPC client for Flask unit tests

### Design Principles:
- **Single Responsibility**: Each component does ONE thing
- **Dependency Inversion**: Flask depends on gRPC interface, not implementation
- **Interface Segregation**: Proto defines minimal contract
- **Separation of Concerns**: Business logic ≠ Inference ≠ HTTP routes

## Key Landmarks Extracted

Only 25 important facial landmarks (not all 478):

- **Eyes**: outer, inner, upper lid, lower lid (8 points)
- **Brows**: outer, mid, inner (6 points)
- **Mouth**: left, right, upper, lower (4 points)
- **Nose**: bridge, tip (2 points)
- **Face**: chin, cheeks, forehead (4 points)

## Action Units Tracked

12 AUs with binary presence and intensity:
- AU1, AU2, AU4, AU5, AU6, AU9
- AU12, AU15, AU17, AU20, AU25, AU26

## Port Configuration

- **gRPC Server**: 50051
- **Flask App**: 5000 (or configured)

**Never expose gRPC port publicly** - internal communication only.
