from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest
import logging
import traceback
from datetime import datetime

from database import (
    generate_referral_code,
    get_referral_stats,
    get_user_language,
    update_user_interaction
)
from utils import get_message

# إعداد logger
logger = logging.getLogger(__name__)

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج أمر /referral - يعرض معلومات نظام الإحالة
    """
    function_name = "referral_command"

    try:
        user = update.message.from_user
        user_id = user.id
        user_name = user.full_name or user.username or "مستخدم"

        logger.info(f"🔵 [{function_name}] بدء معالجة أمر /referral للمستخدم {user_id} ({user_name})")

        # جلب لغة المستخدم
        try:
            lang = get_user_language(user_id)
            logger.debug(f"🌍 [{function_name}] لغة المستخدم {user_id}: {lang}")
        except Exception as e:
            logger.error(f"❌ [{function_name}] خطأ في جلب اللغة للمستخدم {user_id}: {e}")
            lang = "ar"  # افتراضي

        # تحديث آخر تفاعل
        try:
            update_user_interaction(user_id)
        except Exception as e:
            logger.warning(f"⚠️ [{function_name}] فشل تحديث التفاعل للمستخدم {user_id}: {e}")

        # توليد كود إحالة إذا لم يكن موجوداً
        logger.debug(f"🔄 [{function_name}] توليد/جلب كود الإحالة للمستخدم {user_id}...")
        referral_code = generate_referral_code(user_id)

        if not referral_code:
            logger.error(f"❌ [{function_name}] فشل توليد كود الإحالة للمستخدم {user_id}")
            error_message = (
                "❌ حدث خطأ في توليد كود الإحالة. حاول مرة أخرى." if lang == "ar" else
                "❌ Error generating referral code. Try again."
            )
            await update.message.reply_text(error_message, parse_mode='Markdown')
            return
    
        # جلب إحصائيات الإحالة
        logger.debug(f"📊 [{function_name}] جلب إحصائيات الإحالة للمستخدم {user_id}...")

        try:
            stats = get_referral_stats(user_id)
            referral_count = stats.get('referral_count', 0)
            no_logo_credits = stats.get('no_logo_credits', 0)
            logger.debug(f"📊 [{function_name}] إحصائيات المستخدم {user_id} - إحالات: {referral_count}, رصيد: {no_logo_credits}")
        except Exception as e:
            logger.error(f"❌ [{function_name}] خطأ في جلب الإحصائيات للمستخدم {user_id}: {e}")
            referral_count = 0
            no_logo_credits = 0

        # إنشاء رابط الإحالة
        try:
            bot_username = context.bot.username
            referral_link = f"https://t.me/{bot_username}?start={referral_code}"
            logger.debug(f"🔗 [{function_name}] رابط الإحالة: {referral_link}")
        except Exception as e:
            logger.error(f"❌ [{function_name}] خطأ في إنشاء رابط الإحالة للمستخدم {user_id}: {e}")
            referral_link = f"https://t.me/YourBot?start={referral_code}"

        # بناء رسالة الإحالة
        logger.debug(f"📝 [{function_name}] بناء رسالة الإحالة بلغة {lang}...")

        if lang == "ar":
            message_text = (
                f"🎁 **نظام الإحالة - اكسب نقاط مجانية!**\n\n"
                f"🔗 **رابط الإحالة الخاص بك:**\n"
                f"`{referral_link}`\n\n"
                f"📊 **إحصائياتك:**\n"
                f"👥 عدد الإحالات: **{referral_count}** شخص\n"
                f"🎨 رصيد الفيديوهات بدون لوجو: **{no_logo_credits}** فيديو\n\n"
                f"✨ **كيف يعمل؟**\n"
                f"1️⃣ شارك رابطك مع أصدقائك\n"
                f"2️⃣ عندما يسجلون من رابطك\n"
                f"3️⃣ تحصل على **10 فيديوهات بدون لوجو!**\n\n"
                f"💡 **كل إحالة = 10 فيديوهات بدون لوجو مجاناً!**\n\n"
                f"🚀 ابدأ المشاركة الآن واربح نقاط غير محدودة!"
            )
        else:
            message_text = (
                f"🎁 **Referral System - Earn Free Credits!**\n\n"
                f"🔗 **Your referral link:**\n"
                f"`{referral_link}`\n\n"
                f"📊 **Your Stats:**\n"
                f"👥 Referrals: **{referral_count}** people\n"
                f"🎨 No-logo videos balance: **{no_logo_credits}** videos\n\n"
                f"✨ **How it works?**\n"
                f"1️⃣ Share your link with friends\n"
                f"2️⃣ When they register via your link\n"
                f"3️⃣ You get **10 no-logo videos!**\n\n"
                f"💡 **Each referral = 10 no-logo videos free!**\n\n"
                f"🚀 Start sharing now and earn unlimited credits!"
            )

        # إنشاء أزرار للمشاركة
        logger.debug(f"🔘 [{function_name}] إنشاء أزرار المشاركة...")

        share_text = 'احصل على فيديوهات بدون لوجو مجاناً!' if lang == 'ar' else 'Get no-logo videos for free!'

        keyboard = [
            [
                InlineKeyboardButton(
                    "📤 مشاركة الرابط" if lang == "ar" else "📤 Share Link",
                    url=f"https://t.me/share/url?url={referral_link}&text={share_text}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 نسخ الرابط" if lang == "ar" else "📋 Copy Link",
                    callback_data=f"copy_referral_{referral_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 تحديث الإحصائيات" if lang == "ar" else "🔄 Refresh Stats",
                    callback_data="refresh_referral_stats"
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # إرسال الرسالة
        logger.debug(f"📤 [{function_name}] إرسال رسالة الإحالة للمستخدم {user_id}...")

        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        logger.info(f"✅ [{function_name}] نجح! تم عرض معلومات الإحالة للمستخدم {user_id} ({user_name})")

    except Exception as e:
        logger.error(f"❌ [{function_name}] خطأ حرج في معالجة أمر الإحالة: {type(e).__name__}: {str(e)}")
        logger.error(f"📍 [{function_name}] Stack trace:\n{traceback.format_exc()}")

        # محاولة إرسال رسالة خطأ للمستخدم
        try:
            error_msg = (
                "❌ حدث خطأ في عرض معلومات الإحالة. حاول مرة أخرى لاحقاً." if lang == "ar" else
                "❌ An error occurred while displaying referral information. Try again later."
            )
            await update.message.reply_text(error_msg)
        except:
            pass

async def handle_referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار الخاصة بنظام الإحالة"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    
    if query.data == "refresh_referral_stats":
        # تحديث الإحصائيات
        stats = get_referral_stats(user_id)
        referral_code = generate_referral_code(user_id)
        referral_count = stats['referral_count']
        no_logo_credits = stats['no_logo_credits']
        
        bot_username = context.bot.username
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"
        
        # الحصول على الوقت الحالي
        current_time = datetime.now().strftime('%H:%M')
        
        if lang == "ar":
            message_text = (
                f"🎁 **نظام الإحالة - اكسب نقاط مجانية!**\n\n"
                f"🔗 **رابط الإحالة الخاص بك:**\n"
                f"`{referral_link}`\n\n"
                f"📊 **إحصائياتك:**\n"
                f"👥 عدد الإحالات: **{referral_count}** شخص\n"
                f"🎨 رصيد الفيديوهات بدون لوجو: **{no_logo_credits}** فيديو\n\n"
                f"✨ **كيف يعمل؟**\n"
                f"1️⃣ شارك رابطك مع أصدقائك\n"
                f"2️⃣ عندما يسجلون من رابطك\n"
                f"3️⃣ تحصل على **10 فيديوهات بدون لوجو!**\n\n"
                f"💡 **كل إحالة = 10 فيديوهات بدون لوجو مجاناً!**\n\n"
                f"🔄 تم التحديث: {current_time}"
            )
        else:
            message_text = (
                f"🎁 **Referral System - Earn Free Credits!**\n\n"
                f"🔗 **Your referral link:**\n"
                f"`{referral_link}`\n\n"
                f"📊 **Your Stats:**\n"
                f"👥 Referrals: **{referral_count}** people\n"
                f"🎨 No-logo videos balance: **{no_logo_credits}** videos\n\n"
                f"✨ **How it works?**\n"
                f"1️⃣ Share your link with friends\n"
                f"2️⃣ When they register via your link\n"
                f"3️⃣ You get **10 no-logo videos!**\n\n"
                f"💡 **Each referral = 10 no-logo videos free!**\n\n"
                f"🔄 Updated: {current_time}"
            )
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "📤 مشاركة الرابط" if lang == "ar" else "📤 Share Link",
                    url=f"https://t.me/share/url?url={referral_link}&text={'احصل على فيديوهات بدون لوجو مجاناً!' if lang == 'ar' else 'Get no-logo videos for free!'}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 نسخ الرابط" if lang == "ar" else "📋 Copy Link",
                    callback_data=f"copy_referral_{referral_code}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 تحديث الإحصائيات" if lang == "ar" else "🔄 Refresh Stats",
                    callback_data="refresh_referral_stats"
                )
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            await query.answer("✅ تم تحديث الإحصائيات!" if lang == "ar" else "✅ Stats refreshed!")
        except BadRequest as e:
            if "message is not modified" in str(e).lower():
                await query.answer("📊 الإحصائيات محدثة بالفعل!" if lang == "ar" else "📊 Stats already up to date!")
            else:
                raise
    
    elif query.data.startswith("copy_referral_"):
        # إرسال الرابط في رسالة منفصلة للنسخ السهل
        referral_code = query.data.replace("copy_referral_", "")
        bot_username = context.bot.username
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"
        
        copy_message = (
            f"📋 **انسخ الرابط من هنا:**\n\n`{referral_link}`" if lang == "ar" else
            f"📋 **Copy link from here:**\n\n`{referral_link}`"
        )
        
        await context.bot.send_message(
            chat_id=user_id,
            text=copy_message,
            parse_mode='Markdown'
        )
        
        await query.answer("✅ تم إرسال الرابط للنسخ!" if lang == "ar" else "✅ Link sent for copying!")

async def show_referral_in_account(user_id: int, lang: str) -> str:
    """إضافة معلومات الإحالة إلى صفحة الحساب"""
    stats = get_referral_stats(user_id)
    
    if lang == "ar":
        referral_info = (
            f"\n🎁 **نظام الإحالة:**\n"
            f"👥 إحالاتك: {stats['referral_count']}\n"
            f"🎨 رصيد بدون لوجو: {stats['no_logo_credits']} فيديو\n"
            f"💡 استخدم /referral لمزيد من التفاصيل"
        )
    else:
        referral_info = (
            f"\n🎁 **Referral System:**\n"
            f"👥 Your referrals: {stats['referral_count']}\n"
            f"🎨 No-logo balance: {stats['no_logo_credits']} videos\n"
            f"💡 Use /referral for more details"
        )
    
    return referral_info
