from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import and_
import os

from ...model.assessment.sessions import AssessmentSession, EmailNotification
from ...model.shared.users import User
from ...decorators import api_response
from ...db import get_session
from ..SMTP.smtpService import smtp_service
from ...config import Config


class EmailNotificationService:
    """Email Notification Service for CRUD operations following static pattern."""

    @staticmethod
    @api_response
    def create_session_completion_notifications(session_id: str) -> bool:
        """Create email notifications when a session is completed"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session or not session.is_completed:
                return False
            
            user = db.query(User).filter_by(id=session.user_id).first()
            if not user or not user.email:
                return False
            
            # 1. Create immediate completion notification
            completion_notification = EmailNotification.create_completion_notification(
                session_id=session.id,
                user_id=user.id,
                email_address=user.email
            )
            completion_notification.notification_data['session_number'] = session.session_number
            completion_notification.notification_data['user_name'] = user.uname
            
            db.add(completion_notification)
            
            # 2. Create 14-day followup reminder (only if this is session 1)
            if session.session_number == 1:
                followup_date = EmailNotificationService._calculate_followup_date(session.end_time)
                
                followup_notification = EmailNotification.create_followup_reminder(
                    session_id=session.id,
                    user_id=user.id,
                    email_address=user.email,
                    send_date=followup_date
                )
                followup_notification.notification_data['user_name'] = user.uname
                followup_notification.notification_data['session_1_completed_date'] = session.end_time.strftime('%d %B %Y')
                
                db.add(followup_notification)
            
            # Send immediate completion notification
            EmailNotificationService._send_immediate_notification(completion_notification.id)
            
            return True

    @staticmethod
    def _calculate_followup_date(completion_time: datetime) -> datetime:
        """Calculate 14 days + set to 00:00 UTC"""
        followup_date = completion_time + timedelta(days=14)
        return followup_date.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _send_immediate_notification(notification_id: str) -> bool:
        """Send immediate notification (completion email)"""
        with get_session() as db:
            notification = db.query(EmailNotification).filter_by(id=notification_id).first()
            if not notification:
                return False
            
            session = notification.session
            user = notification.user
            
            if notification.notification_type == 'SESSION_COMPLETED':
                success = EmailNotificationService._send_completion_email(notification, session, user)
            else:
                return False
            
            if success:
                notification.mark_sent()
                return True
            else:
                notification.mark_failed("SMTP sending failed")
                return False

    @staticmethod
    def _send_completion_email(notification: EmailNotification, session: AssessmentSession, user: User) -> bool:
        """Send session completion thank you email using template"""
        config = Config()
        session_display = f"Sesi {session.session_number}"
        completion_date = session.end_time.strftime('%d %B %Y, %H:%M')
        
        # Prepare template data for existing template.html
        template_data = {
            'user_name': user.uname,
            'hero_title': f'Terima Kasih, {user.uname}!',
            'message_intro': f'Terima kasih telah menyelesaikan {session_display} pada {completion_date}.',
            'session_label': session_display,
            'session_date': completion_date,
            'session_time': f'{session.duration_seconds // 60 if session.duration_seconds else "N/A"} menit',
            'join_url': config.LANDING_PAGE_URL,
            'reschedule_url': config.RESCHEDULE_URL,
            'cancel_url': config.CANCEL_URL,
            'brand_name': 'Mental Health Assessment',
            'support_email': config.EMAIL_FROM_ADDRESS,
            'primary_color': '#0F766E'
        }
        
        # If this is session 1, add reminder about session 2
        if session.session_number == 1:
            template_data['message_intro'] += ' Kami akan mengirimkan pengingat untuk Sesi 2 dalam 14 hari.'
        
        template_path = os.path.join(os.path.dirname(__file__), '..', 'SMTP', 'template.html')
        
        success = smtp_service.send_template_email(
            to_email=notification.email_address,
            subject=notification.subject,
            template_path=template_path,
            template_data=template_data
        )
        
        return success

    @staticmethod
    @api_response
    def process_scheduled_notifications() -> int:
        """Process all pending scheduled notifications (run by cron job)"""
        with get_session() as db:
            now = datetime.utcnow()
            
            pending_notifications = db.query(EmailNotification).filter(
                and_(
                    EmailNotification.status == 'PENDING',
                    EmailNotification.scheduled_send_at <= now
                )
            ).all()
            
            processed_count = 0
            
            for notification in pending_notifications:
                if notification.notification_type == 'FOLLOWUP_REMINDER':
                    success = EmailNotificationService._send_followup_reminder(notification)
                    if success:
                        processed_count += 1
                
            return processed_count

    @staticmethod
    def _send_followup_reminder(notification: EmailNotification) -> bool:
        """Send 14-day followup reminder email using template"""
        config = Config()
        session = notification.session
        user = notification.user
        
        user_name = notification.notification_data.get('user_name', user.uname)
        session_1_date = notification.notification_data.get('session_1_completed_date', 'beberapa waktu lalu')
        
        # Use existing template for followup reminder
        success = smtp_service.send_followup_email(
            to_email=notification.email_address,
            user_name=user_name,
            session_date="Segera dijadwalkan",
            session_time="Fleksibel sesuai kesediaan Anda",
            join_url=config.LANDING_PAGE_URL,
            reschedule_url=config.RESCHEDULE_URL,
            cancel_url=config.CANCEL_URL
        )
        
        if success:
            notification.mark_sent()
            return True
        else:
            notification.mark_failed("SMTP sending failed")
            return False

    @staticmethod
    @api_response
    def get_pending_notifications(limit: int = 100) -> List[EmailNotification]:
        """Get pending notifications for monitoring"""
        with get_session() as db:
            return db.query(EmailNotification).filter(
                EmailNotification.status == 'PENDING'
            ).order_by(EmailNotification.scheduled_send_at).limit(limit).all()

    @staticmethod
    @api_response
    def retry_failed_notifications() -> int:
        """Retry failed notifications that can be retried"""
        with get_session() as db:
            failed_notifications = db.query(EmailNotification).filter(
                EmailNotification.status == 'FAILED'
            ).all()
            
            retried_count = 0
            
            for notification in failed_notifications:
                if notification.can_retry():
                    notification.status = 'PENDING'
                    notification.updated_at = datetime.utcnow()
                    retried_count += 1
            
            return retried_count

    @staticmethod
    def test_smtp_connection() -> bool:
        """Test SMTP connection by sending a simple test"""
        try:
            from ..SMTP.smtpService import SMTPService
            SMTPService.send_html_email(
                to_email="wicaksonolxn@gmail.com",
                subject="SMTP Test",
                html_content="<p>SMTP connection test successful</p>"
            )
            return True
        except:
            return False