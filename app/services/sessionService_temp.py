    @staticmethod
    def mark_phq_instructions_viewed(session_id: str):
        """Mark PHQ instructions as viewed for a session"""
        from datetime import datetime
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            session.phq_instructions_viewed_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def mark_llm_instructions_viewed(session_id: str):
        """Mark LLM instructions as viewed for a session"""
        from datetime import datetime
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            session.llm_instructions_viewed_at = datetime.utcnow()
            db.commit()