# app/services/SMTP/firstSessionReminderService.py
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, not_, exists
import os

from ...model.shared.users import User
from ...model.assessment.sessions import AssessmentSession
from ...db import get_session
from .smtpService import SMTPService
from ..shared.autoLoginService import AutoLoginService
from ...config import Config
from flask import current_app

class FirstSessionReminderService:
    """Service for sending reminder emails to users who registered but haven't started any assessment"""

    @staticmethod
    def get_users_without_assessments(page: int = 1, per_page: int = 15, search_query: str = None) -> Dict[str, Any]:
        """
        Get paginated list of users who have verified email but haven't started any assessments
        
        Args:
            page: Page number for pagination
            per_page: Number of users per page
            search_query: Search query for username/email
            
        Returns:
            Dict with pagination info and user data
        """
        with get_session() as db:
            # Base query: users with verified email but no assessment sessions
            base_query = db.query(User).filter(
                and_(
                    User.email_verified == True,
                    User.email.isnot(None),
                    User.email != '',
                    not_(exists().where(AssessmentSession.user_id == User.id))
                )
            )
            
            # Add search filter if provided
            if search_query:
                from sqlalchemy import or_
                base_query = base_query.filter(
                    or_(
                        User.uname.ilike(f'%{search_query}%'),
                        User.email.ilike(f'%{search_query}%')
                    )
                )
            
            base_query = base_query.order_by(User.created_at.desc())
            
            # Get total count
            total_count = base_query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            users = base_query.offset(offset).limit(per_page).all()
            
            # Format user data
            user_list = []
            for user in users:
                days_since_registration = (datetime.now(timezone.utc) - user.created_at).days
                
                user_data = {
                    'user_id': user.id,
                    'username': user.uname,
                    'email': user.email,
                    'phone': user.phone,
                    'registration_date': user.created_at.strftime('%d %B %Y'),
                    'days_since_registration': days_since_registration,
                    'status': FirstSessionReminderService._get_user_status(days_since_registration)
                }
                user_list.append(user_data)
            
            # Calculate pagination info
            has_prev = page > 1
            has_next = offset + per_page < total_count
            pages = (total_count + per_page - 1) // per_page  # Ceiling division
            prev_num = page - 1 if has_prev else None
            next_num = page + 1 if has_next else None
            
            return {
                'items': user_list,
                'page': page,
                'pages': pages,
                'per_page': per_page,
                'total': total_count,
                'has_prev': has_prev,
                'has_next': has_next,
                'prev_num': prev_num,
                'next_num': next_num
            }

    @staticmethod
    def _get_user_status(days_since_registration: int) -> str:
        """Get user status based on days since registration"""
        if days_since_registration <= 3:
            return "Baru Mendaftar"
        elif days_since_registration <= 7:
            return "Perlu Diingatkan"
        elif days_since_registration <= 30:
            return "Butuh Dorongan"
        else:
            return "Perlu Perhatian"

    @staticmethod
    def send_first_session_reminder(user_id: int) -> bool:
        """
        Send first session reminder email to a specific user
        
        Args:
            user_id: ID of the user to send reminder to
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            with get_session() as db:
                # Get user data
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    print(f"User with ID {user_id} not found")
                    return False
                
                if not user.email or not user.email_verified:
                    print(f"User {user_id} has no verified email")
                    return False
                
                # Check if user already has assessments
                has_assessments = db.query(AssessmentSession).filter(
                    AssessmentSession.user_id == user_id
                ).first() is not None
                
                if has_assessments:
                    print(f"User {user_id} already has assessments")
                    return False
                
                # Generate auto-login URL for seamless experience
                auto_login_url = AutoLoginService.generate_first_session_auto_login_url(
                    user_id=user.id,
                    redirect_to='/assessment/start'
                )
                
                # Prepare template data
                base_url = current_app.config.get('BASE_URL')
                template_data = {
                    'username': user.uname,
                    'hero_title': f'Siap Memulai Perjalanan Anda, {user.uname}?',
                    'auto_login_url': auto_login_url,
                    'base_url': base_url,
                    'assessment_url': auto_login_url  # Use auto-login URL instead of direct assessment URL
                }
                
                # Send email using SMTPService (copying exact pattern from session2)
                template_path = os.path.join(
                    os.path.dirname(__file__), 
                    'first_session_reminder_template.html'
                )
                
                subject = 'Waktunya Memulai - Asesmen Mental Health Menanti Anda!'
                
                success = SMTPService.send_template_email(
                    to_email=user.email,
                    subject=subject,
                    template_path=template_path,
                    template_data=template_data
                )
                
                if success:
                    print(f"First session reminder sent successfully to user {user_id} ({user.email})")
                    return True
                else:
                    print(f"Failed to send first session reminder to user {user_id}")
                    return False
                    
        except Exception as e:
            print(f"Error sending first session reminder to user {user_id}: {str(e)}")
            return False

    @staticmethod
    def send_bulk_first_session_reminders(user_ids: List[int]) -> Dict[str, Any]:
        """
        Send first session reminders to multiple users
        
        Args:
            user_ids: List of user IDs to send reminders to
            
        Returns:
            Dict with success/failure counts and details
        """
        results = {
            'total_attempted': len(user_ids),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for user_id in user_ids:
            try:
                success = FirstSessionReminderService.send_first_session_reminder(user_id)
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to send to user {user_id}")
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Error sending to user {user_id}: {str(e)}")
        
        return results

    @staticmethod 
    def send_batch_first_session_reminders(user_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Send first session reminders to multiple users (let Gunicorn handle threading)
        
        Args:
            user_ids: List of user IDs to send reminders to
            
        Returns:
            List of results for each user with success/failure status
        """
        print(f"[DEBUG] Starting batch reminders for {len(user_ids)} users using Gunicorn threading")
        
        results = []
        
        for user_id in user_ids:
            try:
                success = FirstSessionReminderService.send_first_session_reminder(user_id)
                results.append({
                    'user_id': user_id,
                    'success': success,
                    'error': None if success else f'Failed to send reminder to user {user_id}'
                })
            except Exception as e:
                results.append({
                    'user_id': user_id, 
                    'success': False,
                    'error': f'Error sending to user {user_id}: {str(e)}'
                })
        
        success_count = len([r for r in results if r['success']])
        print(f"[DEBUG] Batch reminders completed: {success_count}/{len(user_ids)} successful")
        
        return results

    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get statistics about users without assessments"""
        with get_session() as db:
            # Total users without assessments
            total_without_assessments = db.query(User).filter(
                and_(
                    User.email_verified == True,
                    User.email.isnot(None),
                    User.email != '',
                    not_(exists().where(AssessmentSession.user_id == User.id))
                )
            ).count()
            
            # Users by time since registration
            one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
            one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
            
            recent_registrations = db.query(User).filter(
                and_(
                    User.email_verified == True,
                    User.email.isnot(None),
                    User.email != '',
                    not_(exists().where(AssessmentSession.user_id == User.id)),
                    User.created_at >= one_day_ago
                )
            ).count()
            
            week_old_registrations = db.query(User).filter(
                and_(
                    User.email_verified == True,
                    User.email.isnot(None),
                    User.email != '',
                    not_(exists().where(AssessmentSession.user_id == User.id)),
                    User.created_at >= one_week_ago,
                    User.created_at < one_day_ago
                )
            ).count()
            
            month_old_registrations = db.query(User).filter(
                and_(
                    User.email_verified == True,
                    User.email.isnot(None),
                    User.email != '',
                    not_(exists().where(AssessmentSession.user_id == User.id)),
                    User.created_at >= one_month_ago,
                    User.created_at < one_week_ago
                )
            ).count()
            
            old_registrations = db.query(User).filter(
                and_(
                    User.email_verified == True,
                    User.email.isnot(None),
                    User.email != '',
                    not_(exists().where(AssessmentSession.user_id == User.id)),
                    User.created_at < one_month_ago
                )
            ).count()
            
            return {
                'total_without_assessments': total_without_assessments,
                'recent_registrations': recent_registrations,
                'week_old_registrations': week_old_registrations,
                'month_old_registrations': month_old_registrations,
                'old_registrations': old_registrations
            }