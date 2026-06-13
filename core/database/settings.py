from datetime import datetime
from .base import settings_collection
from config.logger import get_logger

# إنشاء logger instance
logger = get_logger(__name__)


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


# ═══════════════════════════════════════════════════════════════
#  Referral System Settings
# ═══════════════════════════════════════════════════════════════

def get_referral_settings():
    """جلب إعدادات نظام الإحالة الحالية"""
    try:
        if settings_collection is None:
            return None

        settings = settings_collection.find_one({'_id': 'referral_settings'})

        # إنشاء الإعدادات الافتراضية إذا لم تكن موجودة
        if not settings:
            default_settings = {
                '_id': 'referral_settings',
                'referral_enabled': True,  # مفعّل افتراضياً
                'last_updated': datetime.now()
            }
            settings_collection.insert_one(default_settings)
            logger.info("✅ تم إنشاء إعدادات نظام الإحالة الافتراضية")
            return default_settings

        return settings
    except Exception as e:
        logger.error(f"❌ فشل جلب إعدادات نظام الإحالة: {e}")
        return None


def set_referral_enabled(enabled: bool):
    """تفعيل أو إيقاف نظام الإحالة"""
    try:
        if settings_collection is None:
            return False

        settings_collection.update_one(
            {'_id': 'referral_settings'},
            {
                '$set': {
                    'referral_enabled': enabled,
                    'last_updated': datetime.now()
                }
            },
            upsert=True
        )

        status = "مفعّل" if enabled else "معطّل"
        logger.info(f"✅ نظام الإحالة تم {status}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة نظام الإحالة: {e}")
        return False


def is_referral_enabled():
    """التحقق من حالة نظام الإحالة"""
    try:
        settings = get_referral_settings()
        if not settings:
            return True  # الافتراضي: مفعّل
        return settings.get('referral_enabled', True)
    except Exception as e:
        logger.error(f"❌ فشل التحقق من حالة نظام الإحالة: {e}")
        return True


# ═══════════════════════════════════════════════════════════════
#  Content Filter Settings (Adult / NSFW)
# ═══════════════════════════════════════════════════════════════

# القوائم الافتراضية (تُستخدم عند إنشاء الإعدادات لأول مرة فقط)
DEFAULT_BLOCKED_DOMAINS = [
    "pornhub.com", "xvideos.com", "xnxx.com", "redtube.com", "youporn.com",
    "porn.com", "sex.com", "tube8.com", "spankbang.com", "eporner.com",
    "hqporner.com", "txxx.com", "xhamster.com", "beeg.com", "drtuber.com"
]

DEFAULT_BLOCKED_KEYWORDS = [
    "porn", "xxx", "sex", "nude", "nsfw", "adult", "18+", "erotic"
]


def get_content_filter_settings():
    """جلب إعدادات فلتر المحتوى الإباحي الحالية"""
    try:
        if settings_collection is None:
            return None

        settings = settings_collection.find_one({'_id': 'content_filter'})

        # إنشاء الإعدادات الافتراضية إذا لم تكن موجودة
        if not settings:
            default_settings = {
                '_id': 'content_filter',
                'enabled': True,            # الفلتر مفعّل افتراضياً
                'age_limit_check': True,    # فحص age_limit من yt-dlp مفعّل افتراضياً
                'blocked_domains': list(DEFAULT_BLOCKED_DOMAINS),
                'blocked_keywords': list(DEFAULT_BLOCKED_KEYWORDS),
                'last_updated': datetime.now()
            }
            settings_collection.insert_one(default_settings)
            logger.info("✅ تم إنشاء إعدادات فلتر المحتوى الافتراضية")
            return default_settings

        return settings
    except Exception as e:
        logger.error(f"❌ فشل جلب إعدادات فلتر المحتوى: {e}")
        return None


def is_content_filter_enabled():
    """التحقق من حالة فلتر المحتوى الإباحي"""
    try:
        settings = get_content_filter_settings()
        if not settings:
            return True  # الافتراضي: مفعّل (آمن)
        return settings.get('enabled', True)
    except Exception as e:
        logger.error(f"❌ فشل التحقق من حالة فلتر المحتوى: {e}")
        return True


def set_content_filter_enabled(enabled: bool):
    """تفعيل أو إيقاف فلتر المحتوى الإباحي"""
    try:
        if settings_collection is None:
            return False

        # ضمان وجود المستند بإعداداته الافتراضية أولاً
        get_content_filter_settings()

        settings_collection.update_one(
            {'_id': 'content_filter'},
            {'$set': {'enabled': enabled, 'last_updated': datetime.now()}},
            upsert=True
        )

        status = "مفعّل" if enabled else "معطّل"
        logger.info(f"✅ فلتر المحتوى الإباحي تم {status}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة فلتر المحتوى: {e}")
        return False


def is_age_limit_check_enabled():
    """التحقق من حالة فحص age_limit (المحتوى المقيّد للبالغين على المنصات العامة)"""
    try:
        settings = get_content_filter_settings()
        if not settings:
            return True
        return settings.get('age_limit_check', True)
    except Exception as e:
        logger.error(f"❌ فشل التحقق من حالة فحص age_limit: {e}")
        return True


def set_age_limit_check_enabled(enabled: bool):
    """تفعيل أو إيقاف فحص age_limit من yt-dlp"""
    try:
        if settings_collection is None:
            return False

        get_content_filter_settings()

        settings_collection.update_one(
            {'_id': 'content_filter'},
            {'$set': {'age_limit_check': enabled, 'last_updated': datetime.now()}},
            upsert=True
        )

        status = "مفعّل" if enabled else "معطّل"
        logger.info(f"✅ فحص age_limit تم {status}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة فحص age_limit: {e}")
        return False


def get_blocked_domains():
    """جلب قائمة النطاقات المحظورة"""
    try:
        settings = get_content_filter_settings()
        if not settings:
            return list(DEFAULT_BLOCKED_DOMAINS)
        return settings.get('blocked_domains', list(DEFAULT_BLOCKED_DOMAINS))
    except Exception as e:
        logger.error(f"❌ فشل جلب النطاقات المحظورة: {e}")
        return list(DEFAULT_BLOCKED_DOMAINS)


def get_blocked_keywords():
    """جلب قائمة الكلمات المحظورة"""
    try:
        settings = get_content_filter_settings()
        if not settings:
            return list(DEFAULT_BLOCKED_KEYWORDS)
        return settings.get('blocked_keywords', list(DEFAULT_BLOCKED_KEYWORDS))
    except Exception as e:
        logger.error(f"❌ فشل جلب الكلمات المحظورة: {e}")
        return list(DEFAULT_BLOCKED_KEYWORDS)


def add_blocked_domain(domain: str):
    """إضافة نطاق محظور. يرجع (نجاح, رسالة)"""
    try:
        if settings_collection is None:
            return False, "قاعدة البيانات غير متاحة"

        domain = domain.strip().lower()
        if not domain:
            return False, "النطاق فارغ"

        get_content_filter_settings()

        if domain in get_blocked_domains():
            return False, "النطاق موجود مسبقاً"

        settings_collection.update_one(
            {'_id': 'content_filter'},
            {'$addToSet': {'blocked_domains': domain},
             '$set': {'last_updated': datetime.now()}},
            upsert=True
        )
        logger.info(f"✅ تم إضافة نطاق محظور: {domain}")
        return True, "تمت الإضافة"
    except Exception as e:
        logger.error(f"❌ فشل إضافة النطاق المحظور: {e}")
        return False, "حدث خطأ"


def remove_blocked_domain(domain: str):
    """حذف نطاق محظور. يرجع (نجاح, رسالة)"""
    try:
        if settings_collection is None:
            return False, "قاعدة البيانات غير متاحة"

        domain = domain.strip().lower()
        get_content_filter_settings()

        if domain not in get_blocked_domains():
            return False, "النطاق غير موجود"

        settings_collection.update_one(
            {'_id': 'content_filter'},
            {'$pull': {'blocked_domains': domain},
             '$set': {'last_updated': datetime.now()}}
        )
        logger.info(f"✅ تم حذف نطاق محظور: {domain}")
        return True, "تم الحذف"
    except Exception as e:
        logger.error(f"❌ فشل حذف النطاق المحظور: {e}")
        return False, "حدث خطأ"


def add_blocked_keyword(keyword: str):
    """إضافة كلمة محظورة. يرجع (نجاح, رسالة)"""
    try:
        if settings_collection is None:
            return False, "قاعدة البيانات غير متاحة"

        keyword = keyword.strip().lower()
        if not keyword:
            return False, "الكلمة فارغة"

        get_content_filter_settings()

        if keyword in get_blocked_keywords():
            return False, "الكلمة موجودة مسبقاً"

        settings_collection.update_one(
            {'_id': 'content_filter'},
            {'$addToSet': {'blocked_keywords': keyword},
             '$set': {'last_updated': datetime.now()}},
            upsert=True
        )
        logger.info(f"✅ تم إضافة كلمة محظورة: {keyword}")
        return True, "تمت الإضافة"
    except Exception as e:
        logger.error(f"❌ فشل إضافة الكلمة المحظورة: {e}")
        return False, "حدث خطأ"


def remove_blocked_keyword(keyword: str):
    """حذف كلمة محظورة. يرجع (نجاح, رسالة)"""
    try:
        if settings_collection is None:
            return False, "قاعدة البيانات غير متاحة"

        keyword = keyword.strip().lower()
        get_content_filter_settings()

        if keyword not in get_blocked_keywords():
            return False, "الكلمة غير موجودة"

        settings_collection.update_one(
            {'_id': 'content_filter'},
            {'$pull': {'blocked_keywords': keyword},
             '$set': {'last_updated': datetime.now()}}
        )
        logger.info(f"✅ تم حذف كلمة محظورة: {keyword}")
        return True, "تم الحذف"
    except Exception as e:
        logger.error(f"❌ فشل حذف الكلمة المحظورة: {e}")
        return False, "حدث خطأ"
