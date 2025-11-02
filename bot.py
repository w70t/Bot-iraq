import os
import logging

# ⭐ إضافة هذا السطر لتحميل متغيرات .env
from dotenv import load_dotenv
load_dotenv()  # يحمل المتغيرات من ملف .env

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# استيراد المكونات
from handlers.start import start, select_language, handle_menu_buttons
from handlers.download import handle_download, handle_quality_selection
from handlers.admin import admin_conv_handler
from handlers.account import account_info, test_subscription
from handlers.video_info import handle_video_message
from handlers.referral import referral_command, handle_referral_callback
from utils import get_message, escape_markdown, get_config, load_config, setup_bot_menu
from database import init_db, update_user_interaction

# معالجات الأزرار التفاعلية
async def handle_vip_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أزرار VIP التفاعلية"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    from database import get_user_language
    lang = get_user_language(user_id)
    
    if query.data == "vip_payment":
        # زر الدفعة
        payment_message = (
            "💳 **الدفع للاشتراك VIP**\n\n"
            "📸 تواصل مع الانستغرام: **@7kmmy**\n\n"
            "💰 السعر: **3$ شهرياً**\n\n"
            "✨ أوافق على معالجة الدفع وسأرسل الصورة التالية للرسالة\n"
            "🔗 الرابط: https://instagram.com/7kmmy"
        ) if lang == "ar" else (
            "💳 **VIP Subscription Payment**\n\n"
            "📸 Contact Instagram: **@7kmmy**\n\n"
            "💰 Price: **$3 monthly**\n\n"
            "✨ I agree to process payment and will send the following image to the message\n"
            "🔗 Link: https://instagram.com/7kmmy"
        )
        await query.message.edit_text(payment_message, parse_mode='Markdown')
        
    elif query.data == "contact_support":
        # زر التواصل
        contact_message = (
            "📞 **تواصل مع دعم العملاء**\n\n"
            "💬 للانستغرام: @7kmmy\n"
            "📧 للبحث عن احتياجاتك\n"
            "⚡ خلال 24 ساعة\n\n"
            "🤝 نحن هنا لمساعدتك!"
        ) if lang == "ar" else (
            "📞 **Contact Customer Support**\n\n"
            "💬 For Instagram: @7kmmy\n"
            "📧 To address your needs\n"
            "⚡ Within 24 hours\n\n"
            "🤝 We are here to help you!"
        )
        await query.message.edit_text(contact_message, parse_mode='Markdown')
        
    elif query.data == "vip_details":
        # زر تفاصيل الباقة
        details_message = (
            "📋 **تفاصيل باقة VIP**\n\n"
            "✨ **المميزات الكاملة:**\n\n"
            "♾️ **تحميلات غير محدودة**\n"
            "⏱️ **فيديوهات بأي طول**\n"
            "🎨 **بدون لوجو**\n"
            "📺 **جودات 4K/8K**\n"
            "⚡ **أولوية في المعالجة**\n"
            "🎵 **تحميل صوتي MP3**\n"
            "💬 **دعم فني 24/7**\n\n"
            "💰 **السعر:** 3$ شهرياً\n"
            "⏱️ **البداية:** بعد تأكيد الدفعة\n"
            "📅 **التجديد:** تلقائياً كل شهر"
        ) if lang == "ar" else (
            "📋 **VIP Plan Details**\n\n"
            "✨ **Complete Features:**\n\n"
            "♾️ **Unlimited downloads**\n"
            "⏱️ **Any video length**\n"
            "🎨 **No watermark**\n"
            "📺 **4K/8K quality**\n"
            "⚡ **Priority processing**\n"
            "🎵 **MP3 audio download**\n"
            "💬 **24/7 technical support**\n\n"
            "💰 **Price:** $3 monthly\n"
            "⏱️ **Start:** After payment confirmation\n"
            "📅 **Renewal:** Automatically every month"
        )
        await query.message.edit_text(details_message, parse_mode='Markdown')

# إعدادات أساسية
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN")
PORT = int(os.getenv("PORT", 8443))
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

# باقي الكود كما هو...
async def forward_to_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إعادة توجيه الرسائل إلى قناة اللوج"""
    if not LOG_CHANNEL_ID:
        return

    user = update.message.from_user
    
    escaped_full_name = escape_markdown(user.full_name)
    username_part = f"@{user.username}" if user.username else "لا يوجد"
    
    user_info = (
        f"👤 **رسالة من:** {escaped_full_name}\n"
        f"🆔 **ID:** `{user.id}`\n"
        f"🔗 **Username:** {username_part}"
    )

    try:
        await context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=user_info,
            parse_mode='MarkdownV2'
        )
        await context.bot.forward_message(
            chat_id=LOG_CHANNEL_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
    except Exception as e:
        logger.error(f"❌ فشل إعادة توجيه الرسالة إلى القناة {LOG_CHANNEL_ID}: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر المساعدة"""
    from database import get_user_language
    
    user_id = update.message.from_user.id
    lang = get_user_language(user_id)
    update_user_interaction(user_id)
    
    help_text = get_message(lang, "help_message")
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def post_init(application: Application):
    """يتم تنفيذه بعد تهيئة البوت"""
    logger.info("🚀 بدء إعداد قائمة الأوامر...")
    await setup_bot_menu(application.bot)
    logger.info("✅ تم إعداد قائمة الأوامر بنجاح!")

def main() -> None:
    """تشغيل البوت الرئيسي"""
    logger.info("=" * 50)
    logger.info("🤖 بدء تشغيل البوت...")
    logger.info("=" * 50)
    
    # تحميل الإعدادات
    load_config()
    config = get_config()
    
    # التحقق من قاعدة البيانات (اختبار بدون قاعدة البيانات)
    try:
        init_db()
        logger.info("✅ تم الاتصال بقاعدة البيانات بنجاح.")
        
        # تهيئة إعدادات المكتبات
        try:
            from database import init_library_settings
            init_library_settings()
            logger.info("✅ تم تهيئة إعدادات المكتبات بنجاح")
        except Exception as e:
            logger.error(f"❌ فشل تهيئة إعدادات المكتبات: {e}")
            
    except Exception as e:
        logger.warning(f"⚠️ خطأ في الاتصال بقاعدة البيانات: {e}")
        logger.info("🧪 تشغيل البوت في وضع الاختبار (بدون قاعدة بيانات).")
        # لا نوقف البوت في وضع الاختبار

    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # تخزين الإعدادات
    application.bot_data["config"] = config

    # ===== تسجيل الـ Handlers =====
    
    # 1. Handler لإعادة توجيه الرسائل للوج (يعمل قبل باقي الـ handlers)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_log_channel),
        group=-1
    )

    # 2. أوامر البداية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("referral", referral_command))
    
    # 3. معلومات الحساب
    application.add_handler(CommandHandler("account", account_info))
    application.add_handler(CommandHandler("testsub", test_subscription))
    
    # 4. Handler للفيديوهات المرسلة
    application.add_handler(MessageHandler(filters.VIDEO, handle_video_message))
    
    # 5. Handler لاختيار اللغة
    application.add_handler(MessageHandler(
        filters.Regex("^(English 🇬🇧|العربية 🇸🇦)$"), 
        select_language
    ))
    
    # 6. Handler لأزرار القائمة الرئيسية
    application.add_handler(MessageHandler(
        filters.Regex("^(📥 تحميل فيديو|📥 Download Video|👤 حسابي|👤 My Account|🎁 الإحالات|🎁 Referrals|❓ المساعدة|❓ Help|⭐ الاشتراك VIP|⭐ Subscribe VIP|🌐 تغيير اللغة|🌐 Change Language)$"),
        handle_menu_buttons
    ))
    
    # 7. Handler لاختيار الجودة (Callback Query)
    application.add_handler(CallbackQueryHandler(
        handle_quality_selection,
        pattern="^quality_"
    ))
    
    # 8. Handler للأزرار التفاعلية (Callback Query)
    application.add_handler(CallbackQueryHandler(
        handle_vip_buttons,
        pattern="^(vip_payment|contact_support|vip_details)$"
    ))
    
    # 9. Handler لأزرار نظام الإحالة (Callback Query)
    application.add_handler(CallbackQueryHandler(
        handle_referral_callback,
        pattern="^(refresh_referral_stats|copy_referral_)"
    ))
    
    # 10. Handler للوحة تحكم الأدمن
    application.add_handler(admin_conv_handler)
    
    # 11. Handler لتحميل الفيديوهات من الروابط (يجب أن يكون الأخير)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"https?://\S+"),
            handle_download,
        )
    )
    
    logger.info("✅ تم تسجيل جميع المعالجات بنجاح.")
    logger.info("=" * 50)

    # تشغيل البوت
    if WEBHOOK_URL:
        logger.info(f"🌐 وضع Webhook")
        logger.info(f"📍 المنفذ: {PORT}")
        logger.info(f"🔗 URL: https://{WEBHOOK_URL}/{BOT_TOKEN}")
        logger.info("=" * 50)
        
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"https://{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        logger.info("🔄 وضع Polling (محلي)")
        logger.info("=" * 50)
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
