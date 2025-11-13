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

# استيراد المكونات من الهيكل الجديد
from handlers.user import (
    start,
    select_language,
    handle_menu_buttons,
    account_info,
    test_subscription,
    referral_command,
    handle_referral_callback,
    show_support_message,
    show_qr_code,
    support_back
)
from handlers.download import (
    handle_download,
    handle_quality_selection,
    cancel_download,
    cancel_download_callback,
    handle_batch_download,
    handle_playlist_download,
    handle_batch_quality_choice,
    toggle_video_selection,
    proceed_to_quality_selection,
    is_playlist_url,
    handle_multi_download,
    show_mode_selection,
    show_quality_selection as show_multi_quality_selection,
    show_audio_format_selection,
    download_videos,
    download_audio,
    handle_download_cancel,
    handle_video_message
)
from handlers.admin import admin_conv_handler
from handlers.general import handle_reactive_response
from handlers.notifications import (
    send_startup_notification,
    send_shutdown_notification,
    send_error_notification,
    send_update_notification,
    announce_new_bot
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

# Validate LOG_CHANNEL_ID
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
if LOG_CHANNEL_ID:
    try:
        LOG_CHANNEL_ID = int(LOG_CHANNEL_ID)
        logger.info(f"✅ LOG_CHANNEL_ID validated: {LOG_CHANNEL_ID}")
    except (ValueError, TypeError):
        logger.error(f"❌ LOG_CHANNEL_ID invalid: {LOG_CHANNEL_ID}")
        LOG_CHANNEL_ID = None
else:
    logger.warning("⚠️ LOG_CHANNEL_ID not configured")
    LOG_CHANNEL_ID = None

# باقي الكود كما هو...
async def forward_to_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إعادة توجيه الرسائل إلى قناة اللوج"""
    # Guard against non-message updates (e.g., callback queries)
    if not getattr(update, "message", None):
        return

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

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج زر Help من الأزرار التفاعلية"""
    from database import get_user_language, is_admin
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    query = update.callback_query
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    update_user_interaction(user_id)

    await query.answer()

    help_text = get_message(lang, "help_message")

    # إنشاء أزرار القائمة
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

    await query.edit_message_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

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


async def self_test(application: Application):
    """نظام اختبار ذاتي للتحقق من المعالجات"""
    logger.info("🧪 Running self-test...")

    # Test critical handlers
    test_handlers = [
        "cancel_download_callback",
        "toggle_video_selection",
        "proceed_to_quality_selection",
        "handle_batch_quality_choice",
        "handle_playlist_download",
        "handle_reactive_response"
    ]

    passed = 0
    failed = 0

    for handler_name in test_handlers:
        try:
            # Check if handler exists in imports
            handler_exists = handler_name in globals()
            if handler_exists:
                logger.info(f"✅ Handler OK: {handler_name}")
                passed += 1
            else:
                logger.warning(f"❌ Missing handler: {handler_name}")
                failed += 1
        except Exception as e:
            logger.error(f"❌ Error checking {handler_name}: {e}")
            failed += 1

    logger.info(f"🧩 Self-test complete: {passed} passed, {failed} failed")
    return passed, failed


async def post_init(application: Application):
    """يتم تنفيذه بعد تهيئة البوت"""
    logger.info("🚀 بدء إعداد قائمة الأوامر...")
    await setup_bot_menu(application.bot)
    logger.info("✅ تم إعداد قائمة الأوامر بنجاح!")

    # إرسال تقارير بدء التشغيل
    await send_startup_reports(application)

    # Self-test
    await self_test(application)

    # إرسال إشعار التشغيل لقناة التحديثات
    await send_startup_notification(application.bot)

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

    # تحقق من وجود cryptography (V5.0.1 Hotfix)
    try:
        from cryptography.fernet import Fernet
        logger.info("✅ cryptography module verified (AES-256 ready)")
    except ImportError:
        logger.warning("⚠️ Missing dependency: cryptography")
        logger.info("🔄 Installing cryptography automatically...")
        try:
            import subprocess
            result = subprocess.run(
                ["pip", "install", "cryptography>=42.0.0"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60
            )
            if result.returncode == 0:
                logger.info("✅ cryptography installed successfully")
                # Verify installation
                from cryptography.fernet import Fernet
                logger.info("✅ cryptography module verified (AES-256 ready)")
            else:
                logger.error("❌ Failed to install cryptography automatically")
                logger.error("Please run manually: pip install cryptography>=42.0.0")
        except Exception as install_error:
            logger.error(f"❌ Auto-install failed: {install_error}")
            logger.error("Please run manually: pip install cryptography>=42.0.0")

    # تحميل الإعدادات
    load_config()
    config = get_config()

    # إنشاء المجلدات الضرورية إذا لم تكن موجودة
    try:
        os.makedirs("videos", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        logger.info("✅ تم التحقق من المجلدات الضرورية (videos, logs)")
    except Exception as e:
        logger.warning(f"⚠️ فشل إنشاء المجلدات: {e}")

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

    # 1.5. Handler للتفاعلات التلقائية (emoji reactions)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reactive_response),
        group=-2
    )

    # 2. أوامر البداية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("referral", referral_command))
    
    # 3. معلومات الحساب
    application.add_handler(CommandHandler("account", account_info))
    application.add_handler(CommandHandler("testsub", test_subscription))

    # 3.3. Health Check & Auto-Report System
    try:
        from handlers.admin.health_check import run_health_check, show_cookie_upload_info
        application.add_handler(CommandHandler("healthcheck", run_health_check))
        application.add_handler(CommandHandler("cookieinfo", show_cookie_upload_info))
        logger.info("✅ تم تسجيل معالجات الفحص الصحي والتقارير التلقائية")
    except Exception as e:
        logger.error(f"❌ فشل تسجيل معالجات الفحص الصحي: {e}")

    # 3.5. Per-user cancel download + batch YouTube download
    application.add_handler(CommandHandler("cancel", cancel_download))
    application.add_handler(CommandHandler("batch", handle_batch_download))

    # 4. Handler للفيديوهات المرسلة
    application.add_handler(MessageHandler(filters.VIDEO, handle_video_message))

    # 4.5. Cookie Management V5.0: Handler لرفع ملفات cookies
    try:
        from handlers.cookie_manager import handle_cookie_upload
        application.add_handler(MessageHandler(filters.Document.ALL, handle_cookie_upload))
        logger.info("✅ تم تسجيل معالج رفع ملفات Cookies")
    except Exception as e:
        logger.error(f"❌ فشل تسجيل معالج رفع ملفات Cookies: {e}")

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

    # 7.5. Playlist handlers (cancel button, batch quality choice, video selection)
    application.add_handler(CallbackQueryHandler(
        cancel_download_callback,
        pattern="^cancel:"
    ))
    application.add_handler(CallbackQueryHandler(
        handle_batch_quality_choice,
        pattern="^batch_quality:"
    ))
    application.add_handler(CallbackQueryHandler(
        toggle_video_selection,
        pattern="^toggle_video:"
    ))
    application.add_handler(CallbackQueryHandler(
        proceed_to_quality_selection,
        pattern="^proceed_selection:"
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

    # 11.5. Handler لزر Help (Callback Query)
    application.add_handler(CallbackQueryHandler(
        handle_help,
        pattern="^help$"
    ))

    # 11.6. Handler لأمر /admin موجود داخل admin_conv_handler كـ entry_point
    # لا نحتاج معالج خارجي هنا لتجنب التعارض

    # 11.8. Handlers للأزرار الداخلية في لوحة الادمن (قبل ConversationHandler للأولوية)
    # ملاحظة: معظم هذه الدوال الآن داخل admin_conv_handler
    # استيراد handlers من cookie_manager
    from handlers.cookie_manager import (
        confirm_delete_all_cookies_callback,
        cancel_delete_cookies_callback
    )

    # معظم معالجات الأدمن موجودة داخل admin_conv_handler
    # هنا فقط المعالجات التي يجب أن تعمل خارج ConversationHandler
    # broadcast_all_start و broadcast_individual_start محذوفة من هنا لأنها داخل ConversationHandler

    # Handlers لأزرار التأكيد في Cookies
    application.add_handler(CallbackQueryHandler(confirm_delete_all_cookies_callback, pattern="^confirm_delete_all_cookies$"))
    application.add_handler(CallbackQueryHandler(cancel_delete_cookies_callback, pattern="^cancel_delete_cookies$"))

    # 12. Handler للوحة تحكم الأدمن (للحالات المعقدة فقط - يأتي بعد handlers الأساسية)
    application.add_handler(admin_conv_handler)

    # 12.5. Playlist URL handler (before general download handler)
    async def playlist_or_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج ذكي للتمييز بين playlist والروابط العادية"""
        url = update.message.text.strip()
        if is_playlist_url(url):
            await handle_playlist_download(update, context)
        else:
            await handle_download(update, context)

    # 13. Handler لتحميل الفيديوهات من الروابط (يجب أن يكون الأخير)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"https?://\S+"),
            playlist_or_download,
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

    # Cookie Management V5.0: جدولة الفحص الأسبوعي للـ cookies
    try:
        from utils import setup_cookie_check_job
        setup_cookie_check_job(application)
        logger.info("✅ تم جدولة الفحص الأسبوعي للـ cookies بنجاح")
    except Exception as e:
        logger.error(f"❌ فشل جدولة الفحص الأسبوعي للـ cookies: {e}")

    # تشغيل البوت
    try:
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

    except KeyboardInterrupt:
        logger.info("⏹️ تم إيقاف البوت بواسطة المستخدم")
        import asyncio
        asyncio.run(send_shutdown_notification(application.bot, reason="إيقاف يدوي / Manual stop"))

    except Exception as e:
        logger.error(f"❌ خطأ فادح في تشغيل البوت: {e}")
        import asyncio
        asyncio.run(send_error_notification(
            application.bot,
            error_type="Critical Runtime Error",
            error_message=str(e)
        ))
        asyncio.run(send_shutdown_notification(application.bot, reason=f"خطأ فادح / Critical error: {str(e)[:50]}"))
        raise

    finally:
        logger.info("🔚 إغلاق البوت...")

if __name__ == "__main__":
    main()
