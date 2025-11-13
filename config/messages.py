"""
Message management - إدارة رسائل المشروع متعدد اللغات
"""
import json
from pathlib import Path
from typing import Dict
from .logger import get_logger

logger = get_logger(__name__)

class MessageManager:
    """إدارة رسائل متعدد اللغات"""

    def __init__(self):
        self._messages: Dict[str, Dict[str, str]] = {}
        self.load_messages()

    def load_messages(self):
        """تحميل الرسائل من messages.json"""
        try:
            messages_path = Path(__file__).parent.parent / 'messages.json'
            with open(messages_path, 'r', encoding='utf-8') as f:
                self._messages = json.load(f)
            logger.info("✅ تم تحميل الرسائل بنجاح.")
        except Exception as e:
            logger.error(f"❌ فشل تحميل الرسائل: {e}")
            self._messages = {}

    def get(self, lang: str, key: str, default: str = None) -> str:
        """
        الحصول على رسالة محددة

        Args:
            lang: اللغة (ar/en)
            key: مفتاح الرسالة
            default: القيمة الافتراضية إذا لم توجد الرسالة

        Returns:
            الرسالة المطلوبة
        """
        if default is None:
            default = key
        return self._messages.get(lang, {}).get(key, default)

    def reload(self):
        """إعادة تحميل الرسائل"""
        self.load_messages()

# Singleton instance
_message_manager_instance = None

def get_message(lang: str, key: str, default: str = None) -> str:
    """
    دالة مختصرة للحصول على رسالة

    Args:
        lang: اللغة (ar/en)
        key: مفتاح الرسالة
        default: القيمة الافتراضية

    Returns:
        الرسالة المطلوبة
    """
    global _message_manager_instance
    if _message_manager_instance is None:
        _message_manager_instance = MessageManager()
    return _message_manager_instance.get(lang, key, default)
