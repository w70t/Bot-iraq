from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import logging
import os
from datetime import datetime

from database import add_user, update_user_language, update_user_interaction, get_user_language, track_referral, generate_referral_code, is_subscription_enabled
from utils import get_message
from handlers.channel_manager import channel_manager

# إعداد logger
logger = logging.getLogger(__name__)

async def send_new_user_notification(context: ContextTypes.DEFAULT_TYPE, user, referrer_id=None):
    """
    إرسال إشعار لقناة الأعضاء الجدد عند اشتراك عضو جديد
    Uses the new ChannelManager system
    """
    try:
        # Use channel_manager to log new user
        await channel_manager.log_new_user(
            bot=context.bot,
            user_id=user.id,
            username=user.username,
            first_name=user.full_name,
            language_code=user.language_code,
            referrer_id=referrer_id
        )
        logger.info(f"✅ تم إرسال إشعار العضو الجديد: {user.id}")
    except Exception as e:
        logger.error(f"❌ فشل إرسال إشعار العضو الجديد: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج أمر /start - يعرض اختيار اللغة وأزرار القائمة
    يدعم deep linking لنظام الإحالة
    """
    user = update.message.from_user
    user_id = user.id

    logger.info("=" * 60)
    logger.info(f"🎬 [START] User {user_id} ({user.full_name}) بدأ البوت")
    logger.info("=" * 60)

    # التحقق من وجود كود إحالة في deep link
    # الصيغة: /start REF_XXXXX
    referral_code = None
    if context.args and len(context.args) > 0:
        potential_code = context.args[0]
        # التحقق من أن الكود يبدأ بـ REF_
        if potential_code.startswith('REF_'):
            referral_code = potential_code
    
    # إضافة المستخدم إلى قاعدة البيانات وتحديد إذا كان جديد
    is_new_user = add_user(user_id, user.username, user.full_name)

    # إرسال إشعار لقناة السجلات عند اشتراك عضو جديد
    if is_new_user:
        await send_new_user_notification(context, user)

    # معالجة الإحالة إذا كانت موجودة
    if referral_code:
        from telegram.ext import ContextTypes
        # جلب الـ bot من context (تمرير None لتجنب مشاكل async)
        referral_success = track_referral(referral_code, user_id, bot=None)
        if referral_success:
            # إرسال إشعار يدوي للمستخدم الجديد
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🎉 تمت إضافة الإحالة بنجاح!\n✅ Referral successfully added!",
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Referral notification error: {e}")
    
    # توليد كود إحالة للمستخدم الجديد
    generate_referral_code(user_id)
    
    update_user_interaction(user_id)

    keyboard = [["العربية 🇸🇦", "English 🇬🇧"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    welcome_text = (
        "🎉 **مرحباً! Welcome!** 🎉\n\n"
        "🌍 **اختر لغتك | Choose your language:**"
    )

    logger.info(f"✅ [START] إرسال رسالة الترحيب مع أزرار اللغة للمستخدم {user_id}")
    logger.info(f"🔘 [START] الأزرار المرسلة: {keyboard}")

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

    logger.info(f"✅ [START] تم إرسال رسالة الترحيب بنجاح للمستخدم {user_id}")
    logger.info("=" * 60)

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج اختيار اللغة - يعرض القائمة الرئيسية
    """
    user = update.message.from_user
    user_id = user.id
    lang_choice = update.message.text

    logger.info("=" * 60)
    logger.info(f"🌍 [SELECT_LANGUAGE] المستخدم {user_id} ({user.full_name}) اختار: {lang_choice}")
    logger.info("=" * 60)

    # تحديد اللغة
    if "English" in lang_choice or "🇬🇧" in lang_choice:
        lang_code = "en"
    else:
        lang_code = "ar"

    logger.info(f"✅ [SELECT_LANGUAGE] اللغة المحددة: {lang_code}")

    update_user_language(user_id, lang_code)

    # الرسالة الترحيبية مع قناة التحديثات
    if lang_code == "ar":
        welcome_message = (
            f"✨ **أهلاً {user.first_name}!**\n\n"
            "📥 يمكنك الآن تحميل الفيديوهات والصوتيات من جميع المنصات!\n\n"
            "📢 **تابع قناتنا الرسمية للتحديثات:**"
        )
    else:
        welcome_message = (
            f"✨ **Welcome {user.first_name}!**\n\n"
            "📥 You can now download videos and audios from all platforms!\n\n"
            "📢 **Follow our official channel for updates:**"
        )

    # إنشاء لوحة المفاتيح الرئيسية
    keyboard = create_main_keyboard(lang_code)
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    logger.info(f"🔘 [SELECT_LANGUAGE] أزرار القائمة الرئيسية: {keyboard}")

    # إنشاء زر قناة التحديثات
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    channel_keyboard = [
        [InlineKeyboardButton("📢 قناة التحديثات الرسمية" if lang_code == "ar" else "📢 Official Updates Channel",
                             url="https://t.me/iraq_7kmmy")]
    ]
    channel_markup = InlineKeyboardMarkup(channel_keyboard)

    logger.info(f"✅ [SELECT_LANGUAGE] إرسال رسالة الترحيب مع زر القناة...")

    # إرسال رسالة الترحيب مع زر القناة
    await update.message.reply_text(
        welcome_message,
        reply_markup=channel_markup,
        parse_mode='Markdown'
    )

    logger.info(f"✅ [SELECT_LANGUAGE] إرسال القائمة الرئيسية...")

    # إرسال لوحة المفاتيح الرئيسية بعد ذلك
    welcome_keyboard_text = get_message(lang_code, "welcome").format(name=user.first_name)
    await update.message.reply_text(
        "🎉 **القائمة الرئيسية:**" if lang_code == "ar" else "🎉 **Main Menu:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    logger.info(f"✅ [SELECT_LANGUAGE] تم إرسال جميع الرسائل بنجاح للمستخدم {user_id}")
    logger.info("=" * 60)

def create_main_keyboard(lang_code: str):
    """
    إنشاء لوحة المفاتيح الرئيسية حسب اللغة
    مع التحكم في عرض زر VIP حسب حالة الاشتراك
    """
    # التحقق من حالة الاشتراك
    sub_enabled = is_subscription_enabled()

    if lang_code == "ar":
        keyboard = [
            ["📥 تحميل فيديو", "🎧 تحميل صوت"],
            ["👤 حسابي", "❓ المساعدة"]
        ]
        # إضافة زر VIP فقط إذا كان مفعلاً
        if sub_enabled:
            keyboard.append(["⭐ الاشتراك VIP"])

        # زر الدعم دائماً موجود
        keyboard.append(["🎁 دعم صاحب البوت"])
        keyboard.append(["🌐 تغيير اللغة"])
    else:
        keyboard = [
            ["📥 Download Video", "🎧 Download Audio"],
            ["👤 My Account", "❓ Help"]
        ]
        # إضافة زر VIP فقط إذا كان مفعلاً
        if sub_enabled:
            keyboard.append(["⭐ Subscribe VIP"])

        # زر الدعم دائماً موجود
        keyboard.append(["🎁 Support the Creator"])
        keyboard.append(["🌐 Change Language"])

    return keyboard

async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج أزرار القائمة الرئيسية
    """
    user_id = update.message.from_user.id
    text = update.message.text
    lang = get_user_language(user_id)
    
    # استيراد محلي لتجنب الاستيراد الدائري
    from handlers.user.account import account_info
    from handlers.user.referral import referral_command
    from handlers.user.support_handler import show_support_message
    
    # تحديث آخر تفاعل
    update_user_interaction(user_id)
    
    if text in ["📥 تحميل فيديو", "📥 Download Video"]:
        message = (
            "🎬 **أرسل رابط الفيديو الآن!**\n\n"
            "✅ **المنصات المدعومة:**\n"
            "• YouTube\n"
            "• Instagram\n"
            "• Facebook\n"
            "• TikTok\n"
            "• Twitter\n"
            "• وأكثر من 1000+ موقع!"
        ) if lang == "ar" else (
            "🎬 **Send video link now!**\n\n"
            "✅ **Supported platforms:**\n"
            "• YouTube\n"
            "• Instagram\n"
            "• Facebook\n"
            "• TikTok\n"
            "• Twitter\n"
            "• And 1000+ more sites!"
        )
        await update.message.reply_text(message, parse_mode='Markdown')

    elif text in ["🎧 تحميل صوت", "🎧 Download Audio"]:
        message = (
            "🎵 **أرسل رابط الصوت/الفيديو الآن!**\n\n"
            "✅ **سيتم استخراج الصوت فقط من:**\n"
            "• YouTube (حتى 6 روابط)\n"
            "• Instagram\n"
            "• Facebook\n"
            "• TikTok\n"
            "• Twitter\n\n"
            "📝 **يمكنك إرسال:**\n"
            "• رابط واحد\n"
            "• عدة روابط (حتى 6)\n"
            "• روابط مفصولة بمسافة أو سطر جديد\n\n"
            "🎧 **الصيغ المتاحة:** MP3, M4A"
        ) if lang == "ar" else (
            "🎵 **Send audio/video link now!**\n\n"
            "✅ **Audio will be extracted from:**\n"
            "• YouTube (up to 6 links)\n"
            "• Instagram\n"
            "• Facebook\n"
            "• TikTok\n"
            "• Twitter\n\n"
            "📝 **You can send:**\n"
            "• Single link\n"
            "• Multiple links (up to 6)\n"
            "• Links separated by space or new line\n\n"
            "🎧 **Available formats:** MP3, M4A"
        )
        await update.message.reply_text(message, parse_mode='Markdown')

    elif text in ["👤 حسابي", "👤 My Account"]:
        await account_info(update, context)
    
    elif text in ["🎁 الإحالات", "🎁 Referrals"]:
        await referral_command(update, context)
    
    elif text in ["❓ المساعدة", "❓ Help"]:
        help_text = get_message(lang, "help_message")

        # إنشاء أزرار القائمة
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from database import is_admin

        if lang == "ar":
            keyboard = [
                [InlineKeyboardButton("📸 تواصل معنا عبر Instagram", url="https://instagram.com/7kmmy")]
            ]
            # إضافة زر Admin للمدراء فقط
            if is_admin(user_id):
                keyboard.insert(0, [InlineKeyboardButton("🛠️ لوحة التحكم", callback_data="admin_panel")])
        else:
            keyboard = [
                [InlineKeyboardButton("📸 Contact Us on Instagram", url="https://instagram.com/7kmmy")]
            ]
            # Add Admin button for admins only
            if is_admin(user_id):
                keyboard.insert(0, [InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin_panel")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif text in ["⭐ الاشتراك VIP", "⭐ Subscribe VIP"]:
        # جلب السعر من قاعدة البيانات
        from database import get_subscription_price
        price = get_subscription_price()

        subscribe_message = (
            "👑 <b>باقة VIP المميزة!</b>\n\n"
            "✨ <b>المميزات:</b>\n"
            "♾️ تحميلات غير محدودة\n"
            "⏱️ فيديوهات بأي طول\n"
            "🎨 بدون لوجو\n"
            "📺 جودات عالية 4K/HD\n"
            "⚡ أولوية في المعالجة\n"
            "🎵 تحميل صوتي MP3\n\n"
            f"💰 <b>السعر:</b> ${price} شهرياً\n\n"
            "📞 <b>للاشتراك، تواصل معنا:</b>\n"
            "📸 Instagram: @7kmmy\n"
            "🔗 https://instagram.com/7kmmy\n\n"
            "📢 <b>تابعنا على Telegram:</b>\n"
            "🔗 https://t.me/iraq_7kmmy\n\n"
            "💡 <b>انقر على الأزرار أدناه للتفاعل</b>"
        ) if lang == "ar" else (
            "👑 <b>VIP Premium Plan!</b>\n\n"
            "✨ <b>Features:</b>\n"
            "♾️ Unlimited downloads\n"
            "⏱️ Any video length\n"
            "🎨 No watermark\n"
            "📺 High quality 4K/HD\n"
            "⚡ Priority processing\n"
            "🎵 Audio download MP3\n\n"
            f"💰 <b>Price:</b> ${price} monthly\n\n"
            "📞 <b>To subscribe, contact us:</b>\n"
            "📸 Instagram: @7kmmy\n"
            "🔗 https://instagram.com/7kmmy\n\n"
            "📢 <b>Follow us on Telegram:</b>\n"
            "🔗 https://t.me/iraq_7kmmy\n\n"
            "💡 <b>Click the buttons below to interact</b>"
        )

        # إنشاء أزرار تفاعلية
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        if lang == "ar":
            keyboard = [
                [InlineKeyboardButton("💳 دفعة الآن - Instagram", callback_data="vip_payment")],
                [InlineKeyboardButton("📞 تواصل معنا", callback_data="contact_support")],
                [InlineKeyboardButton("ℹ️ تفاصيل الباقة", callback_data="vip_details")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("💳 Pay Now - Instagram", callback_data="vip_payment")],
                [InlineKeyboardButton("📞 Contact Us", callback_data="contact_support")],
                [InlineKeyboardButton("ℹ️ Plan Details", callback_data="vip_details")]
            ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(subscribe_message, reply_markup=reply_markup, parse_mode='HTML')

    elif text in ["🎁 دعم صاحب البوت", "🎁 Support the Creator"]:
        # استخدام معالج الدعم الجديد
        await show_support_message(update, context)

    elif text in ["🌐 تغيير اللغة", "🌐 Change Language"]:
        keyboard = [["العربية 🇸🇦", "English 🇬🇧"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        change_lang_text = "🌍 **اختر لغتك | Choose your language:**"
        await update.message.reply_text(change_lang_text, reply_markup=reply_markup, parse_mode='Markdown')
    

