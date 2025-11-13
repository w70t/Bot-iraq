"""
Unified logging configuration - إعداد موحد للـ logging
"""
import logging
import sys
from pathlib import Path

# إنشاء مجلد logs إذا لم يكن موجوداً
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

def setup_logging(level=logging.INFO):
    """
    إعداد موحد للـ logging لجميع الملفات

    Args:
        level: مستوى الـ logging (default: INFO)
    """
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=level,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_DIR / 'bot.log', encoding='utf-8')
        ]
    )

def get_logger(name):
    """
    الحصول على logger موحد

    Args:
        name: اسم الـ logger (عادةً __name__)

    Returns:
        logger object
    """
    return logging.getLogger(name)
