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
    """Send Session 2 notification to a specific user - DELETES old tokens and creates new ones"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'User ID is required'
            }), 400

        # Send notification immediately with force_new_token=True
        # This will DELETE old tokens from database and create fresh ones with correct BASE_URL
        success = Session2NotificationService.send_session2_notification(
            user_id,
            force_new_token=True
        )

        if success:
            return jsonify({
                'status': 'success',
                'message': 'Notification sent successfully (old tokens deleted, new token created)'
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


@session_management_bp.route('/send-to-all-eligible', methods=['POST'])
@login_required
@admin_required
def send_to_all_eligible_users():
    """Send Session 2 tokens to ALL eligible users (Memenuhi Syarat only) - BATCHED with delays"""
    try:
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Get all users with eligibility status (no pagination - returns pagination object)
        all_users_data = Session2NotificationService.get_all_users_with_eligibility()

        # Check if it's a pagination object with .items attribute or a plain list
        if hasattr(all_users_data, 'items'):
            all_users = all_users_data.items
        else:
            all_users = all_users_data

        # Filter to only "Memenuhi Syarat" users
        # is_eligible = True means: has_email + no_session_2 + days >= 14
        eligible_users = [
            user for user in all_users
            if user.get('is_eligible') and user.get('status') == 'Memenuhi Syarat'
        ]

        if not eligible_users:
            return jsonify({
                'status': 'error',
                'message': 'Tidak ada pengguna yang memenuhi syarat untuk menerima token'
            }), 400

        # Gmail SMTP rate limits: ~20 emails/hour max, 3-4 seconds between sends
        BATCH_SIZE = 10  # Send 10 emails per batch
        DELAY_BETWEEN_EMAILS = 3  # 3 seconds between each email (safe for Gmail)
        DELAY_BETWEEN_BATCHES = 30  # 30 seconds between batches (extra safety)

        # Helper function to send notification to a single user with delay
        def send_to_user(user, index):
            try:
                # Add delay based on index to spread out sends
                time.sleep(index * DELAY_BETWEEN_EMAILS)

                # Use force_new_token=True to invalidate old tokens and create fresh ones with correct BASE_URL
                success = Session2NotificationService.send_session2_notification(
                    user['user_id'],
                    force_new_token=True
                )
                if success:
                    current_app.logger.info(f"✓ Sent token to {user['username']} (ID: {user['user_id']})")
                    return {'success': True, 'user': user}
                else:
                    return {
                        'success': False,
                        'user': user,
                        'reason': 'Send failed'
                    }
            except Exception as e:
                current_app.logger.error(f"✗ Failed to send to {user['username']}: {str(e)}")
                return {
                    'success': False,
                    'user': user,
                    'reason': str(e)
                }

        # Send notifications in BATCHES to avoid Gmail rate limits
        sent_count = 0
        failed_count = 0
        failed_users = []

        # Split eligible users into batches
        total_batches = (len(eligible_users) + BATCH_SIZE - 1) // BATCH_SIZE
        current_app.logger.info(f"Sending to {len(eligible_users)} users in {total_batches} batches of {BATCH_SIZE}")

        for batch_num in range(total_batches):
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(eligible_users))
            batch_users = eligible_users[start_idx:end_idx]

            current_app.logger.info(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_users)} users)")

            # Process batch with limited concurrency (max 3 parallel to be safe)
            max_workers = min(3, len(batch_users))

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks in this batch with staggered delays
                future_to_user = {
                    executor.submit(send_to_user, user, idx): user
                    for idx, user in enumerate(batch_users)
                }

                # Collect results as they complete
                for future in as_completed(future_to_user):
                    result = future.result()

                    if result['success']:
                        sent_count += 1
                    else:
                        failed_count += 1
                        failed_users.append({
                            'user_id': result['user']['user_id'],
                            'username': result['user']['username'],
                            'reason': result['reason']
                        })

            # Delay between batches (except after last batch)
            if batch_num < total_batches - 1:
                current_app.logger.info(f"Waiting {DELAY_BETWEEN_BATCHES}s before next batch...")
                time.sleep(DELAY_BETWEEN_BATCHES)

        response = {
            'status': 'success',
            'message': f'Berhasil mengirim token ke {sent_count} dari {len(eligible_users)} pengguna yang memenuhi syarat',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total_eligible': len(eligible_users)
        }

        if failed_users:
            response['failed_users'] = failed_users

        return jsonify(response)

    except Exception as e:
        current_app.logger.error(f"Error sending to all eligible users: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Gagal mengirim token: {str(e)}'
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
        # Get pagination, search, and sort parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        search_query = request.args.get('q', '').strip()
        sort_by = request.args.get('sort_by', 'scheduled_date')
        sort_order = request.args.get('sort_order', 'desc')

        # Limit per_page options
        if per_page not in [10, 15, 20]:
            per_page = 15

        # Validate sort_by options
        if sort_by not in ['user_id', 'username', 'session_end', 'scheduled_date', 'created_at']:
            sort_by = 'scheduled_date'

        # Validate sort_order options
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'

        # Get pending notifications with user details (paginated with search and sort)
        pending_notifications_page = Session2NotificationService.get_pending_notifications_with_users(
            page=page,
            per_page=per_page,
            search_query=search_query,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
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
            'search_query': search_query,
            'sort_by': sort_by,
            'sort_order': sort_order
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

