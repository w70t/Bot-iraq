import random
import traceback
from datetime import datetime
from .base import users_collection
from config.logger import get_logger

# إنشاء logger instance
logger = get_logger(__name__)


# ==================== نظام الإحالة ====================

def generate_referral_code(user_id: int) -> str:
    """
    توليد كود إحالة فريد للمستخدم

    Args:
        user_id: معرف المستخدم في تليجرام

    Returns:
        str: كود الإحالة أو None في حالة الخطأ
    """
    function_name = "generate_referral_code"
    logger.info(f"🔵 [{function_name}] بدء التنفيذ للمستخدم: {user_id}")

    try:
        # التحقق من صحة user_id
        if not user_id or not isinstance(user_id, int):
            logger.error(f"❌ [{function_name}] خطأ: user_id غير صالح: {user_id}")
            return None

        logger.debug(f"🔍 [{function_name}] البحث عن المستخدم {user_id} في قاعدة البيانات...")

        # التحقق إذا كان المستخدم لديه كود بالفعل
        user = users_collection.find_one({'user_id': user_id})

        if user and user.get('referral_code'):
            existing_code = user['referral_code']
            logger.info(f"✅ [{function_name}] المستخدم {user_id} لديه كود موجود: {existing_code}")
            return existing_code

        logger.debug(f"🔄 [{function_name}] توليد كود جديد للمستخدم {user_id}...")

        # توليد كود جديد بصيغة REF_XXXXX
        max_attempts = 10
        attempt = 0
        code = None

        while attempt < max_attempts:
            attempt += 1
            code = f"REF_{user_id}_{random.randint(1000, 9999)}"

            logger.debug(f"🎲 [{function_name}] محاولة {attempt}/{max_attempts}: توليد الكود {code}")

            # التأكد من عدم تكرار الكود
            existing = users_collection.find_one({'referral_code': code})
            if not existing:
                logger.debug(f"✅ [{function_name}] الكود {code} فريد، متابعة الحفظ...")
                break
            else:
                logger.warning(f"⚠️ [{function_name}] الكود {code} مكرر، إعادة المحاولة...")
                code = None

        if not code:
            logger.error(f"❌ [{function_name}] فشل توليد كود فريد بعد {max_attempts} محاولة للمستخدم {user_id}")
            return None

        logger.debug(f"💾 [{function_name}] حفظ الكود {code} في قاعدة البيانات للمستخدم {user_id}...")

        # حفظ الكود في قاعدة البيانات
        result = users_collection.update_one(
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

        if result.acknowledged:
            logger.info(f"✅ [{function_name}] نجح! تم توليد وحفظ كود إحالة للمستخدم {user_id}: {code}")
            return code
        else:
            logger.error(f"❌ [{function_name}] فشل حفظ الكود في قاعدة البيانات للمستخدم {user_id}")
            return None

    except Exception as e:
        logger.error(f"❌ [{function_name}] خطأ حرج للمستخدم {user_id}: {type(e).__name__}: {str(e)}")
        logger.error(f"📍 [{function_name}] Stack trace:\n{traceback.format_exc()}")
        return None


async def track_referral(referrer_code: str, new_user_id: int, bot=None) -> bool:
    """
    تسجيل إحالة جديدة مع إرسال إشعارات

    Args:
        referrer_code: كود الإحالة الخاص بالمحيل
        new_user_id: معرف المستخدم الجديد
        bot: كائن البوت لإرسال الإشعارات (اختياري)

    Returns:
        bool: True في حالة النجاح، False في حالة الفشل
    """
    function_name = "track_referral"
    logger.info(f"🔵 [{function_name}] بدء تتبع إحالة - الكود: {referrer_code}, المستخدم الجديد: {new_user_id}")

    try:
        # التحقق من صحة المدخلات
        if not referrer_code or not isinstance(referrer_code, str):
            logger.error(f"❌ [{function_name}] خطأ: referrer_code غير صالح: {referrer_code}")
            return False

        if not new_user_id or not isinstance(new_user_id, int):
            logger.error(f"❌ [{function_name}] خطأ: new_user_id غير صالح: {new_user_id}")
            return False

        logger.debug(f"🔍 [{function_name}] البحث عن المستخدم المحيل بالكود: {referrer_code}...")

        # البحث عن المستخدم المحيل بالكود
        referrer = users_collection.find_one({'referral_code': referrer_code})

        if not referrer:
            logger.warning(f"⚠️ [{function_name}] كود إحالة غير موجود في قاعدة البيانات: {referrer_code}")
            return False

        referrer_id = referrer.get('user_id')
        referrer_name = referrer.get('full_name', 'مستخدم')

        if not referrer_id:
            logger.error(f"❌ [{function_name}] خطأ: المحيل لا يملك user_id صالح في قاعدة البيانات")
            return False

        logger.info(f"✅ [{function_name}] تم العثور على المحيل - ID: {referrer_id}, الاسم: {referrer_name}")

        # التحقق من عدم إحالة نفسه
        if referrer_id == new_user_id:
            logger.warning(f"⚠️ [{function_name}] محاولة إحالة ذاتية! المستخدم {new_user_id} حاول إحالة نفسه")
            return False

        logger.debug(f"🔍 [{function_name}] التحقق من حالة المستخدم الجديد {new_user_id}...")

        # التحقق من عدم تسجيل الإحالة مسبقاً
        existing_user = users_collection.find_one({'user_id': new_user_id})
        if existing_user and existing_user.get('referred_by'):
            previous_referrer = existing_user.get('referred_by')
            logger.warning(f"⚠️ [{function_name}] المستخدم {new_user_id} تم إحالته بالفعل من قبل المستخدم {previous_referrer}")
            return False

        # جلب بيانات المستخدم الجديد
        new_user = users_collection.find_one({'user_id': new_user_id})
        new_user_name = new_user.get('full_name', 'مستخدم جديد') if new_user else 'مستخدم جديد'

        logger.info(f"👤 [{function_name}] بيانات المستخدم الجديد - ID: {new_user_id}, الاسم: {new_user_name}")
        logger.debug(f"💾 [{function_name}] تسجيل الإحالة في قاعدة البيانات...")

        # تسجيل الإحالة للمستخدم الجديد
        result_referred = users_collection.update_one(
            {'user_id': new_user_id},
            {
                '$set': {
                    'referred_by': referrer_id,
                    'referral_date': datetime.now()
                }
            },
            upsert=True
        )

        if not result_referred.acknowledged:
            logger.error(f"❌ [{function_name}] فشل تسجيل الإحالة للمستخدم الجديد {new_user_id}")
            return False

        logger.debug(f"💰 [{function_name}] تحديث رصيد المحيل {referrer_id}...")

        # زيادة عداد الإحالات للمحيل
        result_referrer = users_collection.update_one(
            {'user_id': referrer_id},
            {
                '$inc': {
                    'referral_count': 1,
                    'no_logo_credits': 10  # مكافأة 10 فيديوهات بدون لوجو
                }
            }
        )

        if not result_referrer.acknowledged:
            logger.error(f"❌ [{function_name}] فشل تحديث رصيد المحيل {referrer_id}")
            # لا نرجع False لأن الإحالة تم تسجيلها

        # حساب الرصيد الجديد
        updated_referrer = users_collection.find_one({'user_id': referrer_id})
        new_balance = updated_referrer.get('no_logo_credits', 10) if updated_referrer else 10
        new_referral_count = updated_referrer.get('referral_count', 1) if updated_referrer else 1

        logger.info(f"💰 [{function_name}] رصيد المحيل {referrer_id} الجديد: {new_balance} فيديو، عدد الإحالات: {new_referral_count}")

        # إرسال إشعار للمُحيل
        if bot:
            logger.debug(f"📤 [{function_name}] إرسال إشعار للمُحيل {referrer_id}...")
            try:
                # رسالة للمحيل
                referrer_message = (
                    f"🎉 **مبروك! حصلت على إحالة جديدة!**\n\n"
                    f"👥 تم تسجيل مستخدم جديد عبر رابطك: **{new_user_name}**\n"
                    f"🎁 **مكافأتك:** 10 فيديوهات بدون لوجو!\n"
                    f"💰 رصيدك الآن: **{new_balance}** فيديو بدون لوجو\n"
                    f"📊 إجمالي إحالاتك: **{new_referral_count}** إحالة\n\n"
                    f"🚀 استمر في المشاركة واربح المزيد!"
                )

                await bot.send_message(
                    chat_id=referrer_id,
                    text=referrer_message,
                    parse_mode='Markdown'
                )
                logger.info(f"✅ [{function_name}] تم إرسال إشعار للمُحيل {referrer_id} بنجاح")

            except Exception as e:
                logger.error(f"❌ [{function_name}] فشل إرسال إشعار للمُحيل {referrer_id}: {type(e).__name__}: {str(e)}")
                logger.debug(f"📍 [{function_name}] تفاصيل خطأ الإشعار:\n{traceback.format_exc()}")

        # إرسال إشعار للمُحال (الشخص الجديد)
        if bot:
            logger.debug(f"📤 [{function_name}] إرسال رسالة ترحيب للمُحال {new_user_id}...")
            try:
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

                await bot.send_message(
                    chat_id=new_user_id,
                    text=referred_message,
                    parse_mode='Markdown'
                )
                logger.info(f"✅ [{function_name}] تم إرسال رسالة ترحيب للمُحال {new_user_id} بنجاح")

            except Exception as e:
                logger.error(f"❌ [{function_name}] فشل إرسال رسالة للمُحال {new_user_id}: {type(e).__name__}: {str(e)}")
                logger.debug(f"📍 [{function_name}] تفاصيل خطأ الرسالة:\n{traceback.format_exc()}")

        logger.info(f"✅ [{function_name}] نجح! تم تسجيل إحالة كاملة - المحيل: {referrer_id} ({referrer_name}) → المُحال: {new_user_id} ({new_user_name})")
        return True

    except Exception as e:
        logger.error(f"❌ [{function_name}] خطأ حرج في تسجيل الإحالة: {type(e).__name__}: {str(e)}")
        logger.error(f"📍 [{function_name}] Stack trace:\n{traceback.format_exc()}")
        return False


def add_referral_points(user_id: int, points: int = 5) -> bool:
    """
    إضافة نقاط إحالة (فيديوهات بدون لوجو) للمستخدم

    Args:
        user_id: معرف المستخدم
        points: عدد النقاط المراد إضافتها (افتراضي: 5)

    Returns:
        bool: True في حالة النجاح، False في حالة الفشل
    """
    function_name = "add_referral_points"
    logger.info(f"🔵 [{function_name}] إضافة {points} نقطة للمستخدم {user_id}")

    try:
        # التحقق من صحة المدخلات
        if not user_id or not isinstance(user_id, int):
            logger.error(f"❌ [{function_name}] خطأ: user_id غير صالح: {user_id}")
            return False

        if not isinstance(points, int) or points <= 0:
            logger.error(f"❌ [{function_name}] خطأ: points غير صالح: {points}")
            return False

        logger.debug(f"💾 [{function_name}] تحديث رصيد المستخدم {user_id}...")

        result = users_collection.update_one(
            {'user_id': user_id},
            {'$inc': {'no_logo_credits': points}},
            upsert=True
        )

        if result.acknowledged:
            # جلب الرصيد الجديد
            user = users_collection.find_one({'user_id': user_id})
            new_balance = user.get('no_logo_credits', points) if user else points
            logger.info(f"✅ [{function_name}] نجح! تمت إضافة {points} نقطة للمستخدم {user_id}، الرصيد الجديد: {new_balance}")
            return True
        else:
            logger.error(f"❌ [{function_name}] فشل تحديث قاعدة البيانات للمستخدم {user_id}")
            return False

    except Exception as e:
        logger.error(f"❌ [{function_name}] خطأ حرج للمستخدم {user_id}: {type(e).__name__}: {str(e)}")
        logger.error(f"📍 [{function_name}] Stack trace:\n{traceback.format_exc()}")
        return False


def use_no_logo_credit(user_id: int) -> bool:
    """
    استخدام نقطة واحدة من رصيد الفيديوهات بدون لوجو

    Args:
        user_id: معرف المستخدم

    Returns:
        bool: True في حالة النجاح، False في حالة الفشل أو عدم وجود رصيد
    """
    function_name = "use_no_logo_credit"
    logger.info(f"🔵 [{function_name}] محاولة خصم نقطة من رصيد المستخدم {user_id}")

    try:
        # التحقق من صحة user_id
        if not user_id or not isinstance(user_id, int):
            logger.error(f"❌ [{function_name}] خطأ: user_id غير صالح: {user_id}")
            return False

        logger.debug(f"🔍 [{function_name}] البحث عن المستخدم {user_id}...")

        user = users_collection.find_one({'user_id': user_id})

        if not user:
            logger.warning(f"⚠️ [{function_name}] المستخدم {user_id} غير موجود في قاعدة البيانات")
            return False

        current_credits = user.get('no_logo_credits', 0)
        logger.debug(f"💰 [{function_name}] رصيد المستخدم {user_id} الحالي: {current_credits}")

        if current_credits <= 0:
            logger.warning(f"⚠️ [{function_name}] رصيد المستخدم {user_id} غير كافٍ: {current_credits}")
            return False

        logger.debug(f"💾 [{function_name}] خصم نقطة من رصيد المستخدم {user_id}...")

        # خصم نقطة واحدة
        result = users_collection.update_one(
            {'user_id': user_id},
            {'$inc': {'no_logo_credits': -1}}
        )

        if result.acknowledged and result.modified_count > 0:
            new_balance = current_credits - 1
            logger.info(f"✅ [{function_name}] نجح! تم خصم نقطة من رصيد المستخدم {user_id}، الرصيد الجديد: {new_balance}")
            return True
        else:
            logger.error(f"❌ [{function_name}] فشل تحديث قاعدة البيانات للمستخدم {user_id}")
            return False

    except Exception as e:
        logger.error(f"❌ [{function_name}] خطأ حرج للمستخدم {user_id}: {type(e).__name__}: {str(e)}")
        logger.error(f"📍 [{function_name}] Stack trace:\n{traceback.format_exc()}")
        return False


def get_referral_stats(user_id: int) -> dict:
    """
    جلب إحصائيات الإحالة للمستخدم

    Args:
        user_id: معرف المستخدم

    Returns:
        dict: قاموس يحتوي على إحصائيات الإحالة
    """
    function_name = "get_referral_stats"
    logger.debug(f"🔵 [{function_name}] جلب إحصائيات الإحالة للمستخدم {user_id}")

    default_stats = {
        'referral_code': None,
        'referral_count': 0,
        'no_logo_credits': 0,
        'referred_by': None
    }

    try:
        # التحقق من صحة user_id
        if not user_id or not isinstance(user_id, int):
            logger.error(f"❌ [{function_name}] خطأ: user_id غير صالح: {user_id}")
            return default_stats

        logger.debug(f"🔍 [{function_name}] البحث عن المستخدم {user_id}...")

        user = users_collection.find_one({'user_id': user_id})

        if not user:
            logger.debug(f"⚠️ [{function_name}] المستخدم {user_id} غير موجود، إرجاع إحصائيات افتراضية")
            return default_stats

        stats = {
            'referral_code': user.get('referral_code'),
            'referral_count': user.get('referral_count', 0),
            'no_logo_credits': user.get('no_logo_credits', 0),
            'referred_by': user.get('referred_by')
        }

        logger.debug(f"✅ [{function_name}] تم جلب إحصائيات المستخدم {user_id}: {stats}")
        return stats

    except Exception as e:
        logger.error(f"❌ [{function_name}] خطأ حرج للمستخدم {user_id}: {type(e).__name__}: {str(e)}")
        logger.error(f"📍 [{function_name}] Stack trace:\n{traceback.format_exc()}")
        return default_stats


def get_no_logo_credits(user_id: int) -> int:
    """
    جلب رصيد الفيديوهات بدون لوجو

    Args:
        user_id: معرف المستخدم

    Returns:
        int: رصيد الفيديوهات بدون لوجو، 0 في حالة الخطأ
    """
    function_name = "get_no_logo_credits"
    logger.debug(f"🔵 [{function_name}] جلب رصيد النقاط للمستخدم {user_id}")

    try:
        # التحقق من صحة user_id
        if not user_id or not isinstance(user_id, int):
            logger.error(f"❌ [{function_name}] خطأ: user_id غير صالح: {user_id}")
            return 0

        logger.debug(f"🔍 [{function_name}] البحث عن المستخدم {user_id}...")

        user = users_collection.find_one({'user_id': user_id})

        if not user:
            logger.debug(f"⚠️ [{function_name}] المستخدم {user_id} غير موجود، الرصيد: 0")
            return 0

        credits = user.get('no_logo_credits', 0)
        logger.debug(f"✅ [{function_name}] رصيد المستخدم {user_id}: {credits}")
        return credits

    except Exception as e:
        logger.error(f"❌ [{function_name}] خطأ حرج للمستخدم {user_id}: {type(e).__name__}: {str(e)}")
        logger.error(f"📍 [{function_name}] Stack trace:\n{traceback.format_exc()}")
        return 0
