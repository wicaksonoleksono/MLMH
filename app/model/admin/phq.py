# app/model/admin/phq.py
from __future__ import annotations

from typing import Optional, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, JSON, ForeignKey, Boolean
from ..base import BaseModel, StatusMixin
import enum


class PHQCategoryType(enum.Enum):
    ANHEDONIA = (1, "Anhedonia", "Kehilangan minat atau kesenangan",
                 "Kurang tertarik atau bergairah dalam melakukan apapun")
    DEPRESSED_MOOD = (2, "Suasana Hati Murung", "Merasa sedih, murung, atau putus asa",
                      "Merasa murung, muram, atau putus asa")
    SLEEP_DISTURBANCE = (3, "Gangguan Tidur", "Insomnia atau hipersomnia",
                         "Sulit tidur atau mudah terbangun, atau terlalu banyak tidur")
    FATIGUE = (4, "Kelelahan", "Kehilangan energi atau merasa lelah", "Merasa lelah atau kurang bertenaga")
    APPETITE_CHANGES = (5, "Perubahan Nafsu Makan", "Fluktuasi berat badan/nafsu makan",
                        "Kurang nafsu makan atau terlalu banyak makan")
    WORTHLESSNESS = (6, "Merasa Tidak Berharga", "Perasaan bersalah atau gagal",
                     "Kurang percaya diri — atau merasa bahwa Anda adalah orang yang gagal atau telah mengecewakan diri sendiri atau keluarga")
    CONCENTRATION = (7, "Kesulitan Konsentrasi", "Kesulitan fokus atau berpikir",
                     "Sulit berkonsentrasi pada sesuatu, misalnya membaca koran atau menonton televisi")
    PSYCHOMOTOR = (8, "Gangguan Psikomotor", "Kegelisahan atau perlambatan gerak",
                   "Bergerak atau berbicara sangat lambat sehingga orang lain memperhatikannya. Atau sebaliknya — merasa resah atau gelisah sehingga Anda lebih sering bergerak dari biasanya")
    SUICIDAL_IDEATION = (9, "Pikiran Bunuh Diri", "Pikiran tentang kematian atau menyakiti diri sendiri",
                         "Merasa lebih baik mati atau ingin melukai diri sendiri dengan cara apapun")

    def __init__(self, order_index, name_en, description_en, description_id):
        self.order_index = order_index
        self.name_en = name_en
        self.description_en = description_en
        self.description_id = description_id

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
            'order_index': cat.order_index
        } for cat in cls]


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
    # {0: "Tidak sama sekali", 1: "Beberapa hari", ...}
    scale_labels: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<PHQScale {self.scale_name} ({self.min_value}-{self.max_value})>"


class PHQSettings(BaseModel, StatusMixin):
    __tablename__ = 'phq_settings'

    setting_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    questions_per_category: Mapped[int] = mapped_column(Integer, default=1)
    scale_id: Mapped[int] = mapped_column(ForeignKey('phq_scales.id'), nullable=False)
    randomize_categories: Mapped[bool] = mapped_column(Boolean, default=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text)  # Instruksi pengisian untuk responden
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    scale: Mapped["PHQScale"] = relationship("PHQScale")

    def __repr__(self) -> str:
        return f"<PHQSettings {self.setting_name}>"
