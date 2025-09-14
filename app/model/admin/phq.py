# app/model/admin/phq.py
from __future__ import annotations

from typing import Optional, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, JSON, ForeignKey, Boolean
from ..base import BaseModel, StatusMixin
import enum


class PHQCategoryType(enum.Enum):
    ANHEDONIA = (1, "Anhedonia", "Kehilangan minat atau kesenangan",
             "Kurang tertarik atau bergairah dalam melakukan apapun", [
                 "Dalam 2 minggu terakhir apakah Anda merasa kurang tertarik atau bergairah dalam melakukan apapun?",
                 "Selama 2 minggu terakhir, Anda merasa kehilangan minat atau tidak bersemangat untuk melakukan kegiatan apa pun?",
                 "Dalam rentang 2 minggu terakhir, apakah Anda sulit merasa tertarik atau bersemangat menjalani aktivitas?"
             ])

    DEPRESSED_MOOD = (2, "Suasana Hati Murung", "Merasa sedih, murung, atau putus asa",
                    "Merasa murung, muram, atau putus asa", [
                        "Dalam 2 minggu terakhir apakah Anda merasa murung, muram, atau putus asa?",
                        "Apakah dalam 2 minggu terakhir Anda mengalami suasana hati yang murung, perasaan muram, atau rasa putus asa?",
                        "Dalam rentang 2 minggu terakhir, apakah muncul perasaan murung, muram, ataupun putus asa pada diri Anda?"
                    ])

    SLEEP_DISTURBANCE = (3, "Gangguan Tidur", "Insomnia atau hipersomnia",
                        "Sulit tidur atau mudah terbangun, atau terlalu banyak tidur", [
                            "Dalam 2 minggu terakhir apakah Anda merasa sulit tidur atau mudah terbangun, atau terlalu banyak tidur?",
                            "Selama 2 minggu terakhir, apakah Anda mengalami kesulitan untuk tidur nyenyak, sering terbangun di malam hari, atau justru tidur berlebihan?",
                            "Dalam rentang 2 minggu terakhir, adakah gangguan tidur seperti sulit memulai tidur, mudah terbangun, ataupun tidur terlalu lama?"
                        ])

    FATIGUE = (4, "Kelelahan", "Kehilangan energi atau merasa lelah",
            "Merasa lelah atau kurang bertenaga", [
                "Dalam 2 minggu terakhir apakah Anda sering merasa lelah atau kurang bertenaga?",
                "Selama 2 minggu terakhir, adakah Anda kerap merasa letih atau kehilangan tenaga?",
                "Dalam rentang 2 minggu terakhir, apakah tubuh Anda sering terasa lelah atau tidak berenergi?"
            ])

    APPETITE_CHANGES = (5, "Perubahan Nafsu Makan", "Fluktuasi berat badan/nafsu makan",
                        "Kurang nafsu makan atau terlalu banyak makan", [
                            "Dalam 2 minggu terakhir apakah Anda merasa kurang nafsu makan atau terlalu banyak makan?",
                            "Selama 2 minggu terakhir, adakah perubahan pada selera makan Anda, seperti berkurang drastis atau justru berlebihan?",
                            "Dalam rentang 2 minggu terakhir, apakah Anda mengalami kesulitan mengendalikan nafsu makan, baik karena kurangnya selera maupun makan berlebihan?"
                        ])

    WORTHLESSNESS = (6, "Merasa Tidak Berharga", "Perasaan bersalah atau gagal",
                    "Kurang percaya diri atau merasa bahwa Anda adalah orang yang gagal atau telah mengecewakan diri sendiri atau keluarga", [
                        "Dalam 2 minggu terakhir apakah Anda merasa kurang percaya diri, atau merasa bahwa Anda adalah orang yang gagal atau telah mengecewakan diri sendiri atau keluarga?",
                        "Selama 2 minggu terakhir, adakah Anda merasa kurang yakin pada diri sendiri, merasa gagal, atau merasa telah mengecewakan diri maupun keluarga?",
                        "Dalam rentang 2 minggu terakhir, apakah muncul perasaan rendah diri, keyakinan bahwa Anda gagal, atau pikiran telah mengecewakan diri sendiri serta keluarga?"
                    ])

    CONCENTRATION = (7, "Kesulitan Konsentrasi", "Kesulitan fokus atau berpikir",
                    "Sulit berkonsentrasi pada sesuatu, misalnya membaca koran atau menonton televisi", [
                        "Dalam 2 minggu terakhir apakah Anda merasa sulit berkonsentrasi pada sesuatu, misalnya membaca berita atau menonton tayangan media?",
                        "Selama 2 minggu terakhir, adakah Anda mengalami kesulitan untuk memusatkan perhatian pada kegiatan, misalnya membaca berita atau menonton tayangan media?",
                        "Dalam rentang 2 minggu terakhir, apakah Anda merasa konsentrasi Anda mudah buyar ketika melakukan sesuatu seperti membaca berita atau menonton tayangan media?"
                    ])

    PSYCHOMOTOR = (8, "Gangguan Psikomotor", "Kegelisahan atau perlambatan gerak",
                "Bergerak atau berbicara sangat lambat sehingga orang lain memperhatikannya. Atau sebaliknya merasa resah atau gelisah sehingga lebih sering bergerak dari biasanya", [
                    "Dalam 2 minggu terakhir apakah Anda merasa bergerak atau berbicara sangat lambat sehingga orang lain memperhatikannya. Atau sebaliknya merasa resah atau gelisah sehingga Anda lebih sering bergerak dari biasanya?",
                    "Selama 2 minggu terakhir, adakah Anda merasa gerakan atau ucapan menjadi sangat lambat hingga orang lain menyadarinya, atau sebaliknya merasa gelisah sehingga lebih sering bergerak dari biasanya?",
                    "Dalam rentang 2 minggu terakhir, apakah Anda mengalami perubahan seperti bergerak atau berbicara jauh lebih lambat, atau justru merasa resah sehingga aktivitas tubuh Anda meningkat?"
                ])

    SUICIDAL_IDEATION = (9, "Pikiran Bunuh Diri", "Pikiran tentang kematian atau menyakiti diri sendiri",
                        "Merasa lebih baik mati atau ingin melukai diri sendiri dengan cara apapun", [
                            "Dalam 2 minggu terakhir apakah Anda merasa lebih baik mati atau ingin melukai diri sendiri dengan cara apapun?",
                            "Selama 2 minggu terakhir, adakah muncul pikiran bahwa lebih baik tidak hidup atau keinginan untuk menyakiti diri sendiri dengan cara apa pun?",
                            "Dalam rentang 2 minggu terakhir, apakah Anda mengalami dorongan atau pikiran tentang kematian, atau tentang melukai diri sendiri?"
                        ])


    def __init__(self, order_index, name_en, description_en, description_id, default_questions):
        self.order_index = order_index
        self.name_en = name_en
        self.description_en = description_en
        self.description_id = description_id
        self.default_questions = default_questions

    @property
    def name_id(self):
        return self.name.upper()

    @classmethod
    def get_all_categories(cls):
        return [{
            'name_id': cat.name_id,
            'name': cat.name_en,
            'description_en': cat.description_en,
            'description_id': cat.description_id,
            'order_index': cat.order_index,
            'default_questions': cat.default_questions
        } for cat in cls]

    @classmethod
    def get_default_scale(cls):
        """Default PHQ scale configuration"""
        return {
            'scale_name': 'PHQ-9 Default Scale',
            'min_value': 0,
            'max_value': 3,
            'scale_labels': {
                '0': 'Tidak sama sekali',
                '1': 'Beberapa hari',
                '2': 'Lebih dari setengah hari',
                '3': 'Hampir setiap hari'
            },
            'is_default': True
        }

    @classmethod
    def get_default_settings(cls):
        """Default PHQ settings configuration"""
        return {
            'randomize_categories': True,  # Default to True as requested
            'instructions': """Anda akan memulai kuesioner singkat untuk membantu memahami kondisi perasaan dan suasana hati Anda akhir-akhir ini.

Di halaman selanjutnya, kami telah menyiapkan beberapa pertanyaan singkat untuk membantu Anda merefleksikan perasaan Anda. Fokus utama dari kuesioner ini adalah kondisi anda dalam periode waktu selama 2 minggu terakhir. Saat menjawab, cobalah untuk mengingat kembali bagaimana perasaan Anda dalam rentang waktu tersebut.

Tidak ada jawaban yang benar atau salah. Jawaban yang paling jujur akan memberikan hasil yang paling bermanfaat bagi anda.""",
            'is_default': True
        }


class PHQQuestion(BaseModel, StatusMixin):
    __tablename__ = 'phq_questions'

    category_name_id: Mapped[str] = mapped_column(String(50), nullable=False)  # ANHEDONIA, DEPRESSED_MOOD, etc
    question_text_en: Mapped[str] = mapped_column(Text, nullable=False)
    question_text_id: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<PHQQuestion {self.id} - {self.category_name_id}>"


class PHQScale(BaseModel, StatusMixin):
    __tablename__ = 'phq_scales'
    scale_name: Mapped[str] = mapped_column(String(100), nullable=False)
    min_value: Mapped[int] = mapped_column(Integer, nullable=False)
    max_value: Mapped[int] = mapped_column(Integer, nullable=False)
    scale_labels: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<PHQScale {self.scale_name} ({self.min_value}-{self.max_value})>"


class PHQSettings(BaseModel, StatusMixin):
    __tablename__ = 'phq_settings'
    questions_per_category: Mapped[int] = mapped_column(Integer, default=1)
    scale_id: Mapped[int] = mapped_column(ForeignKey('phq_scales.id'), nullable=False)
    randomize_categories: Mapped[bool] = mapped_column(Boolean, default=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text)  # Instruksi pengisian untuk responden
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    scale: Mapped["PHQScale"] = relationship("PHQScale")

    def __repr__(self) -> str:
        return f"<PHQSettings {self.__tablename__}"
