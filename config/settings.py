"""
Settings management - إدارة إعدادات المشروع
"""
import os
import json
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from .logger import get_logger

logger = get_logger(__name__)

# تحميل متغيرات البيئة
load_dotenv()

class Settings:
    """إدارة إعدادات المشروع من config.json و .env"""

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self.load_config()

    def load_config(self):
        """تحميل الإعدادات من config.json ودمجها مع .env"""
        try:
            config_path = Path(__file__).parent.parent / 'config.json'
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            logger.info("✅ تم تحميل ملف الإعدادات بنجاح.")

            # دمج المتغيرات السرية من .env
            self._merge_env_variables()

        except FileNotFoundError:
            logger.error("!!! ملف config.json غير موجود. سيتم استخدام إعدادات افتراضية.")
            self._config = {}
        except json.JSONDecodeError as e:
            logger.error(f"!!! خطأ في قراءة ملف config.json: {e}")
            self._config = {}

    def _merge_env_variables(self):
        """دمج متغيرات البيئة مع الإعدادات"""
        # إضافة بيانات Binance
        self._config['binance_api_key'] = os.getenv('BINANCE_API_KEY', 'YOUR_BINANCE_API_KEY_HERE')
        self._config['binance_secret_key'] = os.getenv('BINANCE_SECRET_KEY', 'YOUR_BINANCE_SECRET_KEY_HERE')

        # إضافة معلومات الدفع عبر Instagram
        instagram_username = os.getenv('INSTAGRAM_PAYMENT_USERNAME', '7kmmy')
        self._config['instagram_payment'] = {
            'username': instagram_username,
            'message_ar': f"شكراً لاختيارك! تواصل عبر الإنستغرام @{instagram_username} للدفع",
            'message_en': f"Thank you for choosing! Contact @{instagram_username} on Instagram for payment"
        }

        # إضافة سعر الاشتراك
        self._config['subscription_price_usd'] = float(os.getenv('SUBSCRIPTION_PRICE_USD', '3.0'))

        logger.info("✅ تم دمج متغيرات البيئة مع الإعدادات.")

    def get(self, key: str, default: Any = None) -> Any:
        """الحصول على قيمة إعداد معين"""
        return self._config.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """الحصول على جميع الإعدادات"""
        return self._config.copy()

    @property
    def max_free_duration(self) -> int:
        """الحد الأقصى لمدة الفيديو المجاني"""
        return self._config.get('MAX_FREE_DURATION', 300)

    @property
    def logo_path(self) -> str:
        """مسار ملف اللوجو"""
        return self._config.get('LOGO_PATH', 'Logo.png')

    @property
    def payments_enabled(self) -> bool:
        """هل نظام الدفع مفعّل"""
        return self._config.get('payments_enabled', True)

    @property
    def blocked_domains(self) -> list:
        """قائمة الدومينات المحظورة"""
        return self._config.get('BLOCKED_DOMAINS', [])

    @property
    def adult_content_keywords(self) -> list:
        """كلمات محتوى للبالغين"""
        return self._config.get('ADULT_CONTENT_KEYWORDS', [])

# Singleton instance
_settings_instance = None

def get_settings() -> Settings:
    """الحصول على instance واحد من Settings"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance

def get_config() -> Dict[str, Any]:
    """
    Compatibility function - الحصول على جميع الإعدادات كـ dictionary

    Returns:
        جميع الإعدادات
    """
    return get_settings().get_all()
