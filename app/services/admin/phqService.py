# app/services/admin/phqService.py
from typing import List, Optional, Dict, Any
from sqlalchemy import and_
from ...decorators import api_response
from ...model.admin.phq import PHQCategory, PHQQuestion, PHQScale, PHQSettings
from ...db import get_session


class PHQService:
    """PHQ service for managing PHQ assessment configuration"""

    # ===== CATEGORY CRUD =====
    @staticmethod
    @api_response
    def get_categories() -> List[Dict[str, Any]]:
        """Get all PHQ categories"""
        with get_session() as db:
            categories = db.query(PHQCategory).filter(PHQCategory.is_active == True).order_by(PHQCategory.order_index).all()
            
            return [{
                'id': cat.id,
                'name': cat.name,
                'name_id': cat.name_id,
                'description_en': cat.description_en,
                'description_id': cat.description_id,
                'order_index': cat.order_index,
                'question_count': len(cat.questions)
            } for cat in categories]

    @staticmethod
    @api_response
    def create_category(name: str, name_id: str, description_en: str = None, 
                       description_id: str = None, order_index: int = 0) -> Dict[str, Any]:
        """Create new PHQ category"""
        with get_session() as db:
            existing = db.query(PHQCategory).filter(PHQCategory.name_id == name_id).first()
            if existing:
                raise ValueError(f"Category with name_id '{name_id}' already exists")

            category = PHQCategory(
                name=name,
                name_id=name_id,
                description_en=description_en,
                description_id=description_id,
                order_index=order_index
            )
            
            db.add(category)
            db.commit()
            
            return {
                'id': category.id,
                'name': category.name,
                'name_id': category.name_id,
                'order_index': category.order_index
            }

    @staticmethod
    @api_response
    def update_category(category_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update PHQ category"""
        with get_session() as db:
            category = db.query(PHQCategory).filter(
                and_(PHQCategory.id == category_id, PHQCategory.is_active == True)
            ).first()
            
            if not category:
                raise ValueError(f"Category with ID {category_id} not found")

            for key, value in updates.items():
                if hasattr(category, key):
                    setattr(category, key, value)
            
            db.commit()
            
            return {
                'id': category.id,
                'name': category.name,
                'name_id': category.name_id
            }

    @staticmethod
    @api_response
    def delete_category(category_id: int) -> Dict[str, Any]:
        """Soft delete PHQ category"""
        with get_session() as db:
            category = db.query(PHQCategory).filter(PHQCategory.id == category_id).first()
            
            if not category:
                raise ValueError(f"Category with ID {category_id} not found")
            
            category.is_active = False
            db.commit()
            
            return {'id': category_id, 'deleted': True}

    # ===== QUESTION CRUD =====
    @staticmethod
    @api_response
    def get_questions(category_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get PHQ questions, optionally filtered by category"""
        with get_session() as db:
            query = db.query(PHQQuestion).filter(PHQQuestion.is_active == True)
            
            if category_id:
                query = query.filter(PHQQuestion.category_id == category_id)
            
            questions = query.order_by(PHQQuestion.category_id, PHQQuestion.order_index).all()
            
            return [{
                'id': q.id,
                'category_id': q.category_id,
                'category_name': q.category.name,
                'question_text_en': q.question_text_en,
                'question_text_id': q.question_text_id,
                'order_index': q.order_index
            } for q in questions]

    @staticmethod
    @api_response
    def create_question(category_id: int, question_text_en: str, question_text_id: str, 
                       order_index: int = 0) -> Dict[str, Any]:
        """Create new PHQ question"""
        with get_session() as db:
            # Verify category exists
            category = db.query(PHQCategory).filter(
                and_(PHQCategory.id == category_id, PHQCategory.is_active == True)
            ).first()
            
            if not category:
                raise ValueError(f"Category with ID {category_id} not found")

            question = PHQQuestion(
                category_id=category_id,
                question_text_en=question_text_en,
                question_text_id=question_text_id,
                order_index=order_index
            )
            
            db.add(question)
            db.commit()
            
            return {
                'id': question.id,
                'category_id': question.category_id,
                'question_text_id': question.question_text_id
            }

    @staticmethod
    @api_response
    def update_question(question_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update PHQ question"""
        with get_session() as db:
            question = db.query(PHQQuestion).filter(
                and_(PHQQuestion.id == question_id, PHQQuestion.is_active == True)
            ).first()
            
            if not question:
                raise ValueError(f"Question with ID {question_id} not found")

            for key, value in updates.items():
                if hasattr(question, key):
                    setattr(question, key, value)
            
            db.commit()
            
            return {
                'id': question.id,
                'question_text_id': question.question_text_id
            }

    @staticmethod
    @api_response
    def delete_question(question_id: int) -> Dict[str, Any]:
        """Soft delete PHQ question"""
        with get_session() as db:
            question = db.query(PHQQuestion).filter(PHQQuestion.id == question_id).first()
            
            if not question:
                raise ValueError(f"Question with ID {question_id} not found")
            
            question.is_active = False
            db.commit()
            
            return {'id': question_id, 'deleted': True}

    # ===== SCALE CRUD =====
    @staticmethod
    @api_response
    def get_scales() -> List[Dict[str, Any]]:
        """Get all PHQ scales"""
        with get_session() as db:
            scales = db.query(PHQScale).filter(PHQScale.is_active == True).all()
            
            return [{
                'id': scale.id,
                'scale_name': scale.scale_name,
                'min_value': scale.min_value,
                'max_value': scale.max_value,
                'scale_labels': scale.scale_labels,
                'is_default': scale.is_default
            } for scale in scales]

    @staticmethod
    @api_response
    def create_scale(scale_name: str, min_value: int, max_value: int, 
                    scale_labels: Dict[str, str], is_default: bool = False) -> Dict[str, Any]:
        """Create new PHQ scale"""
        with get_session() as db:
            if is_default:
                # Remove default from other scales
                db.query(PHQScale).filter(PHQScale.is_default == True).update({'is_default': False})

            scale = PHQScale(
                scale_name=scale_name,
                min_value=min_value,
                max_value=max_value,
                scale_labels=scale_labels,
                is_default=is_default
            )
            
            db.add(scale)
            db.commit()
            
            return {
                'id': scale.id,
                'scale_name': scale.scale_name,
                'min_value': scale.min_value,
                'max_value': scale.max_value
            }

    @staticmethod
    @api_response
    def update_scale(scale_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update PHQ scale"""
        with get_session() as db:
            scale = db.query(PHQScale).filter(
                and_(PHQScale.id == scale_id, PHQScale.is_active == True)
            ).first()
            
            if not scale:
                raise ValueError(f"Scale with ID {scale_id} not found")

            if updates.get('is_default'):
                # Remove default from other scales
                db.query(PHQScale).filter(PHQScale.is_default == True).update({'is_default': False})

            for key, value in updates.items():
                if hasattr(scale, key):
                    setattr(scale, key, value)
            
            db.commit()
            
            return {
                'id': scale.id,
                'scale_name': scale.scale_name
            }

    @staticmethod
    @api_response
    def delete_scale(scale_id: int) -> Dict[str, Any]:
        """Soft delete PHQ scale"""
        with get_session() as db:
            scale = db.query(PHQScale).filter(PHQScale.id == scale_id).first()
            
            if not scale:
                raise ValueError(f"Scale with ID {scale_id} not found")
            
            scale.is_active = False
            db.commit()
            
            return {'id': scale_id, 'deleted': True}

    # ===== SETTINGS CRUD =====
    @staticmethod
    @api_response
    def get_settings() -> List[Dict[str, Any]]:
        """Get all PHQ settings"""
        with get_session() as db:
            settings = db.query(PHQSettings).filter(PHQSettings.is_active == True).all()
            
            return [{
                'id': setting.id,
                'setting_name': setting.setting_name,
                'questions_per_category': setting.questions_per_category,
                'scale_id': setting.scale_id,
                'scale_name': setting.scale.scale_name,
                'randomize_questions': setting.randomize_questions,
                'is_default': setting.is_default
            } for setting in settings]

    @staticmethod
    @api_response
    def create_settings(setting_name: str, questions_per_category: int, scale_id: int,
                       randomize_questions: bool = False, is_default: bool = False) -> Dict[str, Any]:
        """Create new PHQ settings"""
        with get_session() as db:
            existing = db.query(PHQSettings).filter(PHQSettings.setting_name == setting_name).first()
            if existing:
                raise ValueError(f"Settings with name '{setting_name}' already exists")

            if is_default:
                # Remove default from other settings
                db.query(PHQSettings).filter(PHQSettings.is_default == True).update({'is_default': False})

            settings = PHQSettings(
                setting_name=setting_name,
                questions_per_category=questions_per_category,
                scale_id=scale_id,
                randomize_questions=randomize_questions,
                is_default=is_default
            )
            
            db.add(settings)
            db.commit()
            
            return {
                'id': settings.id,
                'setting_name': settings.setting_name,
                'questions_per_category': settings.questions_per_category
            }

    @staticmethod
    @api_response
    def update_settings(settings_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update PHQ settings"""
        with get_session() as db:
            settings = db.query(PHQSettings).filter(
                and_(PHQSettings.id == settings_id, PHQSettings.is_active == True)
            ).first()
            
            if not settings:
                raise ValueError(f"Settings with ID {settings_id} not found")

            if updates.get('is_default'):
                # Remove default from other settings
                db.query(PHQSettings).filter(PHQSettings.is_default == True).update({'is_default': False})

            for key, value in updates.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            db.commit()
            
            return {
                'id': settings.id,
                'setting_name': settings.setting_name
            }

    @staticmethod
    @api_response
    def delete_settings(settings_id: int) -> Dict[str, Any]:
        """Soft delete PHQ settings"""
        with get_session() as db:
            settings = db.query(PHQSettings).filter(PHQSettings.id == settings_id).first()
            
            if not settings:
                raise ValueError(f"Settings with ID {settings_id} not found")
            
            settings.is_active = False
            db.commit()
            
            return {'id': settings_id, 'deleted': True}