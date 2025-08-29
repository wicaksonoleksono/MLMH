<!-- prettier-ignore-start -->
[Admin]:
    - Settings assesment
        - OpenQuestion
            - Open Question Components: (Instruction,Stop parser (Hardcoded), Output Format , Format parsersr  )
        - PHQ 
            - Question (Inspired Off the PHQ) 1 Category can have -> Multiple quesstion 
        - Camera
            - Camera( Settings .  )
    
    - CRUD Session
    - Download Session 
    - Download Bulk Session
    - Check User 
    and shit like taht 
    
[Users]:
    - Assesment 
        - Open Question
            -> Parser for ending conversation </end_statement> (IF this shit outed by the agent then it will automatically Continues, While continuing -> pararel We format the output as son)
        - PHQ 
            -> Auto Scoring. 
        - Pararel with (Context switch) for Camera
            -> Front end logic (Camera use )
            -> Backend just sent a settings and Details.. 
            -> Backend later ingest the json data of Photos and such. 
Stack: Flask, Jinja, SQL with postgre with backup as a local volume, 
<!-- prettier-ignore-end -->

admin : can set settings
User : can perform test 2x in general .

## Session Model Planning

### Session Structure:

- **id**: Primary key
- **user_id**: Foreign key to User
- **is_first**: enum ('phq', 'llm') - determines assessment order (50:50 alternating)
- **status**: enum (started, consent_completed, phq_completed, llm_completed, completed)
- **consent_data**: JSON (consent form responses)
- **phq_data**: JSON (PHQ assessment responses + score)
- **llm_data**: JSON (LLM conversation + analysis)
- **camera_data**: JSON (camera settings + captured data)
- **created_at**: Timestamp
- **updated_at**: Timestamp
- **completed_at**: Timestamp (when fully completed)

### Session Flow:

1. User starts assessment → Session created with status='started' + is_first determined (50:50 alternating)
2. User completes consent → status='consent_completed', consent_data saved
3. If is_first='phq': PHQ first → LLM second
4. If is_first='llm': LLM first → PHQ second
5. Camera data processed → status='completed', camera_data saved

### 50:50 Alternating Logic:

- Track total session count globally
- Even session count (0,2,4...) → is_first='phq'
- Odd session count (1,3,5...) → is_first='llm'
- Ensures balanced distribution across all users

### User Limitations:

- Max 2 sessions per user
- Check session count before creating new session

### Admin Operations:

- Read all sessions (with filters)
- Update session data
- Delete sessions
- Download individual/bulk sessions

### User Operations:

- Create session (auto-start on assessment)
- Continue existing incomplete session
- View session history
