import random
from datetime import datetime
from .base import users_collection
from config.logger import get_logger

# إنشاء logger instance
logger = get_logger(__name__)


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
