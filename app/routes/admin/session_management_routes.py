# app/routes/admin/session_management_routes.py
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from flask_login import current_user, login_required
from ...decorators import raw_response, admin_required
from ...services.SMTP.session2NotificationService import Session2NotificationService

session_management_bp = Blueprint('session_management', __name__, url_prefix='/admin/session-management')


@session_management_bp.route('/')
@login_required
@admin_required
def index():
    """Redirect to eligible users page"""
    return redirect(url_for('session_management.get_eligible_users'))


@session_management_bp.route('/eligible-users')
@login_required
@admin_required
@raw_response
def get_eligible_users():
    """Get users who completed Session 1 and are eligible for Session 2"""
    try:
        # Get all users with eligibility status
        all_users = Session2NotificationService.get_all_users_with_eligibility()
        
        # Get pending notifications count
        pending_count = Session2NotificationService.get_pending_notifications_count()
        
        return render_template('admin/session_management/eligible_users.html',
                             user=current_user,
                             all_users=all_users,
                             pending_count=pending_count)
    except Exception as e:
        current_app.logger.error(f"Error fetching eligible users: {str(e)}")
        return render_template('admin/session_management/eligible_users.html',
                             user=current_user,
                             all_users=[],
                             pending_count=0,
                             error="Failed to fetch eligible users")


@session_management_bp.route('/api/eligible-users')
@login_required
@admin_required
def api_get_eligible_users():
    """API endpoint to get users eligible for Session 2"""
    try:
        all_users = Session2NotificationService.get_all_users_with_eligibility()
        eligible_users = [user for user in all_users if user['is_eligible']]
        return jsonify({
            'status': 'success',
            'data': eligible_users
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@session_management_bp.route('/send-notification', methods=['POST'])
@login_required
@admin_required
def send_session2_notification():
    """Send Session 2 notification to a specific user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'User ID is required'
            }), 400
        
        # Send notification immediately
        success = Session2NotificationService.send_session2_notification(user_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Notification sent successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to send notification'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@session_management_bp.route('/pending-notifications')
@login_required
@admin_required
@raw_response
def get_pending_notifications():
    """Get all pending Session 2 notifications"""
    try:
        pending_notifications = Session2NotificationService.get_pending_notifications()
        return render_template('admin/session_management/pending_notifications.html',
                             user=current_user,
                             pending_notifications=pending_notifications)
    except Exception as e:
        current_app.logger.error(f"Error fetching pending notifications: {str(e)}")
        return render_template('admin/session_management/pending_notifications.html',
                             user=current_user,
                             pending_notifications=[],
                             error="Failed to fetch pending notifications")


@session_management_bp.route('/send-all-pending', methods=['POST'])
@login_required
@admin_required
def send_all_pending_notifications():
    """Send all pending Session 2 notifications"""
    try:
        # Send pending notifications
        sent_count = Session2NotificationService.send_pending_notifications()
        
        return jsonify({
            'status': 'success',
            'message': f'Berhasil mengirim {sent_count} notifikasi tertunda'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500