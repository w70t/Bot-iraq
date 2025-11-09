from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database import add_user, update_user_language, update_user_interaction, get_user_language, track_referral, generate_referral_code, is_subscription_enabled
from utils import get_message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج أمر /start - يعرض اختيار اللغة وأزرار القائمة
    يدعم deep linking لنظام الإحالة
    """
    user = update.message.from_user
    user_id = user.id
    
    # التحقق من وجود كود إحالة في deep link
    # الصيغة: /start REF_XXXXX
    referral_code = None
    if context.args and len(context.args) > 0:
        potential_code = context.args[0]
        # التحقق من أن الكود يبدأ بـ REF_
        if potential_code.startswith('REF_'):
            referral_code = potential_code
    
    # إضافة المستخدم إلى قاعدة البيانات
    add_user(user_id, user.username, user.full_name)
    
    # معالجة الإحالة إذا كانت موجودة
    if referral_code:
        from telegram.ext import ContextTypes
        # جلب الـ bot من context
        referral_success = track_referral(referral_code, user_id, bot=context.bot)
        if referral_success:
            # تم إضافة إشعارات تلقائية في track_referral
            pass
    
    # توليد كود إحالة للمستخدم الجديد
    generate_referral_code(user_id)
    
    update_user_interaction(user_id)

    keyboard = [["العربية 🇸🇦", "English 🇬🇧"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    welcome_text = (
        "🎉 **مرحباً! Welcome!** 🎉\n\n"
        "🌍 **اختر لغتك | Choose your language:**"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج اختيار اللغة - يعرض القائمة الرئيسية
    """
    user = update.message.from_user
    user_id = user.id
    lang_choice = update.message.text
    
    # تحديد اللغة
    if "English" in lang_choice or "🇬🇧" in lang_choice:
        lang_code = "en"
    else:
        lang_code = "ar"

    update_user_language(user_id, lang_code)
    
    # الرسالة الترحيبية
    welcome_message = get_message(lang_code, "welcome").format(name=user.first_name)
    
    # إنشاء لوحة المفاتيح الرئيسية
    keyboard = create_main_keyboard(lang_code)
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def create_main_keyboard(lang_code: str):
    """
    إنشاء لوحة المفاتيح الرئيسية حسب اللغة
    مع التحكم في عرض زر VIP حسب حالة الاشتراك
    """
    # التحقق من حالة الاشتراك
    sub_enabled = is_subscription_enabled()

    if lang_code == "ar":
        keyboard = [
            ["📥 تحميل فيديو", "👤 حسابي"]
        ]
        # إضافة زر VIP فقط إذا كان مفعلاً
        if sub_enabled:
            keyboard.append(["⭐ الاشتراك VIP", "❓ المساعدة"])
        else:
            keyboard.append(["❓ المساعدة"])

        # زر الدعم دائماً موجود
        keyboard.append(["🎁 دعم صاحب البوت"])
        keyboard.append(["🌐 تغيير اللغة"])
    else:
        keyboard = [
            ["📥 Download Video", "👤 My Account"]
        ]
        # إضافة زر VIP فقط إذا كان مفعلاً
        if sub_enabled:
            keyboard.append(["⭐ Subscribe VIP", "❓ Help"])
        else:
            keyboard.append(["❓ Help"])

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
    from handlers.account import account_info
    from handlers.referral import referral_command
    
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
    
    elif text in ["👤 حسابي", "👤 My Account"]:
        await account_info(update, context)
    
    elif text in ["🎁 الإحالات", "🎁 Referrals"]:
        await referral_command(update, context)
    
    elif text in ["❓ المساعدة", "❓ Help"]:
        help_text = get_message(lang, "help_message")
        
        # إنشاء زر Contact Us فقط
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        if lang == "ar":
            keyboard = [
                [InlineKeyboardButton("📸 تواصل معنا عبر Instagram", url="https://instagram.com/7kmmy")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("📸 Contact Us on Instagram", url="https://instagram.com/7kmmy")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif text in ["⭐ الاشتراك VIP", "⭐ Subscribe VIP"]:
        subscribe_message = (
            "👑 **باقة VIP المميزة!**\n\n"
            "✨ **المميزات:**\n"
            "♾️ تحميلات غير محدودة\n"
            "⏱️ فيديوهات بأي طول\n"
            "🎨 بدون لوجو\n"
            "📺 جودات عالية 4K/HD\n"
            "⚡ أولوية في المعالجة\n"
            "🎵 تحميل صوتي MP3\n\n"
            "💰 **السعر:** 3$ شهرياً\n\n"
            "📞 **للاشتراك، تواصل معنا:**\n"
            "📸 Instagram: @7kmmy\n"
            "🔗 https://instagram.com/7kmmy\n\n"
            "💡 **انقر على الأزرار أدناه للتفاعل**"
        ) if lang == "ar" else (
            "👑 **VIP Premium Plan!**\n\n"
            "✨ **Features:**\n"
            "♾️ Unlimited downloads\n"
            "⏱️ Any video length\n"
            "🎨 No watermark\n"
            "📺 High quality 4K/HD\n"
            "⚡ Priority processing\n"
            "🎵 Audio download MP3\n\n"
            "💰 **Price:** $3 monthly\n\n"
            "📞 **To subscribe, contact us:**\n"
            "📸 Instagram: @7kmmy\n"
            "🔗 https://instagram.com/7kmmy\n\n"
            "💡 **Click the buttons below to interact**"
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
        await update.message.reply_text(subscribe_message, reply_markup=reply_markup, parse_mode='Markdown')

    elif text in ["🎁 دعم صاحب البوت", "🎁 Support the Creator"]:
        import os

        # رسالة الدعم
        support_message = (
            "💝 **شكراً على دعمك! / Thank you for your support!**\n\n"
            "يمكنك إرسال مكافأة عبر:\n"
            "You can send a tip via:\n\n"
            "💰 Binance أو 📸 Instagram:\n"
            "👉 [اضغط هنا / Click here](https://www.instagram.com/7kmmy)\n\n"
            "🙏 دعمك يساعد في تطوير البوت\n"
            "Your support helps develop the bot"
        )

        # إنشاء أزرار الدعم
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        BINANCE_WALLET = os.getenv("BINANCE_WALLET", "Contact @7kmmy for Binance wallet")

        keyboard = [
            [InlineKeyboardButton("💰 دعم عبر Binance / Support via Binance", callback_data="support_binance")],
            [InlineKeyboardButton("📸 دعم عبر Instagram / Support via Instagram", url="https://www.instagram.com/7kmmy")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(support_message, reply_markup=reply_markup, parse_mode='Markdown')

    elif text in ["🌐 تغيير اللغة", "🌐 Change Language"]:
        keyboard = [["العربية 🇸🇦", "English 🇬🇧"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        change_lang_text = "🌍 **اختر لغتك | Choose your language:**"
        await update.message.reply_text(change_lang_text, reply_markup=reply_markup, parse_mode='Markdown')
    

