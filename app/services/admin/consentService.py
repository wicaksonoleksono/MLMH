# app/services/admin/consentService.py
from typing import List, Optional, Dict, Any
from sqlalchemy import and_
from ...model.admin.consent import ConsentSettings
from ...db import get_session


class ConsentService:
    """Consent service for managing informed consent settings"""

    @staticmethod
    def get_settings() -> List[Dict[str, Any]]:
        """Get all consent settings"""
        with get_session() as db:
            settings = db.query(ConsentSettings).filter(ConsentSettings.is_active == True).all()

            return [{
                'id': setting.id,
                'setting_name': setting.setting_name,
                'title': setting.title,
                'content': setting.content,
                'require_signature': setting.require_signature,
                'require_date': setting.require_date,
                'allow_withdrawal': setting.allow_withdrawal,
                'footer_text': setting.footer_text,
                'is_default': setting.is_default
            } for setting in settings]

    @staticmethod
    def create_settings(title: str, content: str, 
                       require_signature: Optional[bool] = None, require_date: Optional[bool] = None,
                       allow_withdrawal: bool = False, footer_text: str = None,
                       is_default: bool = False) -> Dict[str, Any]:
        """Create or update consent settings"""
        with get_session() as db:
            # Null handling - don't save if required fields are null/empty
            if not title or not title.strip():
                raise ValueError("Title cannot be null or empty")
            
            if not content or not content.strip():
                raise ValueError("Content cannot be null or empty")
            
            # Null handling for optional fields - don't save if null/empty
            final_footer_text = footer_text if footer_text and footer_text.strip() else None
            
            # Auto-generate setting name
            setting_name = f"Consent Form - {title[:30]}"
            
            # Look for existing settings (assume only one set of settings for now)
            existing = db.query(ConsentSettings).filter(ConsentSettings.is_active == True).first()
            
            if is_default:
                # Remove default from other settings
                db.query(ConsentSettings).filter(ConsentSettings.is_default == True).update({'is_default': False})
            
            if existing:
                # Update existing settings
                existing.setting_name = setting_name
                existing.title = title.strip()
                existing.content = content.strip()
                existing.require_signature = require_signature
                existing.require_date = require_date
                existing.allow_withdrawal = allow_withdrawal
                existing.footer_text = final_footer_text
                existing.is_default = is_default
                settings = existing
            else:
                # Create new settings
                settings = ConsentSettings(
                    setting_name=setting_name,
                    title=title.strip(),
                    content=content.strip(),
                    require_signature=require_signature,
                    require_date=require_date,
                    allow_withdrawal=allow_withdrawal,
                    footer_text=final_footer_text,
                    is_default=is_default
                )
                db.add(settings)

            # Auto-set is_active based on field completeness
            all_fields_valid = (
                settings.setting_name and settings.setting_name.strip() != '' and
                settings.title and settings.title.strip() != '' and
                settings.content and settings.content.strip() != ''
            )
            settings.is_active = all_fields_valid
            
            db.commit()

            return {
                'id': settings.id,
                'setting_name': settings.setting_name,
                'title': settings.title,
                'content': settings.content,
                'require_signature': settings.require_signature,
                'require_date': settings.require_date,
                'allow_withdrawal': settings.allow_withdrawal,
                'footer_text': settings.footer_text,
                'is_default': settings.is_default
            }

    @staticmethod
    def update_settings(settings_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update consent settings"""
        with get_session() as db:
            settings = db.query(ConsentSettings).filter(
                and_(ConsentSettings.id == settings_id, ConsentSettings.is_active == True)
            ).first()

            if not settings:
                raise ValueError(f"Consent settings with ID {settings_id} not found")

            if updates.get('is_default'):
                # Remove default from other settings
                db.query(ConsentSettings).filter(ConsentSettings.is_default == True).update({'is_default': False})

            for key, value in updates.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)

            db.commit()

            return {
                'id': settings.id,
                'setting_name': settings.setting_name,
                'title': settings.title
            }

    @staticmethod
    def delete_settings(settings_id: int) -> Dict[str, Any]:
        """Soft delete consent settings"""
        with get_session() as db:
            settings = db.query(ConsentSettings).filter(ConsentSettings.id == settings_id).first()

            if not settings:
                raise ValueError(f"Consent settings with ID {settings_id} not found")

            db.commit()

            return {'id': settings_id, 'deleted': True}

    @staticmethod
    def get_default_settings() -> Dict[str, Any]:
        """Get hardcoded default consent settings for 'Muat Default' button"""
        return {
            "setting_name": "Default Consent Settings",
            "title": "Formulir Persetujuan Penelitian Kesehatan Mental",
            "content": "Dengan ini saya menyatakan bahwa saya telah mendapat penjelasan yang cukup mengenai penelitian ini dan saya bersedia berpartisipasi dalam penelitian assessment kesehatan mental.\n\nSaya memahami bahwa:\n1. Partisipasi saya bersifat sukarela\n2. Data yang dikumpulkan akan dijaga kerahasiaannya\n3. Saya dapat mengundurkan diri kapan saja\n4. Hasil assessment akan digunakan untuk keperluan penelitian",
            "require_signature": None,
            "require_date": None,
            "allow_withdrawal": True,
            "footer_text": "Terima kasih atas partisipasi Anda dalam penelitian ini.",
            "is_default": True
        }