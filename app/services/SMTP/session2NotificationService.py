# app/services/SMTP/session2NotificationService.py
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import and_, or_, func
from ...model.shared.users import User
from ...model.assessment.sessions import AssessmentSession, EmailNotification
from ...db import get_session
from .emailNotificationService import EmailNotificationService
from ...config import Config
from ..shared.autoLoginService import AutoLoginService


class Session2NotificationService:
    """Service for handling Session 2 notifications"""
    
    @staticmethod
    def get_all_users_with_eligibility(page=None, per_page=None):
        """
        Get ALL users with Session 1 and their Session 2 eligibility status
        Returns all users who completed Session 1, with status indicating if they're eligible for Session 2
        """
        with get_session() as db:
            # Create aliases for clarity
            from sqlalchemy.orm import aliased
            Session1 = aliased(AssessmentSession)
            Session2 = aliased(AssessmentSession)
            
            # Build query for users who completed Session 1
            query = db.query(
                User.id,
                User.uname,
                User.email,
                User.phone,
                Session1.end_time.label('session_1_end_time'),
                Session2.id.label('session_2_id')
            ).join(
                Session1,
                and_(
                    Session1.user_id == User.id,
                    Session1.session_number == 1,
                    Session1.is_completed == True
                )
            ).outerjoin(
                Session2,
                and_(
                    Session2.user_id == User.id,
                    Session2.session_number == 2
                )
            ).order_by(Session1.end_time.desc())
            
            # If pagination requested, implement manual pagination
            if page and per_page:
                # Get total count and paginated results
                total_users = query.count()
                offset = (page - 1) * per_page
                all_users = query.offset(offset).limit(per_page).all()
                
                # Calculate pagination info
                has_prev = page > 1
                has_next = offset + per_page < total_users
                pages = (total_users + per_page - 1) // per_page  # Ceiling division
                prev_num = page - 1 if has_prev else None
                next_num = page + 1 if has_next else None
            else:
                all_users = query.all()
                # Set default pagination values for non-paginated case
                total_users = len(all_users)
                has_prev = False
                has_next = False
                pages = 1
                prev_num = None
                next_num = None
                page = 1
                per_page = total_users
            
            # Process results to add calculated fields and eligibility status
            result = []
            for user in all_users:
                if user.session_1_end_time:
                    days_since = (datetime.utcnow() - user.session_1_end_time).days
                    
                    # Determine eligibility status
                    has_email = user.email is not None
                    has_no_session_2 = user.session_2_id is None
                    days_criteria = days_since >= 14
                    
                    # User is eligible if: has email + no Session 2 + 14+ days
                    is_eligible = has_email and has_no_session_2 and days_criteria
                    
                    # Determine status message
                    if not has_email:
                        status = "Tidak Ada Email"
                    elif user.session_2_id is not None:
                        status = "Sudah Sesi 2"
                    elif days_since < 14:
                        status = f"Tunggu {14 - days_since} Hari Lagi"
                    else:
                        status = "Memenuhi Syarat"
                    
                    result.append({
                        'user_id': user.id,
                        'username': user.uname,
                        'email': user.email or 'Tidak ada email',
                        'phone': user.phone,
                        'session_1_completion_date': user.session_1_end_time.strftime('%d %B %Y'),
                        'days_since_session_1': days_since,
                        'session_1_end_time': user.session_1_end_time.isoformat(),
                        'is_eligible': is_eligible,
                        'status': status,
                        'has_session_2': user.session_2_id is not None
                    })
            
            # Return data with pagination info if requested
            if page and per_page:
                # Create pagination object manually
                from collections import namedtuple
                PageObj = namedtuple('PageObj', ['items', 'page', 'pages', 'per_page', 'total', 'has_prev', 'has_next', 'prev_num', 'next_num'])
                page_obj = PageObj(
                    items=result,
                    page=page,
                    pages=pages,
                    per_page=per_page,
                    total=total_users,
                    has_prev=has_prev,
                    has_next=has_next,
                    prev_num=prev_num,
                    next_num=next_num
                )
                return page_obj
            else:
                return result
    
    
    @staticmethod
    def _calculate_followup_date(completion_time: datetime) -> datetime:
        """Calculate 14 days + set to 00:00 UTC+7"""
        # Add 14 days to completion time
        followup_date = completion_time + timedelta(days=14)
        # Set to 00:00 (midnight) in UTC+7
        # Since we store times in UTC, 00:00 UTC+7 is 17:00 UTC the previous day
        # We need to subtract 7 hours to convert from UTC+7 midnight to UTC time
        followup_date = followup_date.replace(hour=17, minute=0, second=0, microsecond=0)
        return followup_date

    @staticmethod
    def create_automatic_notifications() -> int:
        """
        Create Session 2 notifications for eligible users (14-day trigger)
        Returns the number of notifications created
        """
        all_users = Session2NotificationService.get_all_users_with_eligibility()
        eligible_users = [user for user in all_users if user['is_eligible']]
        created_count = 0
        
        with get_session() as db:
            for user_data in eligible_users:
                # Check if notification already exists for this user
                existing_notification = db.query(EmailNotification).filter(
                    and_(
                        EmailNotification.user_id == user_data['user_id'],
                        EmailNotification.notification_type == 'SESSION_2_CONTINUATION',
                        EmailNotification.status == 'PENDING'
                    )
                ).first()
                
                if not existing_notification:
                    # Get the Session 1 record
                    session1 = db.query(AssessmentSession).filter(
                        and_(
                            AssessmentSession.user_id == user_data['user_id'],
                            AssessmentSession.session_number == 1,
                            AssessmentSession.is_completed == True
                        )
                    ).first()
                    
                    if session1:
                        # Calculate the correct scheduled send time (14 days + 00:00 UTC)
                        scheduled_send_at = Session2NotificationService._calculate_followup_date(
                            session1.end_time
                        )
                        
                        # Check if user already has valid auto-login token for Session 2
                        from ...model.shared.auto_login_tokens import AutoLoginToken
                        existing_token = db.query(AutoLoginToken).filter(
                            and_(
                                AutoLoginToken.user_id == user_data['user_id'],
                                AutoLoginToken.purpose == 'auto_login_session2',
                                AutoLoginToken.used == False,
                                AutoLoginToken.expires_at > datetime.utcnow()
                            )
                        ).first()
                        
                        if existing_token:
                            print(f"User {user_data['user_id']} already has valid Session 2 auto-login token. Skipping automatic notification creation.")
                            continue  # Skip this user
                        
                        # Generate auto-login URL for Session 2 - NO FALLBACKS
                        from flask import current_app
                        with current_app.app_context():
                            auto_login_url = AutoLoginService.generate_session2_auto_login_url(user_data['user_id'])
                            session_2_url = Config.BASE_URL
                        
                        # Create notification with proper scheduled time
                        notification = EmailNotification(
                            session_id=session1.id,
                            user_id=user_data['user_id'],
                            email_address=user_data['email'],
                            notification_type='SESSION_2_CONTINUATION',
                            subject='Waktunya Melanjutkan Perjalanan Anda - Sesi 2 Menanti!',
                            template_used='session2_template',
                            scheduled_send_at=scheduled_send_at,
                            notification_data={
                                'username': user_data['username'],
                                'session_1_completion_date': user_data['session_1_completion_date'],
                                'days_since_session_1': user_data['days_since_session_1'],
                                'user_email': user_data['email'],
                                'user_phone': user_data['phone'] if user_data['phone'] else '',
                                'auto_login_url': auto_login_url,
                                'session_2_url': session_2_url,
                                'base_url': Config.BASE_URL
                            }
                        )
                        
                        db.add(notification)
                        created_count += 1
            
            db.commit()
            
        return created_count
    
    @staticmethod
    def send_session2_notification(user_id: int) -> bool:
        """
        Send Session 2 notification to specific user using real data
        This can be used for both automatic and manual sending
        """
        with get_session() as db:
            # Get user data
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.email:
                return False
            
            # Get Session 1 data
            session1 = db.query(AssessmentSession).filter(
                and_(
                    AssessmentSession.user_id == user_id,
                    AssessmentSession.session_number == 1,
                    AssessmentSession.is_completed == True
                )
            ).first()
            
            if not session1:
                return False
            
            # Calculate days since Session 1
            days_since = (datetime.utcnow() - session1.end_time).days
            
            # Check if user already has valid auto-login token for Session 2
            from ...model.shared.auto_login_tokens import AutoLoginToken
            existing_token = db.query(AutoLoginToken).filter(
                and_(
                    AutoLoginToken.user_id == user_id,
                    AutoLoginToken.purpose == 'auto_login_session2',
                    AutoLoginToken.used == False,
                    AutoLoginToken.expires_at > datetime.utcnow()
                )
            ).first()
            
            # Generate auto-login URL for Session 2 - NO FALLBACKS
            from flask import current_app
            with current_app.app_context():
                if existing_token:
                    print(f"User {user_id} has valid Session 2 token. Reusing existing token for email.")
                    # Regenerate JWT with same JTI to reuse the database record
                    import jwt
                    payload = {
                        'user_id': user_id,
                        'username': user.uname,
                        'purpose': 'auto_login_session2',
                        'redirect_to': '/',
                        'single_use': True,
                        'jti': existing_token.token_jti,  # Use existing JTI
                        'exp': existing_token.expires_at,
                        'iat': existing_token.created_at,
                        'iss': 'mental-health-app-autologin'
                    }
                    secret = current_app.config['SECRET_KEY']
                    jwt_token = jwt.encode(payload, secret, algorithm='HS256')
                    auto_login_url = f"{Config.BASE_URL.rstrip('/')}/auth/auto-login?token={jwt_token}"
                else:
                    # Generate new token as usual
                    auto_login_url = AutoLoginService.generate_session2_auto_login_url(user_id)
                session_2_url = Config.BASE_URL
            
            # Create notification data
            notification_data = {
                'username': user.uname,
                'session_1_completion_date': session1.end_time.strftime('%d %B %Y'),
                'days_since_session_1': str(days_since),
                'user_email': user.email,
                'user_phone': user.phone if user.phone else '',
                'auto_login_url': auto_login_url,
                'session_2_url': session_2_url,
                'base_url': Config.BASE_URL
            }
            
            # Create immediate notification
            notification = EmailNotification(
                session_id=session1.id,
                user_id=user_id,
                email_address=user.email,
                notification_type='SESSION_2_CONTINUATION',
                subject='Waktunya Melanjutkan Perjalanan Anda - Sesi 2 Menanti!',
                template_used='session2_template',
                scheduled_send_at=datetime.utcnow(),  # Send immediately
                notification_data=notification_data
            )
            
            db.add(notification)
            db.commit()
            
            # Send the notification immediately
            success = EmailNotificationService._send_session2_continuation_email(
                notification, session1, user
            )
            
            if success:
                notification.mark_sent()
                db.commit()
                return True
            else:
                notification.mark_failed("SMTP sending failed")
                db.commit()
                return False
    
    @staticmethod
    def get_pending_notifications() -> List[Dict[str, Any]]:
        """Get all pending Session 2 notifications"""
        with get_session() as db:
            pending_notifications = db.query(EmailNotification).filter(
                and_(
                    EmailNotification.notification_type == 'SESSION_2_CONTINUATION',
                    EmailNotification.status == 'PENDING'
                )
            ).order_by(EmailNotification.scheduled_send_at.asc()).all()
            
            result = []
            for notification in pending_notifications:
                result.append({
                    'id': notification.id,
                    'user_id': notification.user_id,
                    'email_address': notification.email_address,
                    'scheduled_send_at': notification.scheduled_send_at.strftime('%d %B %Y, %H:%M'),
                    'created_at': notification.created_at.strftime('%d %B %Y, %H:%M'),
                    'username': notification.notification_data.get('username', 'Unknown') if notification.notification_data else 'Unknown'
                })
            
            return result
    
    @staticmethod
    def get_pending_notifications_count() -> int:
        """Get count of pending Session 2 notifications"""
        with get_session() as db:
            count = db.query(EmailNotification).filter(
                and_(
                    EmailNotification.notification_type == 'SESSION_2_CONTINUATION',
                    EmailNotification.status == 'PENDING'
                )
            ).count()
            
            return count
    
    @staticmethod
    def send_pending_notifications() -> int:
        """Send all pending Session 2 notifications"""
        with get_session() as db:
            pending_notifications = db.query(EmailNotification).filter(
                and_(
                    EmailNotification.notification_type == 'SESSION_2_CONTINUATION',
                    EmailNotification.status == 'PENDING',
                    EmailNotification.scheduled_send_at <= datetime.utcnow()
                )
            ).all()
            
            sent_count = 0
            
            for notification in pending_notifications:
                session = notification.session
                user = notification.user
                
                success = EmailNotificationService._send_session2_continuation_email(
                    notification, session, user
                )
                
                if success:
                    notification.mark_sent()
                    sent_count += 1
                else:
                    notification.mark_failed("SMTP sending failed")
            
            db.commit()
            
            return sent_count
    
    @staticmethod
    def get_user_session2_data(user_id: int) -> Dict[str, Any]:
        """Get user's Session 2 notification data"""
        with get_session() as db:
            # Get user data
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}
            
            # Get Session 1 data
            session1 = db.query(AssessmentSession).filter(
                and_(
                    AssessmentSession.user_id == user_id,
                    AssessmentSession.session_number == 1,
                    AssessmentSession.is_completed == True
                )
            ).first()
            
            if not session1:
                return {}
            
            # Calculate days since Session 1
            days_since = (datetime.utcnow() - session1.end_time).days
            
            return {
                'username': user.uname,
                'email': user.email,
                'phone': user.phone if user.phone else '',
                'session_1_date': session1.end_time.strftime('%d %B %Y'),
                'days_since': days_since
            }