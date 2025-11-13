from datetime import datetime
from .base import settings_collection

# استخدام logger من config
try:
    from config.logger import get_logger
except ImportError:
    import logging
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Audio Settings Management
# ═══════════════════════════════════════════════════════════════

def get_audio_settings():
    """جلب إعدادات الصوت الحالية"""
    try:
        if settings_collection is None:
            return None

        settings = settings_collection.find_one({'_id': 'audio_settings'})

        # إنشاء الإعدادات الافتراضية إذا لم تكن موجودة
        if not settings:
            default_settings = {
                '_id': 'audio_settings',
                'audio_enabled': True,
                'audio_limit_minutes': 10.0,  # 10 دقائق للمستخدمين غير المشتركين
                'last_updated': datetime.now()
            }
            settings_collection.insert_one(default_settings)
            logger.info("✅ تم إنشاء إعدادات الصوت الافتراضية")
            return default_settings

        return settings
    except Exception as e:
        logger.error(f"❌ فشل جلب إعدادات الصوت: {e}")
        return None


def set_audio_enabled(enabled: bool):
    """تفعيل أو إيقاف تحميل الصوتيات"""
    try:
        if settings_collection is None:
            return False

        settings_collection.update_one(
            {'_id': 'audio_settings'},
            {
                '$set': {
                    'audio_enabled': enabled,
                    'last_updated': datetime.now()
                }
            },
            upsert=True
        )

        status = "مفعّل" if enabled else "معطّل"
        logger.info(f"✅ تحميل الصوتيات تم {status}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة الصوتيات: {e}")
        return False


def set_audio_limit_minutes(minutes: float):
    """تعيين حد التحميل للصوتيات بالدقائق (للمستخدمين غير المشتركين)

    استخدم -1 للتحميل غير المحدود
    """
    try:
        if settings_collection is None:
            return False

        # -1 يعني غير محدود
        if minutes == -1:
            logger.info("✅ تم تعيين التحميل إلى غير محدود")
        elif minutes < 0:
            logger.warning("⚠️ الحد الزمني لا يمكن أن يكون سالب، استخدام 0")
            minutes = 0

        settings_collection.update_one(
            {'_id': 'audio_settings'},
            {
                '$set': {
                    'audio_limit_minutes': float(minutes),
                    'last_updated': datetime.now()
                }
            },
            upsert=True
        )

        if minutes == -1:
            logger.info(f"✅ تم تعيين حد الصوتيات إلى: غير محدود")
        else:
            logger.info(f"✅ تم تعيين حد الصوتيات إلى: {minutes} دقيقة")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حد الصوتيات: {e}")
        return False


def is_audio_enabled():
    """التحقق من حالة تحميل الصوتيات"""
    try:
        settings = get_audio_settings()
        if not settings:
            return True  # الافتراضي: مفعّل
        return settings.get('audio_enabled', True)
    except Exception as e:
        logger.error(f"❌ فشل التحقق من حالة الصوتيات: {e}")
        return True


def get_audio_limit_minutes():
    """جلب حد التحميل للصوتيات بالدقائق"""
    try:
        settings = get_audio_settings()
        if not settings:
            return 10.0  # الافتراضي: 10 دقائق
        return settings.get('audio_limit_minutes', 10.0)
    except Exception as e:
        logger.error(f"❌ فشل جلب حد الصوتيات: {e}")
        return 10.0


# ═══════════════════════════════════════════════════════════════
#  General Limits Settings (Free Users)
# ═══════════════════════════════════════════════════════════════

def get_general_limits():
    """جلب الإعدادات العامة للقيود"""
    try:
        if settings_collection is None:
            return None

        settings = settings_collection.find_one({'_id': 'general_limits'})

        if not settings:
            default_settings = {
                '_id': 'general_limits',
                'free_time_limit': 5,  # 5 دقائق للمستخدمين غير المشتركين
                'daily_download_limit': 3,  # 3 تحميلات يومية
                'last_updated': datetime.now()
            }
            settings_collection.insert_one(default_settings)
            logger.info("✅ تم إنشاء إعدادات القيود العامة الافتراضية")
            return default_settings

        return settings
    except Exception as e:
        logger.error(f"❌ فشل جلب الإعدادات العامة: {e}")
        return None


def set_free_time_limit(minutes: int):
    """تعيين الحد الزمني للفيديوهات للمستخدمين غير المشتركين (بالدقائق)"""
    try:
        if settings_collection is None:
            return False

        if minutes < 0:
            logger.warning("⚠️ الحد الزمني لا يمكن أن يكون سالب، استخدام 0")
            minutes = 0

        settings_collection.update_one(
            {'_id': 'general_limits'},
            {
                '$set': {
                    'free_time_limit': int(minutes),
                    'last_updated': datetime.now()
                }
            },
            upsert=True
        )

        logger.info(f"✅ تم تعيين الحد الزمني لغير المشتركين إلى: {minutes} دقيقة")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث الحد الزمني: {e}")
        return False


def get_free_time_limit():
    """جلب الحد الزمني للفيديوهات للمستخدمين غير المشتركين"""
    try:
        settings = get_general_limits()
        if not settings:
            return 5  # الافتراضي: 5 دقائق
        return settings.get('free_time_limit', 5)
    except Exception as e:
        logger.error(f"❌ فشل جلب الحد الزمني: {e}")
        return 5


def set_daily_download_limit(count: int):
    """تعيين عدد التحميلات اليومية المسموح بها للمستخدمين غير المشتركين"""
    try:
        if settings_collection is None:
            return False

        if count < 0:
            logger.warning("⚠️ عدد التحميلات لا يمكن أن يكون سالب، استخدام 0")
            count = 0

        settings_collection.update_one(
            {'_id': 'general_limits'},
            {
                '$set': {
                    'daily_download_limit': int(count),
                    'last_updated': datetime.now()
                }
            },
            upsert=True
        )

        logger.info(f"✅ تم تعيين الحد اليومي لغير المشتركين إلى: {count} تحميل")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث الحد اليومي: {e}")
        return False


def get_daily_download_limit_setting():
    """جلب عدد التحميلات اليومية المسموح بها للمستخدمين غير المشتركين"""
    try:
        settings = get_general_limits()
        if not settings:
            return 3  # الافتراضي: 3 تحميلات
        return settings.get('daily_download_limit', 3)
    except Exception as e:
        logger.error(f"❌ فشل جلب الحد اليومي: {e}")
        return 3
