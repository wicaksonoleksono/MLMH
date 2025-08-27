# app/services/admin/phqService.py
from typing import List, Optional, Dict, Any
from sqlalchemy import and_
# from ...decorators import raw_response
from ...model.admin.phq import PHQQuestion, PHQScale, PHQSettings, PHQCategoryType
from ...db import get_session


class PHQService:
    """PHQ service for managing PHQ assessment configuration"""

    # ===== CATEGORY CRUD =====
    @staticmethod
    def get_categories() -> List[Dict[str, Any]]:
        """Get predefined PHQ categories with question counts"""
        categories = PHQCategoryType.get_all_categories()

        with get_session() as db:
            for cat in categories:
                # Get question count for each category
                question_count = db.query(PHQQuestion).filter(
                    PHQQuestion.category_name_id == cat['name_id'],
                    PHQQuestion.is_active == True
                ).count()
                cat['question_count'] = question_count

        return categories

    @staticmethod
    def get_default_categories() -> List[Dict[str, Any]]:
        """Get hardcoded default categories for 'Muat Default' button"""
        return PHQCategoryType.get_all_categories()

    # ===== QUESTION CRUD =====
    @staticmethod
    def get_questions(category_name_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get PHQ questions, optionally filtered by category"""
        with get_session() as db:
            query = db.query(PHQQuestion).filter(PHQQuestion.is_active == True)

            if category_name_id:
                query = query.filter(PHQQuestion.category_name_id == category_name_id)

            questions = query.order_by(PHQQuestion.category_name_id, PHQQuestion.order_index).all()

            return [{
                'id': q.id,
                'category_name_id': q.category_name_id,
                'question_text_en': q.question_text_en,
                'question_text_id': q.question_text_id,
                'order_index': q.order_index
            } for q in questions]

    @staticmethod
    def create_question(category_name_id: str, question_text_en: str, question_text_id: str,
                        order_index: int = 0) -> Dict[str, Any]:
        """Create or update PHQ question"""
        with get_session() as db:
            # Verify category exists in predefined list
            valid_categories = [cat.name_id for cat in PHQCategoryType]
            if category_name_id not in valid_categories:
                raise ValueError(f"Invalid category: {category_name_id}")

            # Check if question already exists for this category and order
            existing = db.query(PHQQuestion).filter(
                and_(
                    PHQQuestion.category_name_id == category_name_id,
                    PHQQuestion.order_index == order_index,
                    PHQQuestion.is_active == True
                )
            ).first()

            if existing:
                # Update existing question
                existing.question_text_en = question_text_en
                existing.question_text_id = question_text_id
                question = existing
            else:
                # Create new question
                question = PHQQuestion(
                    category_name_id=category_name_id,
                    question_text_en=question_text_en,
                    question_text_id=question_text_id,
                    order_index=order_index
                )
                db.add(question)

            db.commit()

            return {
                'id': question.id,
                'category_name_id': question.category_name_id,
                'question_text_id': question.question_text_id
            }

    @staticmethod
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
    def create_scale(scale_name: str, min_value: int, max_value: int,
                     scale_labels: Dict[str, str], is_default: bool = False) -> Dict[str, Any]:
        """Create or update PHQ scale"""
        with get_session() as db:
            existing = db.query(PHQScale).filter(PHQScale.scale_name == scale_name).first()

            if is_default:
                # Remove default from other scales
                db.query(PHQScale).filter(PHQScale.is_default == True).update({'is_default': False})

            if existing:
                # Update existing scale
                existing.min_value = min_value
                existing.max_value = max_value
                existing.scale_labels = scale_labels
                existing.is_default = is_default
                existing.is_active = True
                scale = existing
            else:
                # Create new scale
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
                'randomize_categories': setting.randomize_categories,
                'instructions': setting.instructions,
                'is_default': setting.is_default
            } for setting in settings]

    @staticmethod
    def create_settings(setting_name: str, questions_per_category: int, scale_id: int,
                        randomize_categories: bool = False, instructions: str = None,
                        is_default: bool = False) -> Dict[str, Any]:
        """Create or update PHQ settings"""
        with get_session() as db:
            existing = db.query(PHQSettings).filter(PHQSettings.setting_name == setting_name).first()

            if is_default:
                # Remove default from other settings
                db.query(PHQSettings).filter(PHQSettings.is_default == True).update({'is_default': False})

            if existing:
                # Update existing settings
                existing.questions_per_category = questions_per_category
                existing.scale_id = scale_id
                existing.randomize_categories = randomize_categories
                existing.instructions = instructions
                existing.is_default = is_default
                existing.is_active = True
                settings = existing
            else:
                # Create new settings
                settings = PHQSettings(
                    setting_name=setting_name,
                    questions_per_category=questions_per_category,
                    scale_id=scale_id,
                    randomize_categories=randomize_categories,
                    instructions=instructions,
                    is_default=is_default
                )
                db.add(settings)

            db.commit()

            return {
                'id': settings.id,
                'setting_name': settings.setting_name,
                'questions_per_category': settings.questions_per_category,
                'scale_id': settings.scale_id,
                'randomize_categories': settings.randomize_categories,
                'instructions': settings.instructions,
                'is_default': settings.is_default
            }

    @staticmethod
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
    def delete_settings(settings_id: int) -> Dict[str, Any]:
        """Soft delete PHQ settings"""
        with get_session() as db:
            settings = db.query(PHQSettings).filter(PHQSettings.id == settings_id).first()

            if not settings:
                raise ValueError(f"Settings with ID {settings_id} not found")

            settings.is_active = False
            db.commit()

            return {'id': settings_id, 'deleted': True}
