import os
import logging
import random
import string
from pymongo import MongoClient
from datetime import datetime, timedelta

# ⭐ تحميل متغيرات البيئة
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# الاتصال بقاعدة البيانات
MONGODB_URI = os.getenv("MONGODB_URI")
ADMIN_IDS_STR = os.getenv("ADMIN_ID", "")

try:
    if not MONGODB_URI:
        raise ValueError("متغير البيئة MONGODB_URI غير موجود.")

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.server_info()

    db = client.telegram_bot
    users_collection = db.users

    logger.info("✅ تم الاتصال بقاعدة البيانات بنجاح.")
except Exception as e:
    logger.error(f"!!! خطأ في الاتصال بقاعدة البيانات: {e}")
    db = None
    users_collection = None

    # إرسال تقرير خطأ جسيم
    try:
        from utils import send_critical_log
        send_critical_log(f"فشل الاتصال بقاعدة البيانات MongoDB: {str(e)}", module="database.py")
    except:
        pass

def init_db():
    """التحقق من الاتصال بقاعدة البيانات"""
    if db is None or users_collection is None:
        logger.error("!!! قاعدة البيانات غير متصلة.")
        return False
    return True

def is_admin(user_id: int) -> bool:
    """التحقق من صلاحيات المدير"""
    admin_ids = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(',') if admin_id.strip()]
    return user_id in admin_ids

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
    try:
        user = users_collection.find_one({'user_id': user_id})
        return user
    except Exception as e:
        logger.error(f"❌ فشل جلب بيانات المستخدم: {e}")
        return None

def get_all_users():
    """جلب جميع المستخدمين"""
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
                # رسالة للمحيل
                referrer_message = (
                    f"🎉 **مبروك! حصلت على إحالة جديدة!**\n\n"
                    f"👥 تم تسجيل مستخدم جديد عبر رابطك: **{new_user_name}**\n"
                    f"🎁 **مكافأتك:** 10 فيديوهات بدون لوجو!\n"
                    f"💰 رصيدك الآن: {referrer.get('no_logo_credits', 0) + 10} فيديو بدون لوجو\n\n"
                    f"🚀 استمر في المشاركة واربح المزيد!"
                )
                bot.send_message(chat_id=referrer_id, text=referrer_message, parse_mode='Markdown')
                logger.info(f"📤 تم إرسال إشعار للمُحيل {referrer_id}")
            except Exception as e:
                logger.error(f"❌ فشل إرسال إشعار للمُحيل: {e}")
        
        # إرسال إشعار للمُحال (الشخص الجديد)
        if bot:
            try:
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
                bot.send_message(chat_id=new_user_id, text=referred_message, parse_mode='Markdown')
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
