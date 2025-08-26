# app/services/admin/adminService.py
from typing import List, Optional, Dict, Any
from sqlalchemy import and_, or_
from ...decorators import api_response
from ...model.admin import SystemSetting, AssessmentConfig, MediaSetting, AdminLog, QuestionPool
from ...db import get_session


class AdminService:
    """Admin service for system settings and configuration management"""

    @staticmethod
    @api_response
    def get_system_settings(category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all system settings, optionally filtered by category"""
        with get_session() as db:
            query = db.query(SystemSetting).filter(SystemSetting.is_active == True)

            if category:
                query = query.filter(SystemSetting.category == category)

            settings = query.order_by(SystemSetting.category, SystemSetting.key).all()

            return [{
                'id': setting.id,
                'key': setting.key,
                'value': setting.value,
                'parsed_value': setting.parsed_value,
                'data_type': setting.data_type,
                'category': setting.category,
                'description': setting.description,
                'is_editable': setting.is_editable,
                'requires_restart': setting.requires_restart
            } for setting in settings]

    @staticmethod
    @api_response
    def update_system_setting(key: str, value: str, admin_user: str) -> Dict[str, Any]:
        """Update a system setting value"""
        setting = AdminService._get_db().query(SystemSetting).filter(
            and_(SystemSetting.key == key, SystemSetting.is_active == True)
        ).first()

        if not setting:
            raise ValueError(f"System setting '{key}' not found")

        if not setting.is_editable:
            raise ValueError(f"System setting '{key}' is not editable")

        old_value = setting.value
        setting.value = value

        # Log the change
        AdminService._log_action(
            admin_user=admin_user,
            action='UPDATE_SETTING',
            target_type='SYSTEM_SETTING',
            target_id=key,
            details={'old_value': old_value, 'new_value': value}
        )

        AdminService._get_db().commit()

        return {
            'key': setting.key,
            'old_value': old_value,
            'new_value': setting.value,
            'parsed_value': setting.parsed_value,
            'requires_restart': setting.requires_restart
        }

    @staticmethod
    @api_response
    def create_system_setting(key: str, value: str, data_type: str, category: str,
                              description: str, admin_user: str) -> Dict[str, Any]:
        """Create a new system setting"""
        existing = AdminService._get_db().query(SystemSetting).filter(SystemSetting.key == key).first()
        if existing:
            raise ValueError(f"System setting '{key}' already exists")

        setting = SystemSetting(
            key=key,
            value=value,
            data_type=data_type,
            category=category,
            description=description
        )

        AdminService._get_db().add(setting)

        AdminService._log_action(
            admin_user=admin_user,
            action='CREATE_SETTING',
            target_type='SYSTEM_SETTING',
            target_id=key,
            details={'value': value, 'data_type': data_type, 'category': category}
        )

        AdminService._get_db().commit()

        return {
            'id': setting.id,
            'key': setting.key,
            'value': setting.value,
            'data_type': setting.data_type,
            'category': setting.category
        }

    @staticmethod
    @api_response
    def get_assessment_configs(assessment_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get assessment configurations"""
        query = AdminService._get_db().query(AssessmentConfig).filter(AssessmentConfig.is_active == True)

        if assessment_type:
            query = query.filter(AssessmentConfig.assessment_type == assessment_type)

        configs = query.order_by(AssessmentConfig.assessment_type, AssessmentConfig.config_name).all()

        return [{
            'id': config.id,
            'config_name': config.config_name,
            'assessment_type': config.assessment_type,
            'config_data': config.config_data,
            'version': config.version,
            'description': config.description,
            'is_default': config.is_default,
            'created_by_admin': config.created_by_admin
        } for config in configs]

    @staticmethod
    @api_response
    def create_assessment_config(config_name: str, assessment_type: str, config_data: Dict[str, Any],
                                 description: str, admin_user: str) -> Dict[str, Any]:
        """Create new assessment configuration"""
        existing = AdminService._get_db().query(AssessmentConfig).filter(
            AssessmentConfig.config_name == config_name
        ).first()
        if existing:
            raise ValueError(f"Assessment config '{config_name}' already exists")

        config = AssessmentConfig(
            config_name=config_name,
            assessment_type=assessment_type,
            config_data=config_data,
            description=description,
            created_by_admin=admin_user
        )

        AdminService._get_db().add(config)

        AdminService._log_action(
            admin_user=admin_user,
            action='CREATE_ASSESSMENT_CONFIG',
            target_type='ASSESSMENT_CONFIG',
            target_id=config_name,
            details={'assessment_type': assessment_type}
        )

        AdminService._get_db().commit()

        return {
            'id': config.id,
            'config_name': config.config_name,
            'assessment_type': config.assessment_type,
            'config_data': config.config_data
        }

    @staticmethod
    @api_response
    def get_media_settings(media_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get media settings"""
        query = AdminService._get_db().query(MediaSetting).filter(MediaSetting.is_active == True)

        if media_type:
            query = query.filter(MediaSetting.media_type == media_type)

        settings = query.order_by(MediaSetting.media_type, MediaSetting.setting_name).all()

        return [{
            'id': setting.id,
            'setting_name': setting.setting_name,
            'media_type': setting.media_type,
            'max_file_size_mb': setting.max_file_size_mb,
            'allowed_formats': setting.allowed_formats,
            'camera_settings': setting.camera_settings,
            'auto_process': setting.auto_process,
            'processing_timeout_seconds': setting.processing_timeout_seconds,
            'storage_path': setting.storage_path,
            'retention_days': setting.retention_days
        } for setting in settings]

    @staticmethod
    @api_response
    def update_media_setting(setting_id: int, updates: Dict[str, Any], admin_user: str) -> Dict[str, Any]:
        """Update media setting"""
        setting = AdminService._get_db().query(MediaSetting).filter(
            and_(MediaSetting.id == setting_id, MediaSetting.is_active == True)
        ).first()

        if not setting:
            raise ValueError(f"Media setting with ID {setting_id} not found")

        old_values = {}
        for key, value in updates.items():
            if hasattr(setting, key):
                old_values[key] = getattr(setting, key)
                setattr(setting, key, value)

        AdminService._log_action(
            admin_user=admin_user,
            action='UPDATE_MEDIA_SETTING',
            target_type='MEDIA_SETTING',
            target_id=str(setting_id),
            details={'updates': updates, 'old_values': old_values}
        )

        AdminService._get_db().commit()

        return {
            'id': setting.id,
            'setting_name': setting.setting_name,
            'updated_fields': list(updates.keys())
        }

    @staticmethod
    @api_response
    def get_question_pools(question_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get question pools"""
        query = AdminService._get_db().query(QuestionPool).filter(QuestionPool.is_active == True)

        if question_type:
            query = query.filter(QuestionPool.question_type == question_type)

        pools = query.order_by(QuestionPool.question_type, QuestionPool.pool_name).all()

        return [{
            'id': pool.id,
            'pool_name': pool.pool_name,
            'question_type': pool.question_type,
            'language': pool.language,
            'question_count': pool.question_count,
            'questions': pool.questions,
            'metadata': pool.metadata,
            'is_default': pool.is_default,
            'randomize_order': pool.randomize_order
        } for pool in pools]

    @staticmethod
    @api_response
    def get_admin_logs(limit: int = 100, admin_user: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get admin action logs"""
        query = AdminService._get_db().query(AdminLog)

        if admin_user:
            query = query.filter(AdminLog.admin_user == admin_user)

        logs = query.order_by(AdminLog.created_at.desc()).limit(limit).all()

        return [{
            'id': log.id,
            'admin_user': log.admin_user,
            'action': log.action,
            'target_type': log.target_type,
            'target_id': log.target_id,
            'details': log.details,
            'created_at': log.created_at,
            'ip_address': log.ip_address
        } for log in logs]

    @staticmethod
    def _log_action(admin_user: str, action: str, target_type: str, target_id: str = None,
                    details: Dict[str, Any] = None, ip_address: str = None):
        """Internal method to log admin actions"""
        with get_session() as db:
            log = AdminLog(
                admin_user=admin_user,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
                ip_address=ip_address
            )
            db.add(log)

    @staticmethod
    @api_response
    def get_system_stats() -> Dict[str, Any]:
        """Get system statistics for admin dashboard"""
        from ...model.shared import User
        from ...model.assessment import AssessmentSession, Assessment

        # User statistics
        total_users = AdminService._get_db().query(User).filter(User.is_active == True).count()
        admin_users = AdminService._get_db().query(User).join(User.user_type).filter(
            and_(User.is_active == True, User.user_type.has(name='admin'))
        ).count()

        # Assessment statistics
        total_assessments = AdminService._get_db().query(Assessment).filter(Assessment.is_active == True).count()
        total_sessions = AdminService._get_db().query(AssessmentSession).count()
        completed_sessions = AdminService._get_db().query(AssessmentSession).filter(
            AssessmentSession.status == 'COMPLETED'
        ).count()

        return {
            'users': {
                'total': total_users,
                'admins': admin_users,
                'regular': total_users - admin_users
            },
            'assessments': {
                'total_types': total_assessments,
                'total_sessions': total_sessions,
                'completed_sessions': completed_sessions,
                'completion_rate': round((completed_sessions / total_sessions * 100), 2) if total_sessions > 0 else 0
            },
            'settings': {
                'total_settings': AdminService._get_db().query(SystemSetting).filter(SystemSetting.is_active == True).count(),
                'assessment_configs': AdminService._get_db().query(AssessmentConfig).filter(AssessmentConfig.is_active == True).count(),
                'media_settings': AdminService._get_db().query(MediaSetting).filter(MediaSetting.is_active == True).count()
            }
        }
