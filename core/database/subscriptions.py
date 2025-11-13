from datetime import datetime
from .base import users_collection, settings_collection
from config.logger import get_logger

# إنشاء logger instance
logger = get_logger(__name__)


def is_subscribed(user_id: int) -> bool:
    """التحقق من اشتراك المستخدم"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if user and user.get('subscription_end'):
            if isinstance(user['subscription_end'], datetime):
                return user['subscription_end'] > datetime.now()
        return False
    except Exception as e:
        logger.error(f"❌ فشل التحقق من الاشتراك: {e}")
        return False


def add_subscription(user_id: int, subscription_end: datetime):
    """إضافة اشتراك للمستخدم"""
    try:
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'subscription_end': subscription_end}}
        )
        logger.info(f"✅ تمت إضافة اشتراك للمستخدم {user_id} حتى {subscription_end}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل إضافة الاشتراك: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
#  Global Settings (Subscription Control)
# ═══════════════════════════════════════════════════════════════

def get_global_settings():
    """جلب الإعدادات العامة للبوت"""
    try:
        if settings_collection is None:
            return None

        settings = settings_collection.find_one({'_id': 'global_settings'})

        # إنشاء الإعدادات الافتراضية إذا لم تكن موجودة
        if not settings:
            default_settings = {
                '_id': 'global_settings',
                'subscription_enabled': False,
                'welcome_broadcast_enabled': True,
                'last_updated': datetime.now()
            }
            settings_collection.insert_one(default_settings)
            logger.info("✅ تم إنشاء الإعدادات العامة الافتراضية")
            return default_settings

        return settings
    except Exception as e:
        logger.error(f"❌ فشل جلب الإعدادات العامة: {e}")
        return None


def set_subscription_enabled(enabled: bool):
    """تفعيل أو إيقاف نظام الاشتراك"""
    try:
        if settings_collection is None:
            return False

        settings_collection.update_one(
            {'_id': 'global_settings'},
            {
                '$set': {
                    'subscription_enabled': enabled,
                    'last_updated': datetime.now()
                }
            },
            upsert=True
        )

        status = "enabled" if enabled else "disabled"
        logger.info(f"✅ نظام الاشتراك تم {status}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة الاشتراك: {e}")
        return False


def set_welcome_broadcast_enabled(enabled: bool):
    """تفعيل أو إيقاف رسالة الترحيب عند تفعيل الاشتراك"""
    try:
        if settings_collection is None:
            return False

        settings_collection.update_one(
            {'_id': 'global_settings'},
            {
                '$set': {
                    'welcome_broadcast_enabled': enabled,
                    'last_updated': datetime.now()
                }
            },
            upsert=True
        )

        status = "enabled" if enabled else "disabled"
        logger.info(f"✅ رسالة الترحيب تم {status}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة رسالة الترحيب: {e}")
        return False


def is_subscription_enabled():
    """التحقق من حالة نظام الاشتراك"""
    try:
        settings = get_global_settings()
        if not settings:
            return False
        return settings.get('subscription_enabled', False)
    except Exception as e:
        logger.error(f"❌ فشل التحقق من حالة الاشتراك: {e}")
        return False


def is_welcome_broadcast_enabled():
    """التحقق من حالة رسالة الترحيب"""
    try:
        settings = get_global_settings()
        if not settings:
            return True  # الافتراضي: مفعل
        return settings.get('welcome_broadcast_enabled', True)
    except Exception as e:
        logger.error(f"❌ فشل التحقق من حالة رسالة الترحيب: {e}")
        return True


def set_subscription_price(price: float):
    """تعيين سعر الاشتراك"""
    try:
        if settings_collection is None:
            return False

        settings_collection.update_one(
            {'_id': 'global_settings'},
            {
                '$set': {
                    'subscription_price': price,
                    'last_updated': datetime.now()
                }
            },
            upsert=True
        )

        logger.info(f"✅ تم تعيين سعر الاشتراك إلى: ${price}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث سعر الاشتراك: {e}")
        return False


def get_subscription_price():
    """جلب سعر الاشتراك الحالي"""
    try:
        settings = get_global_settings()
        if not settings:
            return 3.0  # السعر الافتراضي
        return settings.get('subscription_price', 3.0)
    except Exception as e:
        logger.error(f"❌ فشل جلب سعر الاشتراك: {e}")
        return 3.0


def remove_subscription(user_id: int):
    """إلغاء اشتراك المستخدم"""
    try:
        users_collection.update_one(
            {'user_id': user_id},
            {'$unset': {'subscription_end': ""}}
        )
        logger.info(f"✅ تم إلغاء اشتراك المستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل إلغاء الاشتراك: {e}")
        return False
