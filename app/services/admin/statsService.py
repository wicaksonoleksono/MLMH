from ...db import get_session
from ...model.shared.users import User
from ...model.shared.enums import UserType
from ...model.assessment.sessions import AssessmentSession

class StatsService:
    @staticmethod
    def get_dashboard_stats():
        """Get basic stats for admin dashboard"""
        with get_session() as db:
            # User stats
            total_users = db.query(User).count()
            admin_users = db.query(User).join(UserType).filter(UserType.name == 'admin').count()
            regular_users = total_users - admin_users
            
            # Session stats
            total_sessions = db.query(AssessmentSession).count()
            completed_sessions = db.query(AssessmentSession).filter(AssessmentSession.status == 'COMPLETED').count()
            completion_rate = int((completed_sessions / total_sessions * 100)) if total_sessions > 0 else 0
            
            return {
                'users': {
                    'total': total_users,
                    'admins': admin_users,
                    'regular': regular_users
                },
                'assessments': {
                    'total_sessions': total_sessions,
                    'completed_sessions': completed_sessions,
                    'completion_rate': completion_rate
                },
                'settings': {
                    'total_settings': 4,
                    'assessment_configs': 2,
                    'media_settings': 1
                }
            }
    
    @staticmethod
    def get_user_sessions_preview():
        """Get user sessions preview: UserID | Username | Session1 | Session2"""
        with get_session() as db:
            # Get regular users only
            users = db.query(User).join(UserType).filter(UserType.name == 'user').all()
            
            preview_data = []
            for user in users:
                # Get user's sessions
                sessions = db.query(AssessmentSession).filter(AssessmentSession.user_id == user.id).order_by(AssessmentSession.created_at).all()
                
                session1_status = "Not Done"
                session2_status = "Not Done"
                
                if len(sessions) >= 1:
                    s1 = sessions[0]
                    # Session 1 is done if BOTH PHQ and LLM are completed
                    session1_status = "Done" if (s1.phq_completed_at and s1.llm_completed_at) else "Not Done"
                
                if len(sessions) >= 2:
                    s2 = sessions[1]
                    # Session 2 is done if BOTH PHQ and LLM are completed
                    session2_status = "Done" if (s2.phq_completed_at and s2.llm_completed_at) else "Not Done"
                
                preview_data.append({
                    'user_id': user.id,
                    'username': user.uname,
                    'session1': session1_status,
                    'session2': session2_status
                })
            
            return preview_data