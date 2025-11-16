from datetime import datetime
from .base import db
from config.logger import get_logger

# إنشاء logger
logger = get_logger(__name__)


# ========== نظام إدارة المكتبات والإعدادات ==========

def init_library_settings():
    """تهيئة إعدادات المكتبات الافتراضية - جميع المنصات مفعلة"""
    try:
        # ⭐ جميع المنصات المدعومة مفعلة افتراضياً
        default_settings = {
            '_id': 'library_settings',
            'primary_library': 'yt-dlp',
            'backup_library': 'youtube-dl',
            'auto_update': True,
            'allowed_platforms': {
                'youtube': True,
                'facebook': True,
                'instagram': True,
                'threads': True,  # ⭐ إضافة منصة Threads
                'tiktok': True,
                'pinterest': True,
                'twitter': True,
                'reddit': True,
                'vimeo': True,
                'dailymotion': True,
                'twitch': True
            },
            'library_status': {
                'yt-dlp': {
                    'installed': True,
                    'version': '2024.12.13',
                    'last_check': datetime.now(),
                    'status': 'active',
                    'success_rate': 95
                },
                'youtube-dl': {
                    'installed': False,
                    'version': None,
                    'last_check': None,
                    'status': 'inactive',
                    'success_rate': 75
                }
            },
            'admin_approvals': {
                'pending_requests': [],
                'approved_platforms': [],
                'denied_platforms': []
            },
            'performance_metrics': {
                'total_downloads': 0,
                'successful_downloads': 0,
                'failed_downloads': 0,
                'avg_download_speed': 0,
                'last_reset': datetime.now()
            }
        }

        db.settings.update_one(
            {'_id': 'library_settings'},
            {'$setOnInsert': default_settings},
            upsert=True
        )
        logger.info("✅ تم تهيئة إعدادات المكتبات الافتراضية")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تهيئة إعدادات المكتبات: {e}")
        return False


def get_library_settings():
    """جلب إعدادات المكتبات الحالية"""
    try:
        settings = db.settings.find_one({'_id': 'library_settings'})
        if not settings:
            init_library_settings()
            settings = db.settings.find_one({'_id': 'library_settings'})
        return settings
    except Exception as e:
        logger.error(f"❌ فشل جلب إعدادات المكتبات: {e}")
        return None


def update_library_setting(key: str, value):
    """تحديث إعداد مكتبة محدد"""
    try:
        db.settings.update_one(
            {'_id': 'library_settings'},
            {'$set': {key: value}}
        )
        logger.info(f"✅ تم تحديث {key}: {value}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث {key}: {e}")
        return False


def toggle_platform(platform: str, enabled: bool):
    """تفعيل/إلغاء تفعيل منصة معينة"""
    try:
        # ⭐ قائمة موسعة للمنصات المدعومة
        supported_platforms = [
            'youtube', 'facebook', 'instagram', 'threads', 'tiktok',
            'pinterest', 'twitter', 'reddit', 'vimeo',
            'dailymotion', 'twitch'
        ]

        if platform not in supported_platforms:
            logger.warning(f"⚠️ المنصة {platform} غير مدعومة")
            return False

        db.settings.update_one(
            {'_id': 'library_settings'},
            {'$set': {f'allowed_platforms.{platform}': enabled}}
        )
        logger.info(f"✅ تم {'تفعيل' if enabled else 'إلغاء تفعيل'} منصة {platform}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة منصة {platform}: {e}")
        return False


def is_platform_allowed(platform: str) -> bool:
    """التحقق من السماح بمنصة معينة"""
    try:
        settings = get_library_settings()
        if not settings:
            return True  # افتراضياً، السماح بكل شيء

        return settings.get('allowed_platforms', {}).get(platform, True)
    except Exception as e:
        logger.error(f"❌ فشل التحقق من منصة {platform}: {e}")
        return True


def get_allowed_platforms() -> list:
    """جلب قائمة المنصات المسموحة - افتراضياً جميع المنصات مفعلة"""
    try:
        settings = get_library_settings()
        if not settings:
            # ⭐ إرجاع جميع المنصات المدعومة افتراضياً
            return [
                'youtube', 'facebook', 'instagram', 'threads', 'tiktok',
                'pinterest', 'twitter', 'reddit', 'vimeo',
                'dailymotion', 'twitch'
            ]

        allowed = settings.get('allowed_platforms', {})
        # إرجاع المنصات المفعلة فقط
        return [platform for platform, enabled in allowed.items() if enabled]
    except Exception as e:
        logger.error(f"❌ فشل جلب المنصات المسموحة: {e}")
        # في حالة الخطأ، إرجاع جميع المنصات
        return [
            'youtube', 'facebook', 'instagram', 'threads', 'tiktok',
            'pinterest', 'twitter', 'reddit', 'vimeo',
            'dailymotion', 'twitch'
        ]


def add_admin_approval_request(platform: str, requested_by: int, request_data: dict):
    """إضافة طلب موافقة للمدير"""
    try:
        approval_request = {
            'id': f"{platform}_{requested_by}_{datetime.now().timestamp()}",
            'platform': platform,
            'requested_by': requested_by,
            'request_date': datetime.now(),
            'status': 'pending',
            'data': request_data
        }

        db.settings.update_one(
            {'_id': 'library_settings'},
            {'$push': {'admin_approvals.pending_requests': approval_request}}
        )
        logger.info(f"✅ تم إضافة طلب موافقة للمنصة {platform}")
        return approval_request['id']
    except Exception as e:
        logger.error(f"❌ فشل إضافة طلب الموافقة: {e}")
        return None


def get_pending_approvals():
    """جلب طلبات الموافقة المعلقة"""
    try:
        settings = get_library_settings()
        if not settings:
            return []

        return settings.get('admin_approvals', {}).get('pending_requests', [])
    except Exception as e:
        logger.error(f"❌ فشل جلب طلبات الموافقة: {e}")
        return []


def approve_platform_request(request_id: str, approved_by: int):
    """موافقة على طلب تفعيل منصة"""
    try:
        settings = db.settings.find_one({'_id': 'library_settings'})
        if not settings:
            return False

        # البحث عن الطلب
        pending_requests = settings.get('admin_approvals', {}).get('pending_requests', [])
        request = next((r for r in pending_requests if r['id'] == request_id), None)

        if not request:
            return False

        platform = request['platform']

        # نقل الطلب إلى قائمة الموافقات
        db.settings.update_one(
            {'_id': 'library_settings'},
            {
                '$pull': {'admin_approvals.pending_requests': {'id': request_id}},
                '$push': {'admin_approvals.approved_platforms': request}
            }
        )

        # تفعيل المنصة
        toggle_platform(platform, True)

        logger.info(f"✅ تمت الموافقة على منصة {platform} بواسطة المدير {approved_by}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل الموافقة على الطلب: {e}")
        return False


def deny_platform_request(request_id: str, denied_by: int, reason: str = ""):
    """رفض طلب تفعيل منصة"""
    try:
        settings = db.settings.find_one({'_id': 'library_settings'})
        if not settings:
            return False

        # البحث عن الطلب
        pending_requests = settings.get('admin_approvals', {}).get('pending_requests', [])
        request = next((r for r in pending_requests if r['id'] == request_id), None)

        if not request:
            return False

        platform = request['platform']

        # إضافة سبب الرفض
        request['denied_by'] = denied_by
        request['denied_reason'] = reason
        request['denied_date'] = datetime.now()

        # نقل الطلب إلى قائمة المرفوضات
        db.settings.update_one(
            {'_id': 'library_settings'},
            {
                '$pull': {'admin_approvals.pending_requests': {'id': request_id}},
                '$push': {'admin_approvals.denied_platforms': request}
            }
        )

        logger.info(f"❌ تم رفض منصة {platform} بواسطة المدير {denied_by}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل رفض الطلب: {e}")
        return False


def update_library_status(library_name: str, status_data: dict):
    """تحديث حالة مكتبة معينة"""
    try:
        db.settings.update_one(
            {'_id': 'library_settings'},
            {'$set': {f'library_status.{library_name}': status_data}}
        )
        logger.info(f"✅ تم تحديث حالة مكتبة {library_name}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة مكتبة {library_name}: {e}")
        return False


def get_library_status(library_name: str = None):
    """جلب حالة المكتبات"""
    try:
        settings = get_library_settings()
        if not settings:
            return {}

        if library_name:
            return settings.get('library_status', {}).get(library_name, {})
        else:
            return settings.get('library_status', {})
    except Exception as e:
        logger.error(f"❌ فشل جلب حالة المكتبات: {e}")
        return {}


def record_download_attempt(success: bool, speed: float = 0):
    """تسجيل محاولة تحميل لتتبع الإحصائيات"""
    try:
        db.settings.update_one(
            {'_id': 'library_settings'},
            {
                '$inc': {
                    'performance_metrics.total_downloads': 1,
                    'performance_metrics.successful_downloads': 1 if success else 0,
                    'performance_metrics.failed_downloads': 0 if success else 1
                },
                '$set': {
                    'performance_metrics.last_download': datetime.now()
                }
            }
        )

        # تحديث متوسط السرعة (إذا تم توفير سرعة)
        if speed > 0:
            settings = get_library_settings()
            current_avg = settings.get('performance_metrics', {}).get('avg_download_speed', 0)
            total_downloads = settings.get('performance_metrics', {}).get('total_downloads', 1)

            # حساب المتوسط الجديد
            new_avg = (current_avg * (total_downloads - 1) + speed) / total_downloads

            db.settings.update_one(
                {'_id': 'library_settings'},
                {'$set': {'performance_metrics.avg_download_speed': new_avg}}
            )

        return True
    except Exception as e:
        logger.error(f"❌ فشل تسجيل محاولة التحميل: {e}")
        return False


def get_performance_metrics():
    """جلب إحصائيات الأداء"""
    try:
        settings = get_library_settings()
        if not settings:
            return {}

        return settings.get('performance_metrics', {})
    except Exception as e:
        logger.error(f"❌ فشل جلب إحصائيات الأداء: {e}")
        return {}


def reset_performance_metrics():
    """إعادة تعيين إحصائيات الأداء"""
    try:
        db.settings.update_one(
            {'_id': 'library_settings'},
            {
                '$set': {
                    'performance_metrics.total_downloads': 0,
                    'performance_metrics.successful_downloads': 0,
                    'performance_metrics.failed_downloads': 0,
                    'performance_metrics.avg_download_speed': 0,
                    'performance_metrics.last_reset': datetime.now()
                }
            }
        )
        logger.info("✅ تم إعادة تعيين إحصائيات الأداء")
        return True
    except Exception as e:
        logger.error(f"❌ فشل إعادة تعيين الإحصائيات: {e}")
        return False
