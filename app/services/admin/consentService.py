# app/services/admin/consentService.py
from typing import List, Optional, Dict, Any
from sqlalchemy import and_
from ...model.admin.consent import ConsentSettings
from ...db import get_session


class ConsentService:
    """Consent service for managing informed consent settings"""
    DEFAULT_VALUE = """<p style="font-size: 10pt; background-color: #e8f4fc; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db;">Selamat datang di SINDI. Dengan menggunakan aplikasi ini, Anda setuju untuk mematuhi dan terikat oleh syarat dan ketentuan berikut. Mohon dibaca dengan seksama.</p>
<div style="font-size: 10pt;"><h2 style="color: #2c3e50; background-color: #f3f7fb; padding: 10px; border-radius: 5px; border-left: 4px solid #3498db;"><b>Pengumpulan dan Penyimpanan Data Pribadi</b></h2>
<p>Untuk memberikan layanan yang personal dan aman, kami akan mengumpulkan dan menyimpan data pribadi Anda. Data yang kami kumpulkan meliputi:</p>
<ul style="background-color: #f8f9fa; padding: 15px 15px 15px 40px; border-radius: 5px; list-style-type: circle;"><li><i>Nama Lengkap</i></li><li><i>Alamat Email</i></li><li><i>Nomor Telepon</i></li><li><i>Umur</i></li><li><i>Jenis Kelamin</i></li><li><i>Tingkat Pendidikan</i></li><li><i>Latar Belakang Budaya</i></li></ul></div>
<div style="font-size: 10pt;"><h2 style="color: #2c3e50; background-color: #f3f7fb; padding: 10px; border-radius: 5px; border-left: 4px solid #3498db;"><b>Penggunaan Data Pribadi</b></h2>
<p>Kami menjamin bahwa data pribadi Anda hanya akan digunakan untuk tujuan berikut:</p>
<ul style="background-color: #f8f9fa; padding: 15px 15px 15px 40px; border-radius: 5px; list-style-type: circle;"><li><b>Proses Autentikasi:</b> Memverifikasi identitas Anda saat masuk dan menggunakan fitur-fitur dalam aplikasi.</li><li><b>Pengolahan Agregasi Statistik:</b> Mengagregasikan hasil pengolahan statistik sesuai dengan pengelompokan tertentu.</li></ul></div>
<div style="font-size: 10pt;"><h2 style="color: #2c3e50; background-color: #f3f7fb; padding: 10px; border-radius: 5px; border-left: 4px solid #3498db;"><b>Pengumpulan dan Penyimpanan Data Penelitian</b></h2>
<p>Sesuai dengan tujuan penelitian, kami akan mengumpulkan dan menyimpan data yang meliputi:</p>
<ul style="background-color: #f8f9fa; padding: 15px 15px 15px 40px; border-radius: 5px; list-style-type: circle;"><li><i>Data wajah</i></li><li><i>Data kuesioner</i></li><li><i>Data percakapan</i></li></ul></div>
<div style="font-size: 10pt;"><h2 style="color: #2c3e50; background-color: #f3f7fb; padding: 10px; border-radius: 5px; border-left: 4px solid #3498db;"><b>Kerahasiaan dan Pembagian Data Pribadi dan Penelitian</b></h2>
<p style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">Kerahasiaan data Anda adalah prioritas utama kami. Data pribadi Anda tidak akan dibagikan, dijual, atau diungkapkan kepada pihak ketiga mana pun.</p></div>
<div style="font-size: 10pt;"><h2 style="color: #2c3e50; background-color: #f3f7fb; padding: 10px; border-radius: 5px; border-left: 4px solid #3498db;"><b>Analisis Data Penelitian Secara Anonim</b></h2>
<p>Untuk menganalisis aspek-aspek yang berkaitan dengan gejala depresi, kami akan menganalisis data wajah, kuesioner, dan percakapan secara agregat dan <b>anonim</b>. Proses ini dilakukan dengan menjaga kerahasiaan Anda sepenuhnya:</p>
<ul style="background-color: #f8f9fa; padding: 15px 15px 15px 40px; border-radius: 5px; list-style-type: circle;"><li>Data penelitian akan diekstrak untuk analisis kualitatif dan kuantitatif (misalnya, tingkat stres, sentimen umum, topik yang sering dibicarakan).</li><li>Hasil analisis akan disajikan dalam bentuk statistik anonim yang telah digabungkan dengan data dari pengguna lain.</li><li>Tidak ada informasi pribadi atau data yang dapat mengidentifikasi Anda secara personal yang akan disertakan dalam laporan statistik ini.</li></ul></div>
"""
    @staticmethod
    def get_settings() -> List[Dict[str, Any]]:
        """Get all consent settings"""
        with get_session() as db:
            settings = db.query(ConsentSettings).filter(ConsentSettings.is_active == True).all()

            return [{
                'id': setting.id,
                'title': setting.title,
                'content': setting.content,
                'footer_text': setting.footer_text,
                'is_default': setting.is_default
            } for setting in settings]

    @staticmethod
    def create_settings(title: str, content: str, 
                       footer_text: str = None,
                       is_default: bool = False) -> Dict[str, Any]:
        """Create or update consent settings"""
        with get_session() as db:
            # Null handling for footer_text
            final_footer_text = footer_text if footer_text and footer_text.strip() else None
            
            # Look for existing settings (assume only one set of settings for now)
            existing = db.query(ConsentSettings).filter(ConsentSettings.is_active == True).first()
            
            if is_default:
                # Remove default from other settings
                db.query(ConsentSettings).filter(ConsentSettings.is_default == True).update({'is_default': False})
            
            if existing:
                # Update existing settings
                existing.title = title.strip()
                existing.content = content.strip()
                existing.footer_text = final_footer_text
                existing.is_default = is_default
                
                # Auto-set is_active based on field completeness
                all_fields_valid = (
                    existing.title and existing.title.strip() != '' and
                    existing.content and existing.content.strip() != ''
                )
                # Ensure is_active is never None
                existing.is_active = bool(all_fields_valid)
                
                settings = existing
                
            else:
                # Create new settings
                settings = ConsentSettings(
                    title=title.strip(),
                    content=content.strip(),
                    footer_text=final_footer_text,
                    is_default=is_default
                )
                
                # Auto-set is_active based on field completeness
                all_fields_valid = (
                    settings.title and settings.title.strip() != '' and
                    settings.content and settings.content.strip() != ''
                )
                # Ensure is_active is never None
                settings.is_active = bool(all_fields_valid)
                
                db.add(settings)
            
            db.commit()
            
            return {
                'id': settings.id,
                'title': settings.title,
                'content': settings.content,
                'footer_text': settings.footer_text,
                'is_default': settings.is_default
            }

    @staticmethod
    def update_settings(settings_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update consent settings"""
        # DEBUG: Log what frontend is sending
        print(f"DEBUG update_settings received: {updates}")
        for key, value in updates.items():
            print(f"  {key}: {type(value).__name__} = {value}")
        
        # DETECT FIELD MAPPING BUG: is_active should never be None or dict
        if 'is_active' in updates:
            if updates['is_active'] is None:
                print(f"BUG DETECTED: is_active is None! Frontend is sending wrong field mapping.")
                print(f"   is_active value: {updates['is_active']}")
                del updates['is_active']
                print(f"   Removed is_active from updates to prevent crash.")
            elif isinstance(updates['is_active'], dict):
                print(f" BUG DETECTED: is_active is a dict! Frontend is sending wrong field mapping.")
                print(f"   is_active value: {updates['is_active']}")
                del updates['is_active']
                print(f"   Removed is_active from updates to prevent crash.")
        
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
                if hasattr(settings, key) and key != 'is_active':  # Skip is_active field, it's auto-calculated
                    setattr(settings, key, value)
            
            # Recalculate is_active based on field completeness
            all_fields_valid = (
                settings.title and settings.title.strip() != '' and
                settings.content and settings.content.strip() != ''
            )
            settings.is_active = all_fields_valid

            db.commit()

            return {
                'id': settings.id,
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
            "title": "Konfigurasi",
            "content": ConsentService.DEFAULT_VALUE,
            "footer_text": "-",
            "is_default": True
        }