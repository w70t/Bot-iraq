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
from handlers.support_handler import show_support_message, show_qr_code, support_back
from handlers.multi_download_handler import (
    handle_multi_download,
    show_mode_selection,
    show_quality_selection as show_multi_quality_selection,
    show_audio_format_selection,
    download_videos,
    download_audio,
    handle_download_cancel
)
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

async def send_startup_reports(application: Application):
    """إرسال تقارير بدء التشغيل إلى قناة السجلات والأدمن"""
    try:
        from database import get_all_users, is_subscription_enabled, is_welcome_broadcast_enabled
        from datetime import datetime

        # جلب البيانات
        all_users = get_all_users()
        total_users = len(all_users)
        sub_enabled = is_subscription_enabled()
        welcome_enabled = is_welcome_broadcast_enabled()

        # رموز الحالة
        sub_icon = "✅ Enabled" if sub_enabled else "🚫 Disabled"
        welcome_icon = "✅ Enabled" if welcome_enabled else "🚫 Disabled"
        timestamp = datetime.now().strftime("%H:%M — %d-%m-%Y")

        # تقرير لقناة السجلات
        LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
        if LOG_CHANNEL_ID:
            try:
                log_text = (
                    "🧠 *تم تشغيل البوت بنجاح / Bot Started Successfully*\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"💎 الاشتراك / Subscription: {sub_icon}\n"
                    f"💬 الترحيب / Welcome Broadcast: {welcome_icon}\n"
                    f"👥 المستخدمين / Registered Users: {total_users}\n"
                    f"🕒 الوقت / Time: {timestamp}\n"
                    "━━━━━━━━━━━━━━━━━━"
                )
                await application.bot.send_message(
                    chat_id=LOG_CHANNEL_ID,
                    text=log_text,
                    parse_mode='Markdown'
                )
                logger.info("✅ تم إرسال تقرير بدء التشغيل إلى قناة السجلات")
            except Exception as e:
                logger.error(f"❌ فشل إرسال تقرير بدء التشغيل إلى القناة: {e}")

        # تقرير خاص للأدمن
        ADMIN_ID = os.getenv("ADMIN_ID")
        if ADMIN_ID:
            try:
                admin_report = (
                    "🧩 *Bot System Report / تقرير النظام*\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "🚀 Bot started successfully!\n"
                    f"👥 Users: {total_users}\n"
                    f"💎 Subscription: {sub_icon}\n"
                    f"💬 Welcome Broadcast: {welcome_icon}\n"
                    f"🕒 Started: {timestamp}\n"
                    "⚡ Server: Raspberry Pi 5 (Local)\n"
                    "━━━━━━━━━━━━━━━━━━"
                )
                await application.bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=admin_report,
                    parse_mode='Markdown'
                )
                logger.info("✅ تم إرسال تقرير بدء التشغيل للأدمن")
            except Exception as e:
                logger.error(f"❌ فشل إرسال تقرير بدء التشغيل للأدمن: {e}")

    except Exception as e:
        logger.error(f"❌ خطأ في إرسال تقارير بدء التشغيل: {e}")


async def post_init(application: Application):
    """يتم تنفيذه بعد تهيئة البوت"""
    logger.info("🚀 بدء إعداد قائمة الأوامر...")
    await setup_bot_menu(application.bot)
    logger.info("✅ تم إعداد قائمة الأوامر بنجاح!")

    # إرسال تقارير بدء التشغيل
    await send_startup_reports(application)

def main() -> None:
    """تشغيل البوت الرئيسي"""
    logger.info("=" * 50)
    logger.info("🤖 بدء تشغيل البوت...")
    logger.info("=" * 50)

    # تحديث yt-dlp تلقائياً لتجنب مشاكل nsig
    try:
        import subprocess
        logger.info("🔄 Updating yt-dlp...")
        result = subprocess.run(
            ["yt-dlp", "-U"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        if result.returncode == 0:
            logger.info("✅ yt-dlp updated successfully")
        else:
            logger.warning("⚠️ yt-dlp update returned non-zero code (might already be latest)")
    except subprocess.TimeoutExpired:
        logger.warning("⚠️ yt-dlp update timed out - continuing anyway")
    except Exception as e:
        logger.warning(f"⚠️ Could not update yt-dlp: {e} - continuing anyway")

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
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .concurrent_updates(10)
        .build()
    )

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
        filters.Regex("^(📥 تحميل فيديو|📥 Download Video|🎧 تحميل صوت|🎧 Download Audio|👤 حسابي|👤 My Account|🎁 الإحالات|🎁 Referrals|❓ المساعدة|❓ Help|⭐ الاشتراك VIP|⭐ Subscribe VIP|🎁 دعم صاحب البوت|🎁 Support the Creator|🌐 تغيير اللغة|🌐 Change Language)$"),
        handle_menu_buttons
    ))

    # 7. Multi-Download Handlers (يجب أن تكون قبل handler القديم للحصول على الأولوية)
    # Handler لاختيار الوضع (فيديو أو صوت)
    application.add_handler(CallbackQueryHandler(
        show_multi_quality_selection,
        pattern="^mode_video$"
    ))
    application.add_handler(CallbackQueryHandler(
        show_audio_format_selection,
        pattern="^mode_audio$"
    ))

    # Handler لاختيار الجودة (Multi-Download - أنماط محددة)
    application.add_handler(CallbackQueryHandler(
        download_videos,
        pattern="^quality_(360|720|1080)$"
    ))

    # Handler لاختيار صيغة الصوت
    application.add_handler(CallbackQueryHandler(
        download_audio,
        pattern="^audio_(mp3|m4a)$"
    ))

    # Handler لإلغاء التحميل
    application.add_handler(CallbackQueryHandler(
        handle_download_cancel,
        pattern="^download_cancel$"
    ))

    # 8. Handler لاختيار الجودة - النظام القديم (Callback Query)
    # هذا للتوافق مع النظام القديم - الأنماط العامة
    application.add_handler(CallbackQueryHandler(
        handle_quality_selection,
        pattern="^quality_"
    ))

    # 9. Handler للأزرار التفاعلية (Callback Query)
    application.add_handler(CallbackQueryHandler(
        handle_vip_buttons,
        pattern="^(vip_payment|contact_support|vip_details)$"
    ))

    # 10. Handler لأزرار الدعم (Callback Query)
    application.add_handler(CallbackQueryHandler(
        show_qr_code,
        pattern="^support_show_qr$"
    ))
    application.add_handler(CallbackQueryHandler(
        support_back,
        pattern="^support_back$"
    ))

    # 11. Handler لأزرار نظام الإحالة (Callback Query)
    application.add_handler(CallbackQueryHandler(
        handle_referral_callback,
        pattern="^(refresh_referral_stats|copy_referral_)"
    ))

    # 12. Handler للوحة تحكم الأدمن
    application.add_handler(admin_conv_handler)

    # 13. Handler لتحميل الفيديوهات من الروابط (يجب أن يكون الأخير)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"https?://\S+"),
            handle_download,
        )
    )
    
    logger.info("✅ تم تسجيل جميع المعالجات بنجاح.")
    logger.info("=" * 50)

    # Mission 10: جدولة التقرير اليومي
    try:
        from utils import setup_daily_report_job
        setup_daily_report_job(application)
    except Exception as e:
        logger.error(f"❌ فشل جدولة التقرير اليومي: {e}")

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
