# app/routes/admin/session_management_routes.py
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from flask_login import current_user, login_required
from ...decorators import raw_response, admin_required, api_response
from ...services.SMTP.session2NotificationService import Session2NotificationService
from ...services.SMTP.firstSessionReminderService import FirstSessionReminderService

session_management_bp = Blueprint('session_management', __name__, url_prefix='/admin/session-management')


@session_management_bp.route('/')
@login_required
@admin_required
@raw_response
def index():
    """Session management main page with AJAX loading"""
    return render_template('admin/session_management/index.html', user=current_user)


@session_management_bp.route('/ajax-eligible-users')
@login_required
@admin_required
@api_response
def get_eligible_users():
    """AJAX endpoint for users eligible for Session 2"""
    from flask import request

    try:
        # Get pagination, search, and sort parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        search_query = request.args.get('q', '').strip()
        completion_filter = request.args.get('complete')  # 'true', 'false', or None
        sort_by = request.args.get('sort_by', 'session_end')  # Default: session end date
        sort_order = request.args.get('sort_order', 'desc')  # Default: descending

        # Convert completion filter to service format
        if completion_filter == 'true':
            completion_filter = 'complete'
        elif completion_filter == 'false':
            completion_filter = 'incomplete'
        else:
            completion_filter = None

        # Validate sort_by options
        if sort_by not in ['user_id', 'username', 'session_end', 'eligibility', 'created_at']:
            sort_by = 'session_end'

        # Validate sort_order options
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'

        current_app.logger.info(f"Search request: q='{search_query}', page={page}, per_page={per_page}, completion_filter={completion_filter}, sort_by={sort_by}, sort_order={sort_order}")

        # Limit per_page options
        if per_page not in [10, 15, 20]:
            per_page = 15

        # Get all users with eligibility status (paginated with search, completion filter, and sorting)
        all_users_page = Session2NotificationService.get_all_users_with_eligibility(
            page=page,
            per_page=per_page,
            search_query=search_query,
            completion_filter=completion_filter,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Get pending notifications count
        pending_count = Session2NotificationService.get_pending_notifications_count()
        
        result = {
            'items': all_users_page.items,
            'pagination': {
                'page': all_users_page.page,
                'pages': all_users_page.pages,
                'per_page': all_users_page.per_page,
                'total': all_users_page.total,
                'has_prev': all_users_page.has_prev,
                'has_next': all_users_page.has_next,
                'prev_num': all_users_page.prev_num,
                'next_num': all_users_page.next_num
            },
            'stats': {
                'pending_count': pending_count,
                'eligible_count': len([u for u in all_users_page.items if u.get('is_eligible')])
            },
            'search_query': search_query,
            'sort_by': sort_by,
            'sort_order': sort_order
        }

        return result
        
    except Exception as e:
        error_msg = f'Gagal memuat data pengguna yang memenuhi syarat: {str(e)}'
        current_app.logger.error(f"Error in get_eligible_users: {str(e)}")
        print(f"[ERROR] Eligible Users AJAX failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': error_msg}, 500


@session_management_bp.route('/api/eligible-users')
@login_required
@admin_required
def api_get_eligible_users():
    """API endpoint to get users eligible for Session 2"""
    try:
        completion_filter = request.args.get('complete')  # 'true', 'false', or None
        
        # Convert completion filter to service format
        if completion_filter == 'true':
            completion_filter = 'complete'
        elif completion_filter == 'false':
            completion_filter = 'incomplete'
        else:
            completion_filter = None
            
        all_users = Session2NotificationService.get_all_users_with_eligibility(completion_filter=completion_filter)
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


# ========== FIRST SESSION REMINDER ROUTES ==========

@session_management_bp.route('/ajax-unstarted-users')
@login_required
@admin_required
@api_response
def get_unstarted_users():
    """AJAX endpoint for users who haven't started assessments"""
    from flask import request
    
    try:
        # Get pagination and search parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        search_query = request.args.get('q', '').strip()
        
        # Limit per_page options
        if per_page not in [10, 15, 20]:
            per_page = 15
        
        # Get users without assessments (paginated with search)
        unstarted_users_page = FirstSessionReminderService.get_users_without_assessments(page=page, per_page=per_page, search_query=search_query)
        
        # Get statistics
        stats = FirstSessionReminderService.get_statistics()
        
        # Return data in same format as dashboard (without manual jsonify)
        return {
            'items': unstarted_users_page['items'],
            'pagination': {
                'page': unstarted_users_page['page'],
                'pages': unstarted_users_page['pages'],
                'per_page': unstarted_users_page['per_page'],
                'total': unstarted_users_page['total'],
                'has_prev': unstarted_users_page['has_prev'],
                'has_next': unstarted_users_page['has_next'],
                'prev_num': unstarted_users_page['prev_num'],
                'next_num': unstarted_users_page['next_num']
            },
            'stats': stats,
            'search_query': search_query
        }
    except Exception as e:
        current_app.logger.error(f"Error in get_unstarted_users: {str(e)}")
        print(f"[ERROR] Unstarted Users AJAX failed: {str(e)}")
        return {'error': f'Gagal memuat data pengguna belum mulai: {str(e)}'}, 500


# ========== PENDING NOTIFICATIONS ROUTES ==========

@session_management_bp.route('/ajax-pending-notifications')
@login_required
@admin_required
@api_response
def get_pending_notifications_ajax():
    """AJAX endpoint for pending Session 2 notifications"""
    from flask import request
    
    try:
        # Get pagination and search parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        search_query = request.args.get('q', '').strip()
        
        # Limit per_page options
        if per_page not in [10, 15, 20]:
            per_page = 15
        
        # Get pending notifications with user details (paginated with search)
        pending_notifications_page = Session2NotificationService.get_pending_notifications_with_users(page=page, per_page=per_page, search_query=search_query)
        
        # Get total pending count for stats
        total_pending_count = Session2NotificationService.get_pending_notifications_count()
        
        # Return data in same format as dashboard (without manual jsonify)
        return {
            'items': pending_notifications_page.items,
            'pagination': {
                'page': pending_notifications_page.page,
                'pages': pending_notifications_page.pages,
                'per_page': pending_notifications_page.per_page,
                'total': pending_notifications_page.total,
                'has_prev': pending_notifications_page.has_prev,
                'has_next': pending_notifications_page.has_next,
                'prev_num': pending_notifications_page.prev_num,
                'next_num': pending_notifications_page.next_num
            },
            'stats': {
                'total_pending': total_pending_count,
                'shown_pending': len(pending_notifications_page.items)
            },
            'search_query': search_query
        }
    except Exception as e:
        current_app.logger.error(f"Error in get_pending_notifications: {str(e)}")
        print(f"[ERROR] Pending Notifications AJAX failed: {str(e)}")
        return {'error': f'Gagal memuat notifikasi tertunda: {str(e)}'}, 500


@session_management_bp.route('/send-first-session-reminder', methods=['POST'])
@login_required
@admin_required
def send_first_session_reminder():
    """Send first session reminder email to a specific user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'User ID is required'
            }), 400
        
        # Send reminder email immediately
        success = FirstSessionReminderService.send_first_session_reminder(user_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Reminder email sent successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to send reminder email'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@session_management_bp.route('/send-batch-first-session-reminders', methods=['POST'])
@login_required
@admin_required
@api_response
def send_batch_first_session_reminders():
    """Send first session reminder emails to multiple users asynchronously"""
    try:
        data = request.get_json()
        user_ids = data.get('user_ids', [])
        
        if not user_ids:
            return {'error': 'User IDs are required'}, 400
        
        # Send batch reminders asynchronously
        results = FirstSessionReminderService.send_batch_first_session_reminders(user_ids)
        
        success_count = len([r for r in results if r['success']])
        failed_count = len(results) - success_count
        
        return {
            'total_requested': len(user_ids),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results,
            'message': f'Batch reminder completed: {success_count} sent, {failed_count} failed'
        }
        
    except Exception as e:
        error_msg = f'Failed to send batch reminders: {str(e)}'
        current_app.logger.error(error_msg)
        print(f"[ERROR] Batch reminders failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': error_msg}, 500


@session_management_bp.route('/send-all-unstarted-reminders', methods=['POST'])
@login_required
@admin_required
@api_response
def send_all_unstarted_reminders():
    """Send first session reminder emails to ALL unstarted users"""
    try:
        # Get all unstarted users
        unstarted_data = FirstSessionReminderService.get_users_without_assessments()
        user_ids = [user['user_id'] for user in unstarted_data['items']]
        
        if not user_ids:
            return {
                'total_requested': 0,
                'success_count': 0,
                'failed_count': 0,
                'message': 'No unstarted users found'
            }
        
        print(f"[DEBUG] Sending reminders to all {len(user_ids)} unstarted users")
        # Send batch reminders asynchronously
        results = FirstSessionReminderService.send_batch_first_session_reminders(user_ids)
        
        success_count = len([r for r in results if r['success']])
        failed_count = len(results) - success_count
        
        return {
            'total_requested': len(user_ids),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results,
            'message': f'Sent reminders to all unstarted users: {success_count} sent, {failed_count} failed'
        }
        
    except Exception as e:
        error_msg = f'Failed to send all reminders: {str(e)}'
        current_app.logger.error(error_msg)
        print(f"[ERROR] Send all reminders failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': error_msg}, 500


@session_management_bp.route('/api/unstarted-users')
@login_required
@admin_required
def api_get_unstarted_users():
    """API endpoint to get users who haven't started assessments"""
    try:
        unstarted_users = FirstSessionReminderService.get_users_without_assessments()
        return jsonify({
            'status': 'success',
            'data': unstarted_users['items']
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

