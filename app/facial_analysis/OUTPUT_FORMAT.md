# Facial Analysis Output Format

## JSONL File Structure

Each processed assessment generates a JSONL file with **one JSON object per line** (one per image), sorted chronologically by `seconds_since_assessment_start`.

### File Naming Convention
```
facial_analysis/session_{session_id}_{assessment_type}_{timestamp}.jsonl
```

Example:
- `facial_analysis/session_abc123_PHQ_20250109_143022.jsonl`
- `facial_analysis/session_abc123_LLM_20250109_151530.jsonl`

## JSONL Entry Format

Each line contains a JSON object with the following structure:

```json
{
  "filename": "user123_s1_20250109_143025_ghi789.jpg",
  "assessment_type": "PHQ",
  "user_timing": {
    "seconds_since_assessment_start": 3,
    "end_seconds": 5,
    "duration_seconds": 2,
    "absolute_timestamp": "2025-01-09T14:30:25Z"
  },
  "analysis": {
    "facial_expression": "Sadness",
    "head_pose": {
      "pitch": 5.2,
      "yaw": -0.8,
      "roll": 1.1
    },
    "action_units": {
      "au_1": 1,
      "au_2": 0,
      "au_4": 1,
      ...
    },
    "au_intensities": {
      "au_1": 2.3,
      "au_2": 0.0,
      "au_4": 1.8,
      ...
    },
    "key_landmarks": [
      {"index": 33, "x": 0.342, "y": 0.445, "z": -0.015},
      {"index": 133, "x": 0.415, "y": 0.448, "z": -0.012},
      ...
    ]
  },
  "inference_time_ms": 132
}
```

## Field Descriptions

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `filename` | string | Image filename (relative to upload directory) |
| `assessment_type` | string | Either "PHQ" or "LLM" |
| `inference_time_ms` | int | Time taken for LibreFace processing (milliseconds) |

### User Timing Object

**Preserves exact timing from frontend camera capture:**

| Field | Type | Description |
|-------|------|-------------|
| `seconds_since_assessment_start` | int | Seconds elapsed from when assessment started |
| `end_seconds` | int | End time (usually same as start for instant captures) |
| `duration_seconds` | int | Duration of user interaction before capture |
| `absolute_timestamp` | string | ISO 8601 timestamp of when image was captured |

**Why This Matters:**
- Researchers can analyze emotional progression over time
- `seconds_since_assessment_start` enables temporal alignment across users
- `absolute_timestamp` provides exact moment of capture
- `duration_seconds` shows how long user interacted before capture

### Analysis Object

#### facial_expression
- Type: `string`
- Possible values: `"Neutral"`, `"Happiness"`, `"Sadness"`, `"Anger"`, `"Fear"`, `"Disgust"`, `"Surprise"`
- Source: LibreFace emotion classifier

#### head_pose
- Type: `object`
- Fields:
  - `pitch` (float): Head rotation up/down (degrees)
  - `yaw` (float): Head rotation left/right (degrees)
  - `roll` (float): Head tilt (degrees)

#### action_units
- Type: `object`
- Binary presence (0 or 1) for 12 Action Units:
  - `au_1`: Inner Brow Raiser
  - `au_2`: Outer Brow Raiser
  - `au_4`: Brow Lowerer
  - `au_5`: Upper Lid Raiser
  - `au_6`: Cheek Raiser
  - `au_9`: Nose Wrinkler
  - `au_12`: Lip Corner Puller
  - `au_15`: Lip Corner Depressor
  - `au_17`: Chin Raiser
  - `au_20`: Lip Stretcher
  - `au_25`: Lips Part
  - `au_26`: Jaw Drop

#### au_intensities
- Type: `object`
- Float intensity values (0.0 - 5.0) for same 12 AUs
- Higher values = stronger activation

### Understanding Action Units: Binary vs Intensity

Action Units (AUs) come from the **Facial Action Coding System (FACS)** and LibreFace provides **TWO** measurements for each AU:

#### 1. Binary Detection (`action_units`) - 0 or 1
Indicates if the AU is **actively detected**:
- **0** = Not detected / Below threshold
- **1** = Detected / Present above threshold

Think of it as: **"Is this muscle movement happening? Yes or No?"**

#### 2. Intensity Values (`au_intensities`) - 0.0 to 5.0
Indicates **HOW STRONG** the muscle movement is:
- **0.0** = No activation
- **0.5 - 1.0** = Trace/weak activation
- **1.0 - 3.0** = Moderate activation
- **3.0 - 5.0** = Strong/extreme activation

#### Example from Real Data:
```json
{
  "action_units": {
    "au_12": 0,    // Lip Corner Puller (smile) - NOT detected
    "au_17": 1,    // Chin Raiser - DETECTED
    ...
  },
  "au_intensities": {
    "au_12": 0.029,  // Very weak activation (below threshold)
    "au_17": 0.109,  // Weak but above threshold
    ...
  }
}
```

**Interpretation:**
- **au_12** (Lip Corner Puller - smiling):
  - Binary: `0` → Not actively smiling
  - Intensity: `0.029` → Trace activation (almost nothing)

- **au_17** (Chin Raiser):
  - Binary: `1` → Actively detected
  - Intensity: `0.109` → Weak activation but above threshold

#### When to Use Which?

**Use Binary (`action_units`) for:**
- Quick yes/no analysis: "Did the person smile during this question?"
- Counting AU occurrences: "How many times was AU_12 active?"
- Simple presence/absence statistics

**Use Intensity (`au_intensities`) for:**
- Measuring expression strength: "How much did they smile?"
- Detecting subtle changes: Low intensities below binary threshold
- Fine-grained emotional analysis
- Correlation with depression severity scores

**Both are included** in the JSONL output so you can use whichever fits your research needs.

#### key_landmarks
- Type: `array of objects`
- 25 important facial landmarks (not all 478 MediaPipe points)
- Each landmark:
  ```json
  {
    "index": 33,      // MediaPipe landmark index
    "x": 0.342,       // Normalized x coordinate (0-1)
    "y": 0.445,       // Normalized y coordinate (0-1)
    "z": -0.015       // Depth estimate
  }
  ```

**Landmark Indices:**
- Eyes: 33, 133, 159, 145, 263, 362, 386, 374
- Brows: 46, 105, 70, 276, 334, 300
- Mouth: 61, 291, 13, 14
- Nose: 1, 0
- Chin: 152
- Cheeks: 234, 454
- Forehead: 10

## Reading JSONL Files

### Python Example
```python
import json

results = []
with open('session_abc123_PHQ_20250109.jsonl', 'r') as f:
    for line in f:
        results.append(json.loads(line))

# Results are already sorted chronologically
for result in results:
    time = result['user_timing']['seconds_since_assessment_start']
    emotion = result['analysis']['facial_expression']
    print(f"At {time}s: {emotion}")
```

### R Example
```r
library(jsonlite)

# Read JSONL file
lines <- readLines('session_abc123_PHQ_20250109.jsonl')
results <- lapply(lines, fromJSON)

# Convert to dataframe
df <- do.call(rbind, lapply(results, function(x) {
  data.frame(
    time = x$user_timing$seconds_since_assessment_start,
    emotion = x$analysis$facial_expression,
    au_12 = x$analysis$action_units$au_12
  )
}))
```

## Chronological Ordering

**IMPORTANT:** All JSONL files are pre-sorted by `seconds_since_assessment_start` in ascending order.

This means:
- First line = earliest capture
- Last line = latest capture
- Time flows naturally from top to bottom

Researchers can directly analyze temporal progressions without re-sorting.

## Use Cases

### 1. Emotional Progression Analysis
Track how emotions change during PHQ questionnaire:
```
0s: Neutral → 5s: Sadness → 12s: Neutral → 18s: Happiness
```

### 2. Action Unit Correlation
Analyze which AUs co-occur with depression symptoms

### 3. Temporal Alignment
Compare facial expressions across multiple users at same assessment timepoints

### 4. LLM Conversation Analysis
See how facial expressions change during chatbot interaction

## Database Record

In addition to JSONL file, metadata is stored in `SessionFacialAnalysis` table:

```python
{
    'id': 'analysis_uuid',
    'session_id': 'session_uuid',
    'assessment_type': 'PHQ',
    'jsonl_file_path': 'facial_analysis/session_abc_PHQ_20250109.jsonl',
    'status': 'completed',
    'total_images_processed': 45,
    'images_with_faces_detected': 43,
    'images_failed': 2,
    'processing_time_seconds': 12.5,
    'avg_time_per_image_ms': 125,
    'summary_stats': {
        'dominant_emotion': 'Neutral',
        'emotion_distribution': {'Neutral': 30, 'Sadness': 8, 'Happiness': 5},
        'avg_au_activations': 2.3,
        'most_active_aus': ['au_12', 'au_6', 'au_1']
    }
}
```

## Export

JSONL files are included in session export ZIP:
```
session_abc123_export.zip
├── session_info.json
├── phq_responses.json
├── llm_conversation.json
├── images/
│   ├── phq/
│   └── llm/
└── facial_analysis/
    ├── session_abc123_PHQ_20250109.jsonl
    └── session_abc123_LLM_20250109.jsonl
```
