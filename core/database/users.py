from datetime import datetime
from .base import users_collection, ensure_db_connection, ADMIN_IDS

# استخدام logger من config
try:
    from config.logger import get_logger
except ImportError:
    import logging
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """التحقق من صلاحيات المدير"""
    return user_id in ADMIN_IDS


def add_user(user_id: int, username: str = None, full_name: str = None, language: str = 'ar'):
    """إضافة مستخدم جديد"""
    try:
        user_data = {
            'user_id': user_id,
            'username': username,
            'full_name': full_name,
            'language': language,
            'join_date': datetime.now(),
            'last_interaction': datetime.now(),
            'download_count': 0,
            'daily_downloads': [],
            'subscription_end': None
        }

        users_collection.update_one(
            {'user_id': user_id},
            {'$setOnInsert': user_data},
            upsert=True
        )
        logger.info(f"✅ تم إضافة/تحديث المستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل إضافة المستخدم: {e}")
        return False


def get_user(user_id: int):
    """جلب بيانات مستخدم"""
    if not ensure_db_connection():
        return None
    try:
        user = users_collection.find_one({'user_id': user_id})
        return user
    except Exception as e:
        logger.error(f"❌ فشل جلب بيانات المستخدم: {e}")
        return None


def get_all_users():
    """جلب جميع المستخدمين"""
    if not ensure_db_connection():
        return []
    try:
        users = list(users_collection.find())
        return users
    except Exception as e:
        logger.error(f"❌ فشل جلب المستخدمين: {e}")
        return []


def update_user_language(user_id: int, language: str):
    """تحديث لغة المستخدم"""
    try:
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'language': language}}
        )
        logger.info(f"✅ تم تحديث لغة المستخدم {user_id} إلى {language}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث اللغة: {e}")
        return False


def get_user_language(user_id: int) -> str:
    """جلب لغة المستخدم"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if user and 'language' in user:
            return user['language']
        return 'ar'
    except Exception as e:
        logger.error(f"❌ فشل جلب اللغة: {e}")
        return 'ar'


def update_user_interaction(user_id: int):
    """تحديث آخر تفاعل للمستخدم"""
    try:
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'last_interaction': datetime.now()}}
        )
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث التفاعل: {e}")
        return False


def delete_user(user_id: int):
    """حذف مستخدم"""
    try:
        result = users_collection.delete_one({'user_id': user_id})
        if result.deleted_count > 0:
            logger.info(f"✅ تم حذف المستخدم {user_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ فشل حذف المستخدم: {e}")
        return False


def get_user_stats(user_id: int):
    """جلب إحصائيات المستخدم"""
    try:
        from .subscriptions import is_subscribed
        from .downloads import get_daily_download_count

        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return None

        stats = {
            'total_downloads': user.get('download_count', 0),
            'daily_downloads': get_daily_download_count(user_id),
            'is_vip': is_subscribed(user_id),
            'join_date': user.get('join_date'),
            'subscription_end': user.get('subscription_end')
        }

        return stats
    except Exception as e:
        logger.error(f"❌ فشل جلب الإحصائيات: {e}")
        return None


def get_users_count() -> dict:
    """جلب عدد المستخدمين"""
    try:
        total = users_collection.count_documents({})
        vip = users_collection.count_documents({
            'subscription_end': {'$gt': datetime.now()}
        })

        return {
            'total': total,
            'vip': vip,
            'free': total - vip
        }
    except Exception as e:
        logger.error(f"❌ فشل جلب العدد: {e}")
        return {'total': 0, 'vip': 0, 'free': 0}
