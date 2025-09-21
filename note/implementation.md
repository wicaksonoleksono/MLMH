# Async Operations Implementation Notes

## Context & Why

### Problem
- PHQ individual response saves block the UI
- LLM chat responses block other users
- Camera file uploads block the assessment flow
- Multiple users experience performance degradation due to blocking I/O operations

### Solution Approach
Instead of rewriting to ASGI (which adds complexity without real benefits), we implement a two-phase approach:

1. **Phase 1**: Change Gunicorn worker class to `gevent` for async I/O benefits
2. **Phase 2**: Make database operations async in service layer

## Phase 1: Gunicorn Gevent Workers

### Change Required
```bash
# In manage.sh, change this line:
WORKER_CLASS="gthread"
# To:
WORKER_CLASS="gevent"
```

### Benefits
- ✅ Non-blocking I/O operations
- ✅ Better concurrent user handling  
- ✅ No code changes required
- ✅ Easy rollback if issues
- ✅ Battle-tested solution

### Technical Details
- Gevent provides greenlet-based async I/O
- Flask routes remain synchronous (no code changes)
- Database connections become non-blocking
- File operations become non-blocking
- Network requests become non-blocking

## Phase 2: Service Layer Async Operations

### PHQ Service Async Implementation
```python
# Individual response saves (non-blocking)
async def update_response_async(session_id: str, question_id: int, updates: Dict[str, Any]):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, PHQResponseService.update_response, session_id, question_id, updates)

# Bulk submit (non-blocking)  
async def save_session_responses_async(session_id: str, responses_data: List[Dict[str, Any]]):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, PHQResponseService.save_session_responses, session_id, responses_data)
```

### LLM Service Async Implementation
```python
# Conversation turn saves (non-blocking)
async def create_conversation_turn_async(session_id: str, turn_number: int, ai_message: str, user_message: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, LLMConversationService.create_conversation_turn, 
                                      session_id, turn_number, ai_message, user_message)

# Message streaming (non-blocking)
async def save_message_async(session_id: str, message_data: Dict[str, Any]):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, LLMConversationService.save_message, session_id, message_data)
```

### Camera Service Async Implementation
```python
# Batch capture creation (non-blocking)
async def create_batch_capture_async(assessment_id: str, filenames: List[str], capture_type: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, CameraAssessmentService.create_batch_capture_with_assessment_id,
                                      assessment_id, filenames, capture_type, {})

# File linking (non-blocking)
async def link_captures_async(session_id: str, assessment_id: str, assessment_type: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, CameraAssessmentService.link_incremental_captures_to_assessment,
                                      session_id, assessment_id, assessment_type)
```

## Implementation Strategy

### 1. Gunicorn Worker Change
- Simple one-line change in `manage.sh`
- Immediate async I/O benefits
- No code changes required

### 2. Service Layer Async Wrappers
- Create async versions of critical database operations
- Use `asyncio.run_in_executor()` to run sync operations in thread pool
- Maintain existing service layer logic (no rewrite needed)

### 3. Route Layer Integration
- Routes can call async service methods with `await`
- Or use `asyncio.run()` for sync route compatibility
- Gradual migration possible

## Expected Performance Improvements

### Before (gthread)
- PHQ response save: ~100-200ms blocking
- LLM chat response: ~500-1000ms blocking  
- Camera batch upload: ~200-500ms blocking
- Concurrent users: Limited by worker count

### After (gevent + async services)
- PHQ response save: ~10-20ms non-blocking
- LLM chat response: ~50-100ms non-blocking
- Camera batch upload: ~20-50ms non-blocking  
- Concurrent users: Significantly higher capacity

## Risk Mitigation

### Rollback Plan
```bash
# If issues occur, immediately rollback:
WORKER_CLASS="gthread"
```

### Testing Strategy
1. Test with single user first
2. Test with multiple concurrent users
3. Monitor error logs during transition
4. Verify all assessment flows work correctly

## Dependencies

### Required Packages
```bash
pip install gevent  # Should already be installed
```

### Optional Monitoring
```bash
pip install psutil  # For performance monitoring
```

## Monitoring Points

### Key Metrics to Watch
- Response times for PHQ saves
- LLM chat response latency
- Camera upload completion times
- Error rates during concurrent usage
- Memory usage patterns

### Log Analysis
- Check for gevent-related warnings
- Monitor database connection pool usage
- Watch for any timeout issues