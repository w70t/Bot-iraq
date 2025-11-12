import os
import logging
import random
import string
from pymongo import MongoClient
from datetime import datetime, timedelta

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# الاتصال بقاعدة البيانات
MONGODB_URI = os.getenv("MONGODB_URI")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")

# Parse ADMIN_IDS safely
try:
    ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip().isdigit()]
    if not ADMIN_IDS:
        logger.warning("⚠️ No valid ADMIN_IDs found in .env. Admin functions will be disabled.")
except (ValueError, AttributeError) as e:
    logger.error(f"❌ Failed to parse ADMIN_ID from .env: {e}")
    ADMIN_IDS = []

try:
    if not MONGODB_URI:
        raise ValueError("متغير البيئة MONGODB_URI غير موجود.")

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.server_info()

    db = client.telegram_bot
    users_collection = db.users
    settings_collection = db.settings

    logger.info("✅ تم الاتصال بقاعدة البيانات بنجاح.")
except Exception as e:
    logger.error(f"!!! خطأ في الاتصال بقاعدة البيانات: {e}")
    db = None
    users_collection = None
    settings_collection = None

    # إرسال تقرير خطأ جسيم
    try:
        from utils import send_critical_log
        send_critical_log(f"فشل الاتصال بقاعدة البيانات MongoDB: {str(e)}", module="database.py")
    except Exception as log_error:
        logger.error(f"فشل إرسال سجل الخطأ: {log_error}")

def init_db():
    """التحقق من الاتصال بقاعدة البيانات"""
    if db is None or users_collection is None:
        logger.error("!!! قاعدة البيانات غير متصلة.")
        return False
    return True

def ensure_db_connection():
    """التحقق من الاتصال بقاعدة البيانات مع إعادة المحاولة التلقائية"""
    global client, db, users_collection, settings_collection

    # إذا كانت المتغيرات غير مهيأة، محاولة إعادة الاتصال
    if db is None or users_collection is None or settings_collection is None:
        logger.warning("⚠️ Database connection lost, attempting reconnection...")
        try:
            # محاولة إعادة الاتصال
            if not MONGODB_URI:
                logger.error("❌ MONGODB_URI not configured")
                return False

            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            client.server_info()  # Test connection

            db = client.telegram_bot
            users_collection = db.users
            settings_collection = db.settings

            logger.info("✅ Database reconnection successful")
            return True
        except Exception as e:
            logger.error(f"❌ Database reconnection failed: {e}")
            try:
                from utils import send_critical_log
                send_critical_log(f"Database reconnection failed: {str(e)}", module="database.py")
            except:
                pass
            return False

    # التحقق من أن الاتصال ما زال حياً
    try:
        # Quick ping to verify connection is alive
        client.admin.command('ping')
        return True
    except Exception as e:
        logger.warning(f"⚠️ Database ping failed: {e}, attempting reconnection...")

        # محاولة إعادة الاتصال
        try:
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            client.server_info()  # Test connection

            db = client.telegram_bot
            users_collection = db.users
            settings_collection = db.settings

            logger.info("✅ Database reconnection successful after ping failure")
            return True
        except Exception as reconnect_error:
            logger.error(f"❌ Database reconnection failed: {reconnect_error}")
            try:
                from utils import send_critical_log
                send_critical_log(f"Database reconnection failed: {str(reconnect_error)}", module="database.py")
            except:
                pass
            return False

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

def increment_download_count(user_id: int):
    """زيادة عداد التحميلات"""
    try:
        today = datetime.now().date()
        
        users_collection.update_one(
            {'user_id': user_id},
            {
                '$inc': {'download_count': 1},
                '$push': {
                    'daily_downloads': {
                        'date': datetime.combine(today, datetime.min.time()),
                        'count': 1
                    }
                }
            }
        )
        logger.info(f"✅ تم زيادة عداد التحميلات للمستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل زيادة العداد: {e}")
        return False

def get_daily_download_count(user_id: int) -> int:
    """جلب عدد التحميلات اليومية"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return 0
        
        today = datetime.now().date()
        daily_downloads = user.get('daily_downloads', [])
        
        today_count = sum(
            1 for download in daily_downloads
            if isinstance(download.get('date'), datetime) and download['date'].date() == today
        )
        
        return today_count
    except Exception as e:
        logger.error(f"❌ فشل جلب العداد اليومي: {e}")
        return 0

def get_total_downloads_count() -> int:
    """جلب إجمالي التحميلات"""
    try:
        pipeline = [
            {'$group': {'_id': None, 'total': {'$sum': '$download_count'}}}
        ]
        result = list(users_collection.aggregate(pipeline))
        if result:
            return result[0]['total']
        return 0
    except Exception as e:
        logger.error(f"❌ فشل جلب الإجمالي: {e}")
        return 0

def reset_daily_downloads():
    """إعادة تعيين التحميلات اليومية (يتم تشغيله تلقائياً)"""
    try:
        yesterday = datetime.now() - timedelta(days=1)
        users_collection.update_many(
            {},
            {
                '$pull': {
                    'daily_downloads': {
                        'date': {'$lt': yesterday}
                    }
                }
            }
        )
        logger.info("✅ تم تنظيف السجلات القديمة")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تنظيف السجلات: {e}")
        return False

def get_user_stats(user_id: int):
    """جلب إحصائيات المستخدم"""
    try:
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

def set_logo_status(enabled: bool):
    """تفعيل/إيقاف اللوجو للجميع"""
    try:
        # حفظ الحالة في مستند خاص بالإعدادات
        db.settings.update_one(
            {'_id': 'logo_settings'},
            {'$set': {'enabled': enabled, 'updated_at': datetime.now()}},
            upsert=True
        )
        logger.info(f"✅ تم {'تفعيل' if enabled else 'إيقاف'} اللوجو")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة اللوجو: {e}")
        return False

def is_logo_enabled() -> bool:
    """التحقق من حالة اللوجو"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings:
            return settings.get('enabled', True)
        return True  # افتراضياً مفعّل
    except Exception as e:
        logger.error(f"❌ فشل جلب حالة اللوجو: {e}")
        return True

# ==================== نظام الإحالة ====================

def generate_referral_code(user_id: int) -> str:
    """توليد كود إحالة فريد للمستخدم"""
    try:
        # التحقق إذا كان المستخدم لديه كود بالفعل
        user = users_collection.find_one({'user_id': user_id})
        if user and user.get('referral_code'):
            return user['referral_code']
        
        # توليد كود جديد بصيغة REF_XXXXX
        code = f"REF_{user_id}_{random.randint(1000, 9999)}"
        
        # التأكد من عدم تكرار الكود
        while users_collection.find_one({'referral_code': code}):
            code = f"REF_{user_id}_{random.randint(1000, 9999)}"
        
        # حفظ الكود في قاعدة البيانات
        users_collection.update_one(
            {'user_id': user_id},
            {
                '$set': {
                    'referral_code': code,
                    'referral_count': 0,
                    'no_logo_credits': 0
                }
            },
            upsert=True
        )
        
        logger.info(f"✅ تم توليد كود إحالة للمستخدم {user_id}: {code}")
        return code
    except Exception as e:
        logger.error(f"❌ فشل توليد كود الإحالة: {e}")
        return None

def track_referral(referrer_code: str, new_user_id: int, bot=None) -> bool:
    """تسجيل إحالة جديدة مع إرسال إشعارات"""
    try:
        # البحث عن المستخدم المحيل بالكود
        referrer = users_collection.find_one({'referral_code': referrer_code})
        
        if not referrer:
            logger.warning(f"⚠️ كود إحالة غير صالح: {referrer_code}")
            return False
        
        referrer_id = referrer['user_id']
        
        # التحقق من عدم إحالة نفسه
        if referrer_id == new_user_id:
            logger.warning(f"⚠️ المستخدم {new_user_id} حاول إحالة نفسه")
            return False
        
        # التحقق من عدم تسجيل الإحالة مسبقاً
        existing_user = users_collection.find_one({'user_id': new_user_id})
        if existing_user and existing_user.get('referred_by'):
            logger.warning(f"⚠️ المستخدم {new_user_id} تم إحالته بالفعل")
            return False
        
        # جلب بيانات المستخدم الجديد للمُحال إليه
        new_user = users_collection.find_one({'user_id': new_user_id})
        new_user_name = new_user.get('full_name', 'مستخدم جديد') if new_user else 'مستخدم جديد'
        
        # تسجيل الإحالة للمستخدم الجديد
        users_collection.update_one(
            {'user_id': new_user_id},
            {
                '$set': {
                    'referred_by': referrer_id,
                    'referral_date': datetime.now()
                }
            },
            upsert=True
        )
        
        # زيادة عداد الإحالات للمحيل
        users_collection.update_one(
            {'user_id': referrer_id},
            {
                '$inc': {
                    'referral_count': 1,
                    'no_logo_credits': 10  # مكافأة 10 فيديوهات بدون لوجو
                }
            }
        )
        
        # إرسال إشعار للمُحيل
        if bot:
            try:
                from telegram import Bot
                bot_obj = Bot(token=bot._token)
                # رسالة للمحيل
                referrer_message = (
                    f"🎉 **مبروك! حصلت على إحالة جديدة!**\n\n"
                    f"👥 تم تسجيل مستخدم جديد عبر رابطك: **{new_user_name}**\n"
                    f"🎁 **مكافأتك:** 10 فيديوهات بدون لوجو!\n"
                    f"💰 رصيدك الآن: {referrer.get('no_logo_credits', 0) + 10} فيديو بدون لوجو\n\n"
                    f"🚀 استمر في المشاركة واربح المزيد!"
                )
                bot_obj.send_message(chat_id=referrer_id, text=referrer_message, parse_mode='Markdown')
                logger.info(f"📤 تم إرسال إشعار للمُحيل {referrer_id}")
            except Exception as e:
                logger.error(f"❌ فشل إرسال إشعار للمُحيل: {e}")

        # إرسال إشعار للمُحال (الشخص الجديد)
        if bot:
            try:
                from telegram import Bot
                bot_obj = Bot(token=bot._token)
                # جلب بيانات المُحيل
                referrer_name = referrer.get('full_name', 'صديقك')

                # رسالة للمُحال
                referred_message = (
                    f"🎉 **أهلاً وسهلاً!**\n\n"
                    f"شكراً لدخولك من خلال رابط **{referrer_name}** 🙏\n\n"
                    f"💡 **هل تريد أنت أيضاً الحصول على 10 نقاط مجانية؟**\n\n"
                    f"🎁 ببساطة:\n"
                    f"1️⃣ استخدم /referral للحصول على رابطك الخاص\n"
                    f"2️⃣ شارك رابطك مع أصدقائك\n"
                    f"3️⃣ احصل على **10 فيديوهات بدون لوجو** لكل صديق يسجل!\n\n"
                    f"⭐ **النقاط = فيديوهات بدون لوجو مجاناً!**\n\n"
                    f"🚀 ابدأ الآن واربح نقاط غير محدودة!"
                )
                bot_obj.send_message(chat_id=new_user_id, text=referred_message, parse_mode='Markdown')
                logger.info(f"📤 تم إرسال رسالة ترحيب للمُحال {new_user_id}")
            except Exception as e:
                logger.error(f"❌ فشل إرسال رسالة للمُحال: {e}")
        
        logger.info(f"✅ تم تسجيل إحالة: {referrer_id} أحال {new_user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تسجيل الإحالة: {e}")
        return False

def add_referral_points(user_id: int, points: int = 5):
    """إضافة نقاط إحالة (فيديوهات بدون لوجو) للمستخدم"""
    try:
        users_collection.update_one(
            {'user_id': user_id},
            {'$inc': {'no_logo_credits': points}}
        )
        logger.info(f"✅ تمت إضافة {points} نقطة للمستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل إضافة النقاط: {e}")
        return False

def use_no_logo_credit(user_id: int) -> bool:
    """استخدام نقطة واحدة من رصيد الفيديوهات بدون لوجو"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        
        if not user:
            return False
        
        current_credits = user.get('no_logo_credits', 0)
        
        if current_credits <= 0:
            return False
        
        # خصم نقطة واحدة
        users_collection.update_one(
            {'user_id': user_id},
            {'$inc': {'no_logo_credits': -1}}
        )
        
        logger.info(f"✅ تم خصم نقطة من رصيد المستخدم {user_id}، المتبقي: {current_credits - 1}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل خصم النقطة: {e}")
        return False

def get_referral_stats(user_id: int) -> dict:
    """جلب إحصائيات الإحالة للمستخدم"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        
        if not user:
            return {
                'referral_code': None,
                'referral_count': 0,
                'no_logo_credits': 0,
                'referred_by': None
            }
        
        return {
            'referral_code': user.get('referral_code'),
            'referral_count': user.get('referral_count', 0),
            'no_logo_credits': user.get('no_logo_credits', 0),
            'referred_by': user.get('referred_by')
        }
    except Exception as e:
        logger.error(f"❌ فشل جلب إحصائيات الإحالة: {e}")
        return {
            'referral_code': None,
            'referral_count': 0,
            'no_logo_credits': 0,
            'referred_by': None
        }

def get_no_logo_credits(user_id: int) -> int:
    """جلب رصيد الفيديوهات بدون لوجو"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return 0
        return user.get('no_logo_credits', 0)
    except Exception as e:
        logger.error(f"❌ فشل جلب رصيد النقاط: {e}")
        return 0

# ==================== إدارة حركات اللوجو ====================

def set_logo_animation(animation_type: str):
    """تعيين نوع حركة اللوجو"""
    try:
        valid_types = ['static', 'corner_rotation', 'bounce', 'slide', 'fade', 'zoom']
        
        if animation_type not in valid_types:
            animation_type = 'static'  # افتراضي
        
        db.settings.update_one(
            {'_id': 'logo_settings'},
            {
                '$set': {
                    'animation_type': animation_type,
                    'updated_at': datetime.now()
                }
            },
            upsert=True
        )
        
        logger.info(f"✅ تم تعيين حركة اللوجو إلى: {animation_type}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تعيين حركة اللوجو: {e}")
        return False

def get_logo_animation() -> str:
    """جلب نوع حركة اللوجو الحالية"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings and 'animation_type' in settings:
            return settings['animation_type']
        return 'static'  # افتراضي
    except Exception as e:
        logger.error(f"❌ فشل جلب حركة اللوجو: {e}")
        return 'static'

# ==================== إعدادات اللوجو المتقدمة ====================

def set_logo_position(position: str):
    """تعيين موضع اللوجو"""
    try:
        valid_positions = [
            'top_right',      # زاوية يمين أعلى
            'top_left',       # زاوية يسار أعلى
            'bottom_right',   # زاوية يمين أسفل
            'bottom_left',    # زاوية يسار أسفل
            'center',         # وسط الشاشة
            'top_center',     # وسط أعلى
            'bottom_center',  # وسط أسفل
            'center_right',   # وسط يمين
            'center_left'     # وسط يسار
        ]
        
        if position not in valid_positions:
            position = 'top_right'  # افتراضي
        
        db.settings.update_one(
            {'_id': 'logo_settings'},
            {
                '$set': {
                    'position': position,
                    'updated_at': datetime.now()
                }
            },
            upsert=True
        )
        
        logger.info(f"✅ تم تعيين موضع اللوجو إلى: {position}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تعيين موضع اللوجو: {e}")
        return False

def get_logo_position() -> str:
    """جلب موضع اللوجو الحالي"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings and 'position' in settings:
            return settings['position']
        return 'top_right'  # افتراضي
    except Exception as e:
        logger.error(f"❌ فشل جلب موضع اللوجو: {e}")
        return 'top_right'

def set_logo_size(size: str):
    """تعيين حجم اللوجو"""
    try:
        valid_sizes = {
            'small': 100,   # صغير
            'medium': 150,  # متوسط
            'large': 200    # كبير
        }
        
        if size not in valid_sizes:
            size = 'medium'  # افتراضي
        
        db.settings.update_one(
            {'_id': 'logo_settings'},
            {
                '$set': {
                    'size': size,
                    'size_pixels': valid_sizes[size],
                    'updated_at': datetime.now()
                }
            },
            upsert=True
        )
        
        logger.info(f"✅ تم تعيين حجم اللوجو إلى: {size} ({valid_sizes[size]}px)")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تعيين حجم اللوجو: {e}")
        return False

def get_logo_size() -> tuple:
    """جلب حجم اللوجو الحالي (اسم، بكسل)"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings and 'size' in settings:
            return settings['size'], settings.get('size_pixels', 150)
        return 'medium', 150  # افتراضي
    except Exception as e:
        logger.error(f"❌ فشل جلب حجم اللوجو: {e}")
        return 'medium', 150

def set_logo_opacity(opacity: int):
    """تعيين شفافية اللوجو (40-90)"""
    try:
        # التحقق من القيمة
        if opacity < 40:
            opacity = 40
        elif opacity > 90:
            opacity = 90
        
        db.settings.update_one(
            {'_id': 'logo_settings'},
            {
                '$set': {
                    'opacity': opacity,
                    'opacity_decimal': opacity / 100.0,
                    'updated_at': datetime.now()
                }
            },
            upsert=True
        )
        
        logger.info(f"✅ تم تعيين شفافية اللوجو إلى: {opacity}%")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تعيين شفافية اللوجو: {e}")
        return False

def get_logo_opacity() -> tuple:
    """جلب شفافية اللوجو الحالية (نسبة، عشري)"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings and 'opacity' in settings:
            return settings['opacity'], settings.get('opacity_decimal', 0.7)
        return 70, 0.7  # افتراضي
    except Exception as e:
        logger.error(f"❌ فشل جلب شفافية اللوجو: {e}")
        return 70, 0.7

def get_all_logo_settings() -> dict:
    """جلب جميع إعدادات اللوجو"""
    try:
        animation = get_logo_animation()
        position = get_logo_position()
        size_name, size_px = get_logo_size()
        opacity_pct, opacity_dec = get_logo_opacity()
        target_id, target_name = get_logo_target()
        
        return {
            'animation': animation,
            'position': position,
            'size_name': size_name,
            'size_pixels': size_px,
            'opacity_percent': opacity_pct,
            'opacity_decimal': opacity_dec,
            'target_id': target_id,
            'target_name': target_name
        }
    except Exception as e:
        logger.error(f"❌ فشل جلب إعدادات اللوجو: {e}")
        return {
            'animation': 'corner_rotation',
            'position': 'top_right',
            'size_name': 'medium',
            'size_pixels': 150,
            'opacity_percent': 70,
            'opacity_decimal': 0.7,
            'target_id': 'free_only',
            'target_name': 'المستخدمون العاديون فقط'
        }


# ====================================
# إعدادات الفئة المستهدفة للوجو
# ====================================

def set_logo_target(target: str):
    """
    تعيين الفئة المستهدفة لتطبيق اللوجو
    
    Args:
        target: خيارات شاملة تشمل جميع أنواع المستخدمين
    """
    try:
        # قائمة شاملة بجميع الخيارات المتاحة
        valid_targets = [
            'free_with_points',    # العاديون (مع النقاط)
            'free_no_points',      # العاديون (بدون النقاط)
            'free_all',            # جميع العاديون
            'vip_with_points',     # VIP (مع النقاط)
            'vip_no_points',       # VIP (بدون النقاط)
            'vip_all',             # جميع VIP
            'everyone_with_points', # الجميع (مع النقاط)
            'everyone_no_points',  # الجميع (بدون النقاط)
            'everyone_all',        # الجميع (الجميع)
            'no_credits_only',     # المستخدمون بدون نقاط فقط
            'everyone_except_no_credits'  # الجميع عدا من لديهم نقاط
        ]
        
        if target not in valid_targets:
            logger.warning(f"⚠️ فئة مستهدفة غير صحيحة: {target}, استخدام free_all")
            target = 'free_all'
            
        db.settings.update_one(
            {'_id': 'logo_settings'},
            {'$set': {'target': target}},
            upsert=True
        )
        
        target_names = {
            'free_with_points': 'العاديون - يظهر للجميع (لا يهم النقاط)',
            'free_no_points': 'العاديون - فقط من ليس لديهم نقاط',
            'free_all': 'جميع العاديون',
            'vip_with_points': 'VIP - يظهر للجميع (لا يهم النقاط)',
            'vip_no_points': 'VIP - فقط من ليس لديهم نقاط',
            'vip_all': 'جميع VIP',
            'everyone_with_points': 'الجميع - يظهر للجميع (لا يهم النقاط)',
            'everyone_no_points': 'الجميع - فقط من ليس لديهم نقاط',
            'everyone_all': 'الجميع',
            'no_credits_only': 'المستخدمون بدون نقاط فقط',
            'everyone_except_no_credits': 'الجميع عدا من لديهم نقاط'
        }
        logger.info(f"✅ تم تعيين الفئة المستهدفة للوجو إلى: {target_names[target]}")
    except Exception as e:
        logger.error(f"❌ فشل تعيين الفئة المستهدفة: {e}")

def get_logo_target() -> tuple:
    """
    جلب الفئة المستهدفة الحالية لتطبيق اللوجو
    
    Returns:
        tuple: (target_id, target_name_ar)
    """
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        target = settings.get('target', 'free_all') if settings else 'free_all'
        
        # التحقق من صحة الخيار، إذا لم يكن صحيحاً استخدم القيمة الافتراضية
        valid_targets = [
            'free_with_points', 'free_no_points', 'free_all',
            'vip_with_points', 'vip_no_points', 'vip_all',
            'everyone_with_points', 'everyone_no_points', 'everyone_all',
            'no_credits_only', 'everyone_except_no_credits'
        ]
        
        if target not in valid_targets:
            target = 'free_all'
            
        target_names = {
            'free_with_points': 'العاديون - يظهر للجميع (لا يهم النقاط)',
            'free_no_points': 'العاديون - فقط من ليس لديهم نقاط',
            'free_all': 'جميع العاديون',
            'vip_with_points': 'VIP - يظهر للجميع (لا يهم النقاط)',
            'vip_no_points': 'VIP - فقط من ليس لديهم نقاط',
            'vip_all': 'جميع VIP',
            'everyone_with_points': 'الجميع - يظهر للجميع (لا يهم النقاط)',
            'everyone_no_points': 'الجميع - فقط من ليس لديهم نقاط',
            'everyone_all': 'الجميع',
            'no_credits_only': 'المستخدمون بدون نقاط فقط',
            'everyone_except_no_credits': 'الجميع عدا من لديهم نقاط'
        }
        
        return target, target_names.get(target, 'جميع العاديون')
    except Exception as e:
        logger.error(f"❌ فشل جلب الفئة المستهدفة: {e}")
        return 'free_only', 'المستخدمون العاديون فقط'

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
            'youtube', 'facebook', 'instagram', 'tiktok', 
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
                'youtube', 'facebook', 'instagram', 'tiktok', 
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
            'youtube', 'facebook', 'instagram', 'tiktok', 
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


# ═══════════════════════════════════════════════════════════════
#  Global Settings (Subscription Control) - Mission 5
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


# ═══════════════════════════════════════════════════════════════
#  Mission 10: Download Tracking & Admin Logs
# ═══════════════════════════════════════════════════════════════

# إنشاء مجموعة التحميلات
try:
    downloads_collection = db.downloads if db is not None else None
    error_reports_collection = db.error_reports if db is not None else None
except Exception as e:
    logger.error(f"❌ فشل إنشاء مجموعة التحميلات: {e}")
    downloads_collection = None
    error_reports_collection = None


def track_download(
    user_id: int,
    platform: str,
    mode: str,
    quality: str = None,
    format: str = None,
    status: str = 'completed',
    url: str = None,
    file_size: int = 0,
    error_msg: str = None
):
    """
    تتبع تحميل مفصل

    Args:
        user_id: معرف المستخدم
        platform: المنصة (youtube/instagram/facebook)
        mode: الوضع (video/audio)
        quality: الجودة (360/720/1080) للفيديو
        format: الصيغة (mp3/m4a) للصوت
        status: الحالة (completed/canceled/failed)
        url: رابط التحميل
        file_size: حجم الملف بالبايت
        error_msg: رسالة الخطأ إن وجدت
    """
    try:
        if downloads_collection is None:
            logger.warning("⚠️ مجموعة التحميلات غير متاحة")
            return False

        download_data = {
            'user_id': user_id,
            'platform': platform,
            'mode': mode,
            'quality': quality,
            'format': format,
            'status': status,
            'url': url,
            'file_size': file_size,
            'error_msg': error_msg,
            'timestamp': datetime.now(),
            'date': datetime.now().date()
        }

        downloads_collection.insert_one(download_data)

        # تحديث عداد التحميلات للمستخدم
        increment_download_count(user_id)

        logger.info(f"✅ تم تتبع التحميل: {user_id} - {platform} - {mode} - {status}")
        return True

    except Exception as e:
        logger.error(f"❌ فشل تتبع التحميل: {e}")
        return False


def get_user_downloads(user_id: int, limit: int = 50):
    """جلب سجل تحميلات المستخدم"""
    try:
        if downloads_collection is None:
            return []

        downloads = list(downloads_collection.find(
            {'user_id': user_id}
        ).sort('timestamp', -1).limit(limit))

        return downloads
    except Exception as e:
        logger.error(f"❌ فشل جلب تحميلات المستخدم: {e}")
        return []


def get_download_stats(start_date=None, end_date=None):
    """
    جلب إحصائيات التحميلات للأدمن

    Args:
        start_date: تاريخ البداية (datetime)
        end_date: تاريخ النهاية (datetime)

    Returns:
        dict: إحصائيات التحميلات
    """
    try:
        if downloads_collection is None:
            return {}

        # تحديد نطاق التاريخ
        query = {}
        if start_date or end_date:
            query['timestamp'] = {}
            if start_date:
                query['timestamp']['$gte'] = start_date
            if end_date:
                query['timestamp']['$lte'] = end_date

        # جلب جميع التحميلات في النطاق
        downloads = list(downloads_collection.find(query))

        # حساب الإحصائيات
        total_downloads = len(downloads)
        completed = len([d for d in downloads if d.get('status') == 'completed'])
        canceled = len([d for d in downloads if d.get('status') == 'canceled'])
        failed = len([d for d in downloads if d.get('status') == 'failed'])

        # إحصائيات حسب الوضع
        video_downloads = len([d for d in downloads if d.get('mode') == 'video'])
        audio_downloads = len([d for d in downloads if d.get('mode') == 'audio'])

        # إحصائيات حسب المنصة
        platforms = {}
        for download in downloads:
            platform = download.get('platform', 'unknown')
            platforms[platform] = platforms.get(platform, 0) + 1

        # أعلى المستخدمين تحميلاً
        user_downloads = {}
        for download in downloads:
            user_id = download.get('user_id')
            if user_id:
                user_downloads[user_id] = user_downloads.get(user_id, 0) + 1

        top_users = sorted(user_downloads.items(), key=lambda x: x[1], reverse=True)[:10]

        stats = {
            'total_downloads': total_downloads,
            'completed': completed,
            'canceled': canceled,
            'failed': failed,
            'video_downloads': video_downloads,
            'audio_downloads': audio_downloads,
            'platforms': platforms,
            'top_users': top_users,
            'success_rate': (completed / total_downloads * 100) if total_downloads > 0 else 0
        }

        return stats

    except Exception as e:
        logger.error(f"❌ فشل جلب إحصائيات التحميلات: {e}")
        return {}


def get_daily_download_stats():
    """جلب إحصائيات التحميلات اليومية"""
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = datetime.now()

        return get_download_stats(start_date=today_start, end_date=today_end)
    except Exception as e:
        logger.error(f"❌ فشل جلب إحصائيات اليوم: {e}")
        return {}


def generate_daily_report():
    """
    توليد تقرير يومي شامل

    Returns:
        str: نص التقرير بصيغة Markdown
    """
    try:
        stats = get_daily_download_stats()

        if not stats or stats.get('total_downloads', 0) == 0:
            return (
                "📊 **تقرير يومي - Daily Report**\n\n"
                f"📅 التاريخ / Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
                "ℹ️ لا توجد تحميلات اليوم\n"
                "No downloads today"
            )

        # بناء التقرير
        report = (
            "📊 **تقرير التحميلات اليومي / Daily Downloads Report**\n"
            "═════════════════════════════════════\n\n"
            f"📅 **التاريخ / Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"📥 **إجمالي التحميلات / Total Downloads:** {stats['total_downloads']}\n"
            f"✅ **مكتملة / Completed:** {stats['completed']}\n"
            f"❌ **ملغاة / Canceled:** {stats['canceled']}\n"
            f"⚠️ **فاشلة / Failed:** {stats['failed']}\n"
            f"📈 **معدل النجاح / Success Rate:** {stats['success_rate']:.1f}%\n\n"
            "─────────────────────────────────────\n\n"
            f"🎬 **تحميلات فيديو / Video Downloads:** {stats['video_downloads']}\n"
            f"🎧 **تحميلات صوت / Audio Downloads:** {stats['audio_downloads']}\n\n"
            "─────────────────────────────────────\n\n"
            "🌐 **المنصات / Platforms:**\n"
        )

        # إضافة إحصائيات المنصات
        for platform, count in stats['platforms'].items():
            report += f"   • {platform.capitalize()}: {count}\n"

        # إضافة أعلى المستخدمين
        if stats['top_users']:
            report += "\n─────────────────────────────────────\n\n"
            report += "👥 **أعلى المستخدمين / Top Users:**\n"
            for idx, (user_id, count) in enumerate(stats['top_users'][:5], 1):
                report += f"   {idx}. User {user_id}: {count} downloads\n"

        report += "\n═════════════════════════════════════\n"
        report += f"⏰ **وقت التقرير / Report Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return report

    except Exception as e:
        logger.error(f"❌ فشل توليد التقرير اليومي: {e}")
        return "❌ فشل توليد التقرير / Failed to generate report"


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
#  Error Reporting System
# ═══════════════════════════════════════════════════════════════

def create_error_report(user_id: int, username: str, url: str, error_type: str, error_message: str):
    """
    إنشاء بلاغ خطأ جديد

    Args:
        user_id: معرف المستخدم
        username: اسم المستخدم
        url: رابط الفيديو الذي فشل
        error_type: نوع الخطأ (مثل: TimedOut, NetworkError, etc.)
        error_message: رسالة الخطأ التفصيلية
    """
    try:
        if error_reports_collection is None:
            logger.warning("⚠️ مجموعة البلاغات غير متاحة")
            return None

        report_data = {
            'user_id': user_id,
            'username': username,
            'url': url,
            'error_type': error_type,
            'error_message': error_message,
            'status': 'pending',  # pending, resolved
            'created_at': datetime.now(),
            'resolved_at': None,
            'admin_note': None
        }

        result = error_reports_collection.insert_one(report_data)
        logger.info(f"✅ تم إنشاء بلاغ خطأ: {result.inserted_id}")

        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"❌ فشل إنشاء بلاغ الخطأ: {e}")
        return None


def get_pending_error_reports(limit: int = 50):
    """جلب البلاغات المعلقة (غير المحلولة)"""
    try:
        if error_reports_collection is None:
            return []

        reports = list(error_reports_collection.find(
            {'status': 'pending'}
        ).sort('created_at', -1).limit(limit))

        return reports
    except Exception as e:
        logger.error(f"❌ فشل جلب البلاغات المعلقة: {e}")
        return []


def get_all_error_reports(limit: int = 100):
    """جلب جميع البلاغات (معلقة ومحلولة)"""
    try:
        if error_reports_collection is None:
            return []

        reports = list(error_reports_collection.find().sort('created_at', -1).limit(limit))

        return reports
    except Exception as e:
        logger.error(f"❌ فشل جلب البلاغات: {e}")
        return []


def resolve_error_report(report_id: str, admin_note: str = None):
    """
    تحديد بلاغ كـ "محلول"

    Args:
        report_id: معرف البلاغ
        admin_note: ملاحظة اختيارية من المدير
    """
    try:
        if error_reports_collection is None:
            return False

        from bson.objectid import ObjectId

        update_data = {
            'status': 'resolved',
            'resolved_at': datetime.now()
        }

        if admin_note:
            update_data['admin_note'] = admin_note

        result = error_reports_collection.update_one(
            {'_id': ObjectId(report_id)},
            {'$set': update_data}
        )

        if result.modified_count > 0:
            logger.info(f"✅ تم حل البلاغ: {report_id}")
            return True
        else:
            logger.warning(f"⚠️ لم يتم العثور على البلاغ: {report_id}")
            return False
    except Exception as e:
        logger.error(f"❌ فشل حل البلاغ: {e}")
        return False


def get_error_report_by_id(report_id: str):
    """جلب بلاغ محدد بواسطة المعرف"""
    try:
        if error_reports_collection is None:
            return None

        from bson.objectid import ObjectId

        report = error_reports_collection.find_one({'_id': ObjectId(report_id)})

        return report
    except Exception as e:
        logger.error(f"❌ فشل جلب البلاغ: {e}")
        return None


def delete_error_report(report_id: str):
    """حذف بلاغ"""
    try:
        if error_reports_collection is None:
            return False

        from bson.objectid import ObjectId

        result = error_reports_collection.delete_one({'_id': ObjectId(report_id)})

        if result.deleted_count > 0:
            logger.info(f"✅ تم حذف البلاغ: {report_id}")
            return True
        else:
            logger.warning(f"⚠️ لم يتم العثور على البلاغ: {report_id}")
            return False
    except Exception as e:
        logger.error(f"❌ فشل حذف البلاغ: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
#  Download Success Rate Tracking
# ═══════════════════════════════════════════════════════════════

def track_download_success(user_id: int, success: bool):
    """تتبع نجاح/فشل التحميلات"""
    try:
        if users_collection is None:
            return False

        users_collection.update_one(
            {'user_id': user_id},
            {
                '$inc': {
                    'download_success_count' if success else 'download_fail_count': 1
                },
                '$setOnInsert': {
                    'download_success_count': 0,
                    'download_fail_count': 0
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"❌ فشل تتبع حالة التحميل: {e}")
        return False


def get_download_success_rate() -> float:
    """حساب معدل نجاح التحميلات"""
    try:
        if users_collection is None:
            return 0.0

        pipeline = [
            {
                '$group': {
                    '_id': None,
                    'total_success': {'$sum': '$download_success_count'},
                    'total_fail': {'$sum': '$download_fail_count'}
                }
            }
        ]
        result = list(users_collection.aggregate(pipeline))

        if result and len(result) > 0:
            success = result[0].get('total_success', 0)
            fail = result[0].get('total_fail', 0)
            total = success + fail

            if total > 0:
                return (success / total * 100)

        return 0.0
    except Exception as e:
        logger.error(f"❌ فشل حساب معدل النجاح: {e}")
        return 0.0


def get_user_download_stats(user_id: int) -> dict:
    """جلب إحصائيات التحميل للمستخدم"""
    try:
        if users_collection is None:
            return {'success': 0, 'fail': 0, 'rate': 0.0}

        user = users_collection.find_one({'user_id': user_id})

        if not user:
            return {'success': 0, 'fail': 0, 'rate': 0.0}

        success = user.get('download_success_count', 0)
        fail = user.get('download_fail_count', 0)
        total = success + fail

        rate = (success / total * 100) if total > 0 else 0.0

        return {
            'success': success,
            'fail': fail,
            'total': total,
            'rate': rate
        }
    except Exception as e:
        logger.error(f"❌ فشل جلب إحصائيات المستخدم: {e}")
        return {'success': 0, 'fail': 0, 'rate': 0.0}
