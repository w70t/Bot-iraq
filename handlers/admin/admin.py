import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from datetime import datetime, timedelta

from database import (
    get_all_users,
    get_user,
    add_subscription,
    is_admin,
    get_user_language,
    get_total_downloads_count,
    get_global_settings,
    set_subscription_enabled,
    set_welcome_broadcast_enabled,
    is_subscription_enabled,
    is_welcome_broadcast_enabled,
    get_daily_download_stats,
    generate_daily_report
)
from utils import get_message, escape_markdown, admin_only, validate_user_id, validate_days, log_warning
from handlers.cookie_manager import confirm_delete_all_cookies_callback, cancel_delete_cookies_callback

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ThreadPoolExecutor for async subprocess execution
executor = ThreadPoolExecutor(max_workers=3)

# حالات المحادثة
MAIN_MENU, AWAITING_USER_ID, AWAITING_DAYS, BROADCAST_MESSAGE, AWAITING_CUSTOM_PRICE, AWAITING_AUDIO_LIMIT, AWAITING_TIME_LIMIT, AWAITING_DAILY_LIMIT, AWAITING_USER_ID_BROADCAST, AWAITING_MESSAGE_BROADCAST, AWAITING_PLATFORM_COOKIE = range(11)

async def admin_command_simple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج بسيط جداً لأمر /admin - خارج ConversationHandler تماماً"""
    user_id = update.effective_user.id

    logger.info(f"🔍 [SIMPLE] Admin command /admin received from user {user_id}")

    # التحقق من صلاحيات الأدمن
    if not is_admin(user_id):
        from database import get_user_language
        lang = get_user_language(user_id)
        error_msg = (
            "⛔ عذراً، هذا الأمر مخصص للمدراء فقط"
            if lang == 'ar' else
            "⛔ Sorry, this command is for admins only"
        )
        logger.info(f"❌ User {user_id} is not admin - access denied")
        await update.message.reply_text(error_msg)
        return

    # إذا كان أدمن، عرض لوحة التحكم
    logger.info(f"✅ User {user_id} is admin - showing admin panel")

    try:
        from database import is_logo_enabled, get_allowed_platforms

        logo_status = is_logo_enabled()
        logo_text = "✅ مفعّل" if logo_status else "❌ معطّل"

        allowed_platforms = get_allowed_platforms()
        enabled_platforms = len(allowed_platforms)
        library_status = f"{enabled_platforms}/10 منصات"

        sub_enabled = is_subscription_enabled()
        sub_status = "✅" if sub_enabled else "🚫"

        keyboard = [
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("📥 سجل التحميلات", callback_data="admin_download_logs")],
            [InlineKeyboardButton("⭐ ترقية عضو", callback_data="admin_upgrade")],
            [InlineKeyboardButton(f"💎 التحكم بالاشتراك ({sub_status})", callback_data="admin_vip_control")],
            [InlineKeyboardButton("⚙️ إعدادات القيود العامة", callback_data="admin_general_limits")],
            [InlineKeyboardButton(f"🎨 اللوجو ({logo_text})", callback_data="admin_logo")],
            [InlineKeyboardButton(f"📚 المكتبات ({library_status})", callback_data="admin_libraries")],
            [InlineKeyboardButton("🧾 بلاغات المستخدمين", callback_data="admin_error_reports")],
            [InlineKeyboardButton("👥 قائمة الأعضاء", callback_data="admin_list_users")],
            [InlineKeyboardButton("📢 إرسال رسالة جماعية", callback_data="admin_broadcast")],
            [InlineKeyboardButton("❌ إغلاق", callback_data="admin_close")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = (
            "🔐 **لوحة تحكم المدير**\n\n"
            "اختر الإجراء المطلوب:"
        )

        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"✅ Admin panel sent successfully to user {user_id}")
    except Exception as e:
        logger.error(f"❌ Error in admin_command_simple: {e}", exc_info=True)
        await update.message.reply_text("❌ حدث خطأ، الرجاء المحاولة مرة أخرى")

async def handle_admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج زر Admin Panel من الأزرار التفاعلية - مستقل عن ConversationHandler"""
    query = update.callback_query
    user_id = query.from_user.id

    logger.info(f"🔘 Admin panel button pressed by user {user_id}")

    # التحقق من صلاحيات الأدمن
    if not is_admin(user_id):
        # الحصول على لغة المستخدم
        from database import get_user_language
        lang = get_user_language(user_id)

        # رسالة بحسب اللغة
        error_message = (
            "🔒 عذراً، هذا الزر مخصص للمدراء فقط!"
            if lang == 'ar' else
            "🔒 Sorry, this button is for admins only!"
        )
        logger.info(f"❌ User {user_id} tried to access admin panel - access denied")
        await query.answer(error_message, show_alert=True)
        return

    # إذا كان أدمن، عرض لوحة التحكم مباشرة
    logger.info(f"✅ User {user_id} is admin - showing admin panel from button")

    try:
        # جلب حالات الإعدادات
        from database import is_logo_enabled, get_allowed_platforms
        logo_status = is_logo_enabled()
        logo_text = "✅ مفعّل" if logo_status else "❌ معطّل"

        allowed_platforms = get_allowed_platforms()
        total_platforms = 11  # ⭐ جميع المنصات المدعومة (بما فيها Threads)
        enabled_platforms = len(allowed_platforms)
        library_status = f"{enabled_platforms}/{total_platforms} منصات"

        sub_enabled = is_subscription_enabled()
        sub_status = "✅" if sub_enabled else "🚫"

        keyboard = [
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("📥 سجل التحميلات", callback_data="admin_download_logs")],
            [InlineKeyboardButton("⭐ ترقية عضو", callback_data="admin_upgrade")],
            [InlineKeyboardButton(f"💎 التحكم بالاشتراك ({sub_status})", callback_data="admin_vip_control")],
            [InlineKeyboardButton("⚙️ إعدادات القيود العامة", callback_data="admin_general_limits")],
            [InlineKeyboardButton(f"🎨 اللوجو ({logo_text})", callback_data="admin_logo")],
            [InlineKeyboardButton(f"📚 المكتبات ({library_status})", callback_data="admin_libraries")],
            [InlineKeyboardButton("🧾 بلاغات المستخدمين", callback_data="admin_error_reports")],
            [InlineKeyboardButton("👥 قائمة الأعضاء", callback_data="admin_list_users")],
            [InlineKeyboardButton("📢 إرسال رسالة جماعية", callback_data="admin_broadcast")],
            [InlineKeyboardButton("❌ إغلاق", callback_data="admin_close")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = (
            "🔐 **لوحة تحكم المدير**\n\n"
            "اختر الإجراء المطلوب:"
        )

        await query.answer()
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"✅ Admin panel displayed successfully for user {user_id}")
    except Exception as e:
        logger.error(f"❌ Error showing admin panel: {e}")
        await query.answer("❌ حدث خطأ، الرجاء المحاولة مرة أخرى", show_alert=True)

async def admin_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج بسيط لأمر /admin - entry point في ConversationHandler"""
    try:
        user_id = update.effective_user.id

        logger.info(f"🔍 [ADMIN_CMD_HANDLER] Admin command received from user {user_id}")
        logger.info(f"🔍 [ADMIN_CMD_HANDLER] Update type: {type(update)}")
        logger.info(f"🔍 [ADMIN_CMD_HANDLER] Has message: {update.message is not None}")
        logger.info(f"🔍 [ADMIN_CMD_HANDLER] Has callback_query: {update.callback_query is not None}")

        # التحقق من صلاحيات الأدمن
        if not is_admin(user_id):
            # الحصول على لغة المستخدم
            from database import get_user_language
            lang = get_user_language(user_id)
            error_msg = (
                "⛔ عذراً، هذا الأمر مخصص للمدراء فقط"
                if lang == 'ar' else
                "⛔ Sorry, this command is for admins only"
            )
            logger.info(f"❌ [ADMIN_CMD_HANDLER] User {user_id} is not admin - access denied")
            await update.message.reply_text(error_msg)
            return ConversationHandler.END

        # إذا كان أدمن، استدعي admin_panel
        logger.info(f"✅ [ADMIN_CMD_HANDLER] User {user_id} is admin - calling admin_panel")
        result = await admin_panel(update, context)
        logger.info(f"✅ [ADMIN_CMD_HANDLER] admin_panel returned: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ [ADMIN_CMD_HANDLER] CRITICAL ERROR: {e}", exc_info=True)
        if update.message:
            await update.message.reply_text(f"❌ خطأ حرج: {e}")
        return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة التحكم الرئيسية"""
    try:
        user_id = update.effective_user.id

        logger.info(f"📋 [ADMIN_PANEL] Called by user {user_id}")
        logger.info(f"📋 [ADMIN_PANEL] Update type: {type(update)}")
        logger.info(f"📋 [ADMIN_PANEL] Has message: {update.message is not None}")
        logger.info(f"📋 [ADMIN_PANEL] Has callback_query: {update.callback_query is not None}")

        if update.callback_query:
            logger.info(f"📋 [ADMIN_PANEL] Callback data: {update.callback_query.data}")

        # ✅ فحص صلاحيات الأدمن
        logger.info(f"📋 [ADMIN_PANEL] Checking admin privileges for user {user_id}")
        if not is_admin(user_id):
            logger.warning(f"⚠️ [ADMIN_PANEL] User {user_id} is not admin!")
            error_msg = "⛔ عذراً، هذا الأمر مخصص للمدراء فقط"
            if update.callback_query:
                await update.callback_query.answer(error_msg, show_alert=True)
                return ConversationHandler.END
            else:
                await update.message.reply_text(error_msg)
                return ConversationHandler.END

        logger.info(f"✅ [ADMIN_PANEL] User {user_id} is admin - proceeding")

        # جلب حالة اللوجو
        logger.info(f"📋 [ADMIN_PANEL] Fetching logo status")
        from database import is_logo_enabled
        logo_status = is_logo_enabled()
        logo_text = "✅ مفعّل" if logo_status else "❌ معطّل"

        # جلب حالة المكتبات
        logger.info(f"📋 [ADMIN_PANEL] Fetching library settings")
        from database import get_allowed_platforms, get_library_settings
        settings = get_library_settings()
        allowed_platforms = get_allowed_platforms()
        # ⭐ تحديث العدد الإجمالي للمنصات المدعومة
        total_platforms = 11  # ⭐ جميع المنصات المدعومة (بما فيها Threads)
        enabled_platforms = len(allowed_platforms)
        library_status = f"{enabled_platforms}/{total_platforms} منصات"

        # جلب حالة الاشتراك
        logger.info(f"📋 [ADMIN_PANEL] Fetching subscription status")
        sub_enabled = is_subscription_enabled()
        sub_status = "✅" if sub_enabled else "🚫"

        logger.info(f"📋 [ADMIN_PANEL] Building keyboard")
        keyboard = [
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("📥 سجل التحميلات", callback_data="admin_download_logs")],
            [InlineKeyboardButton("⭐ ترقية عضو", callback_data="admin_upgrade")],
            [InlineKeyboardButton(f"💎 التحكم بالاشتراك ({sub_status})", callback_data="admin_vip_control")],
            [InlineKeyboardButton("⚙️ إعدادات القيود العامة", callback_data="admin_general_limits")],
            [InlineKeyboardButton(f"🎨 اللوجو ({logo_text})", callback_data="admin_logo")],
            [InlineKeyboardButton(f"📚 المكتبات ({library_status})", callback_data="admin_libraries")],
            [InlineKeyboardButton("🧾 بلاغات المستخدمين", callback_data="admin_error_reports")],
            [InlineKeyboardButton("👥 قائمة الأعضاء", callback_data="admin_list_users")],
            [InlineKeyboardButton("📢 إرسال رسالة جماعية", callback_data="admin_broadcast")],
            [InlineKeyboardButton("❌ إغلاق", callback_data="admin_close")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        message_text = (
            "🔐 **لوحة تحكم المدير**\n\n"
            "اختر الإجراء المطلوب:"
        )

        if update.callback_query:
            logger.info(f"📲 [ADMIN_PANEL] Sending via callback_query edit")
            await update.callback_query.answer(cache_time=0)  # Stop spinner immediately
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            logger.info(f"📨 [ADMIN_PANEL] Sending via message reply")
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

        logger.info(f"✅ [ADMIN_PANEL] Sent successfully, returning MAIN_MENU state")
        return MAIN_MENU
    except Exception as e:
        logger.error(f"❌ [ADMIN_PANEL] CRITICAL ERROR: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.answer(f"❌ خطأ: {e}", show_alert=True)
        elif update.message:
            await update.message.reply_text(f"❌ خطأ: {e}")
        return ConversationHandler.END

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإحصائيات"""
    query = update.callback_query
    await query.answer()
    
    all_users = get_all_users()
    total_users = len(all_users)
    
    vip_users = [u for u in all_users if u.get('subscription_end')]
    total_vip = len(vip_users)
    
    total_downloads = get_total_downloads_count()
    
    stats_text = (
        "📊 **إحصائيات البوت**\n\n"
        f"👥 إجمالي المستخدمين: `{total_users}`\n"
        f"⭐ مشتركين VIP: `{total_vip}`\n"
        f"🆓 مستخدمين مجانيين: `{total_users - total_vip}`\n"
        f"📥 إجمالي التحميلات: `{total_downloads}`\n\n"
        f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

async def show_download_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    عرض سجل التحميلات اليومي (Mission 10)
    """
    query = update.callback_query
    await query.answer()

    # جلب إحصائيات اليوم
    report = generate_daily_report()

    keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        report,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU

async def upgrade_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض خيارات إدارة الاشتراكات"""
    query = update.callback_query
    await query.answer()

    text = (
        "⭐ إدارة اشتراكات الأعضاء\n\n"
        "اختر الإجراء المطلوب:"
    )

    keyboard = [
        [InlineKeyboardButton("➕ إضافة اشتراك", callback_data="admin_add_subscription")],
        [InlineKeyboardButton("➖ إلغاء اشتراك", callback_data="admin_cancel_subscription")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )

    return MAIN_MENU

async def admin_add_subscription_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية إضافة اشتراك"""
    query = update.callback_query
    await query.answer()

    text = (
        "➕ إضافة اشتراك جديد\n\n"
        "أرسل أحد التالي:\n\n"
        "1️⃣ User ID (رقم):\n"
        "   مثال: 123456789\n\n"
        "2️⃣ Username:\n"
        "   مثال: @username أو username\n\n"
        "💡 يمكنك الحصول على User ID من:\n"
        "• معلومات الحساب\n"
        "• رسائل السجل في القناة\n"
        "• أمر /account من المستخدم"
    )

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )

    return AWAITING_USER_ID

async def receive_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال معرف المستخدم أو اليوزر نيم"""
    # التحقق من الوضع: إلغاء اشتراك أم إضافة اشتراك
    if context.user_data.get('cancel_subscription_mode'):
        return await receive_user_id_for_cancel(update, context)

    user_input = update.message.text.strip()
    user_id = None
    user_data = None

    # محاولة التعامل مع Username
    if user_input.startswith('@') or not user_input.isdigit():
        username = user_input.replace('@', '')  # إزالة @ إذا وجدت

        # البحث عن المستخدم بالـ username
        all_users = get_all_users()
        for user in all_users:
            if user.get('username') == username:
                user_id = user.get('user_id')
                user_data = user
                break

        if not user_id:
            await update.message.reply_text(
                f"❌ لم أجد مستخدم بالـ username: {username}\n\n"
                f"💡 تأكد من:\n"
                f"• اليوزر نيم صحيح\n"
                f"• المستخدم أرسل /start للبوت"
            )
            return AWAITING_USER_ID

    # محاولة التعامل مع User ID
    else:
        # التحقق من صحة معرف المستخدم
        is_valid, validated_user_id, error_msg = validate_user_id(user_input)

        if not is_valid:
            await update.message.reply_text(
                f"❌ {error_msg}\n\n"
                "أرسل:\n"
                "• User ID (رقم): مثال 123456789\n"
                "• أو Username: مثال @username"
            )
            return AWAITING_USER_ID

        user_id = validated_user_id
        user_data = get_user(user_id)

        if not user_data:
            await update.message.reply_text(
                "❌ المستخدم غير موجود في قاعدة البيانات!\n"
                "تأكد من أن المستخدم قام بإرسال /start للبوت."
            )
            return AWAITING_USER_ID

    context.user_data['upgrade_target_id'] = user_id

    user_name = user_data.get('full_name', 'غير معروف')
    username = user_data.get('username', 'لا يوجد')

    text = (
        f"✅ تم العثور على المستخدم:\n\n"
        f"👤 الاسم: {user_name}\n"
        f"🆔 المعرف: {user_id}\n"
        f"🔗 اليوزر: @{username if username != 'لا يوجد' else 'غير متوفر'}\n\n"
        f"📅 أرسل عدد الأيام للاشتراك:\n"
        f"مثال: 30 (شهر) | 365 (سنة)"
    )

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text,
        reply_markup=reply_markup
    )

    return AWAITING_DAYS

async def receive_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال عدد الأيام وإتمام الترقية"""
    days_text = update.message.text.strip()

    # التحقق من صحة عدد الأيام
    is_valid, days, error_msg = validate_days(days_text)

    if not is_valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nأرسل رقم موجب (مثال: 30)")
        return AWAITING_DAYS
    
    user_id = context.user_data.get('upgrade_target_id')
    
    if not user_id:
        await update.message.reply_text("❌ حدث خطأ! أعد المحاولة.")
        return ConversationHandler.END
    
    subscription_end = datetime.now() + timedelta(days=days)
    
    if add_subscription(user_id, subscription_end):
        user_data = get_user(user_id)
        user_name = user_data.get('full_name', 'المستخدم')
        
        success_text = (
            f"✅ تمت الترقية بنجاح!\n\n"
            f"👤 المستخدم: {user_name}\n"
            f"🆔 المعرف: {user_id}\n"
            f"📅 المدة: {days} يوم\n"
            f"⏰ تنتهي في: {subscription_end.strftime('%Y-%m-%d')}\n\n"
            f"🎉 تم إرسال إشعار للمستخدم"
        )
        
        await update.message.reply_text(success_text)
        
        # إرسال إشعار للمستخدم
        try:
            notification_text = (
                f"🎉 مبروك! تمت ترقيتك إلى VIP\n\n"
                f"⭐ مدة الاشتراك: {days} يوم\n"
                f"📅 ينتهي في: {subscription_end.strftime('%Y-%m-%d')}\n\n"
                f"✨ الآن يمكنك:\n"
                f"• تحميل بلا حدود ♾️\n"
                f"• فيديوهات بدون لوجو 🎨\n"
                f"• جودات عالية 4K/HD 📺\n"
                f"• أولوية في المعالجة ⚡\n\n"
                f"💎 شكراً لاشتراكك معنا!"
            )
            
            await context.bot.send_message(
                chat_id=user_id,
                text=notification_text
            )
            logger.info(f"✅ تم إرسال إشعار الترقية للمستخدم {user_id}")
        except Exception as e:
            log_warning(f"⚠️ فشل إرسال الإشعار للمستخدم {user_id}: {e}", module="handlers/admin.py")
        
        del context.user_data['upgrade_target_id']
        
        keyboard = [[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="admin_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "اختر الإجراء التالي:",
            reply_markup=reply_markup
        )
        
        return MAIN_MENU
    else:
        await update.message.reply_text("❌ فشلت عملية الترقية!")
        return ConversationHandler.END

async def admin_cancel_subscription_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية إلغاء اشتراك"""
    query = update.callback_query
    await query.answer()

    text = (
        "➖ إلغاء اشتراك عضو\n\n"
        "أرسل أحد التالي:\n\n"
        "1️⃣ User ID (رقم):\n"
        "   مثال: 123456789\n\n"
        "2️⃣ Username:\n"
        "   مثال: @username أو username\n\n"
        "💡 يمكنك الحصول على User ID من:\n"
        "• معلومات الحساب\n"
        "• رسائل السجل في القناة\n"
        "• أمر /account من المستخدم"
    )

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )

    # حفظ علامة أن هذا طلب إلغاء اشتراك
    context.user_data['cancel_subscription_mode'] = True

    return AWAITING_USER_ID

async def receive_user_id_for_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال معرف المستخدم لإلغاء الاشتراك"""
    user_input = update.message.text.strip()
    user_id = None
    user_data = None

    # محاولة التعامل مع Username
    if user_input.startswith('@') or not user_input.isdigit():
        username = user_input.replace('@', '')

        # البحث عن المستخدم بالـ username
        all_users = get_all_users()
        for user in all_users:
            if user.get('username') == username:
                user_id = user.get('user_id')
                user_data = user
                break

        if not user_id:
            await update.message.reply_text(
                f"❌ لم أجد مستخدم بالـ username: {username}\n\n"
                f"💡 تأكد من:\n"
                f"• اليوزر نيم صحيح\n"
                f"• المستخدم أرسل /start للبوت"
            )
            return AWAITING_USER_ID

    # محاولة التعامل مع User ID
    else:
        is_valid, validated_user_id, error_msg = validate_user_id(user_input)

        if not is_valid:
            await update.message.reply_text(
                f"❌ {error_msg}\n\n"
                "أرسل:\n"
                "• User ID (رقم): مثال 123456789\n"
                "• أو Username: مثال @username"
            )
            return AWAITING_USER_ID

        user_id = validated_user_id
        user_data = get_user(user_id)

        if not user_data:
            await update.message.reply_text(
                "❌ المستخدم غير موجود في قاعدة البيانات!\n"
                "تأكد من أن المستخدم قام بإرسال /start للبوت."
            )
            return AWAITING_USER_ID

    # التحقق من وجود اشتراك
    subscription_end = user_data.get('subscription_end')
    if not subscription_end:
        await update.message.reply_text(
            "⚠️ هذا المستخدم ليس لديه اشتراك VIP نشط!"
        )
        return ConversationHandler.END

    context.user_data['cancel_target_id'] = user_id

    user_name = user_data.get('full_name', 'غير معروف')
    username = user_data.get('username', 'لا يوجد')

    text = (
        f"⚠️ تأكيد إلغاء الاشتراك\n\n"
        f"👤 الاسم: {user_name}\n"
        f"🆔 المعرف: {user_id}\n"
        f"🔗 اليوزر: @{username if username != 'لا يوجد' else 'غير متوفر'}\n"
        f"📅 الاشتراك ينتهي في: {subscription_end}\n\n"
        f"❓ هل أنت متأكد من إلغاء الاشتراك؟"
    )

    keyboard = [
        [InlineKeyboardButton("✅ نعم، إلغاء الاشتراك", callback_data="confirm_cancel_sub")],
        [InlineKeyboardButton("❌ لا، إلغاء العملية", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text,
        reply_markup=reply_markup
    )

    return MAIN_MENU

async def confirm_cancel_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد وتنفيذ إلغاء الاشتراك"""
    query = update.callback_query
    await query.answer()

    user_id = context.user_data.get('cancel_target_id')

    if not user_id:
        await query.edit_message_text("❌ حدث خطأ! أعد المحاولة.")
        return ConversationHandler.END

    # حذف الاشتراك من قاعدة البيانات
    from database import remove_subscription

    if remove_subscription(user_id):
        user_data = get_user(user_id)
        user_name = user_data.get('full_name', 'المستخدم')

        success_text = (
            f"✅ تم إلغاء الاشتراك بنجاح!\n\n"
            f"👤 المستخدم: {user_name}\n"
            f"🆔 المعرف: {user_id}\n\n"
            f"🔔 تم إرسال إشعار للمستخدم"
        )

        await query.edit_message_text(success_text)

        # إرسال إشعار للمستخدم
        try:
            notification_text = (
                f"⚠️ تم إلغاء اشتراك VIP الخاص بك\n\n"
                f"📌 تم إلغاء اشتراكك من قبل الإدارة\n"
                f"💡 للحصول على اشتراك جديد، يرجى التواصل مع الدعم\n\n"
                f"شكراً لاستخدامك البوت 🙏"
            )

            await context.bot.send_message(
                chat_id=user_id,
                text=notification_text
            )
            logger.info(f"✅ تم إرسال إشعار إلغاء الاشتراك للمستخدم {user_id}")
        except Exception as e:
            log_warning(f"⚠️ فشل إرسال الإشعار للمستخدم {user_id}: {e}", module="handlers/admin.py")

        del context.user_data['cancel_target_id']
        if 'cancel_subscription_mode' in context.user_data:
            del context.user_data['cancel_subscription_mode']

        keyboard = [[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="admin_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "اختر الإجراء التالي:",
            reply_markup=reply_markup
        )

        return MAIN_MENU
    else:
        await query.edit_message_text("❌ فشلت عملية إلغاء الاشتراك!")
        return ConversationHandler.END

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المستخدمين"""
    query = update.callback_query
    await query.answer()
    
    all_users = get_all_users()
    
    if not all_users:
        await query.edit_message_text("📭 لا يوجد مستخدمين حالياً")
        return MAIN_MENU
    
    users_text = "👥 قائمة المستخدمين (آخر 20)\n\n"
    
    for idx, user in enumerate(all_users[-20:], 1):
        user_id = user.get('user_id')
        name = user.get('full_name', 'غير معروف')[:20]
        username = user.get('username', 'لا يوجد')
        is_vip = "⭐" if user.get('subscription_end') else "🆓"
        
        users_text += f"{idx}. {is_vip} {user_id} - {name}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        users_text,
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

async def manage_logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة اللوجو - تفعيل/إيقاف واختيار الحركة والموضع والحجم والشفافية والفئة المستهدفة"""
    query = update.callback_query
    await query.answer()
    
    from database import (
        is_logo_enabled, 
        get_logo_animation,
        get_logo_position,
        get_logo_size,
        get_logo_opacity,
        get_logo_target
    )
    
    current_status = is_logo_enabled()
    status_text = "✅ مفعّل" if current_status else "❌ معطّل"
    
    # الحركة
    current_animation = get_logo_animation()
    animation_names = {
        'static': '📌 لوجو ثابت',
        'corner_rotation': '🔄 حركة الزوايا',
        'bounce': '⬆️ ارتداد',
        'slide': '➡️ انزلاق',
        'fade': '💫 ظهور/اختفاء',
        'zoom': '🔍 تكبير/تصغير'
    }
    animation_text = animation_names.get(current_animation, 'غير معروف')
    
    # الموضع
    current_position = get_logo_position()
    position_names = {
        'top_right': '📍 يمين أعلى',
        'top_left': '📍 يسار أعلى',
        'bottom_right': '📍 يمين أسفل',
        'bottom_left': '📍 يسار أسفل',
        'center': '⭐ وسط الشاشة',
        'top_center': '📍 وسط أعلى',
        'bottom_center': '📍 وسط أسفل',
        'center_right': '📍 وسط يمين',
        'center_left': '📍 وسط يسار'
    }
    position_text = position_names.get(current_position, 'غير معروف')
    
    # الحجم
    size_name, size_px = get_logo_size()
    size_names = {
        'small': '🔹 صغير',
        'medium': '🔸 متوسط',
        'large': '🔶 كبير'
    }
    size_text = f"{size_names.get(size_name, 'غير معروف')} ({size_px}px)"
    
    # الشفافية
    opacity_pct, _ = get_logo_opacity()
    
    # الفئة المستهدفة
    target_id, target_name = get_logo_target()
    
    text = (
        f"🎨 **إدارة اللوجو المتقدمة**\n\n"
        f"📊 **الإعدادات الحالية:**\n"
        f"• الحالة: {status_text}\n"
        f"• الحركة: {animation_text}\n"
        f"• الموضع: {position_text}\n"
        f"• الحجم: {size_text}\n"
        f"• الشفافية: {opacity_pct}%\n"
        f"• الفئة المستهدفة: {target_name}\n\n"
        f"⚠️ **تنبيه مهم:**\n"
        f"🔒 **اللوجو الثابت**: يبقى ثابت تماماً في الموضع المحدد (لا يتحرك)\n"
        f"⚡ **الحركات المتحركة**: تتحرك في المكان المحدد (وسط، تحت، إلخ)\n\n"
        f"💡 **ملاحظات:**\n"
        f"• يمكنك تحديد من سيظهر له اللوجو\n"
        f"• الشفافية الموصى بها: 60-80%\n"
        f"• كل حركة تحترم الموضع المختار من الأزرار\n\n"
        f"اختر الإعداد المطلوب:"
    )
    
    # تحديد زر التفعيل/الإيقاف حسب الحالة
    toggle_button = (
        InlineKeyboardButton("❌ تعطيل اللوجو", callback_data="logo_disable")
        if current_status
        else InlineKeyboardButton("✅ تفعيل اللوجو", callback_data="logo_enable")
    )

    keyboard = [
        [toggle_button],
        [InlineKeyboardButton("🎬 نوع الحركة", callback_data="logo_change_animation")],
        [InlineKeyboardButton("📍 موقع اللوجو", callback_data="logo_change_position")],
        [InlineKeyboardButton("📏 حجم اللوجو", callback_data="logo_change_size")],
        [InlineKeyboardButton("🎨 شفافية اللوجو", callback_data="logo_change_opacity")],
        [InlineKeyboardButton("🎯 الفئة المستهدفة", callback_data="logo_change_target")],
        [InlineKeyboardButton("↩️ العودة", callback_data="admin_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

async def show_animation_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة اختيار حركة اللوجو"""
    query = update.callback_query
    await query.answer()
    
    from database import get_logo_animation
    current_animation = get_logo_animation()
    
    text = (
        f"🎬 اختر حركة اللوجو:\n\n"
        f"الحركة الحالية: {current_animation}\n\n"
        f"📍 **شرح المميزات:**\n\n"
        f"🔒 **اللوجو الثابت**: يبقى ثابت تماماً في الموضع المحدد - لا يتحرك مطلقاً!\n"
        f"⚡ **الحركات المتحركة**: تتحرك في المكان المحدد (وسط، تحت، إلخ)\n\n"
        f"✅ **مثال**: إذا اخترت \"لوجو ثابت وسط أسفل\" → اللوجو يبقى ثابت تماماً في وسط أسفل الفيديو\n\n"
        f"جميع الحركات مع شفافية 70% للوضوح"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔒 لوجو ثابت (لا يتحرك)", callback_data="set_anim_static")],
        [InlineKeyboardButton("🔄 حركة الزوايا (متغير)", callback_data="set_anim_corner_rotation")],
        [InlineKeyboardButton("⬆️ ارتداد (متغير)", callback_data="set_anim_bounce")],
        [InlineKeyboardButton("➡️ انزلاق (متغير)", callback_data="set_anim_slide")],
        [InlineKeyboardButton("💫 ظهور/اختفاء (متغير)", callback_data="set_anim_fade")],
        [InlineKeyboardButton("🔍 تكبير/تصغير (متغير)", callback_data="set_anim_zoom")],
        [InlineKeyboardButton("🔙 العودة", callback_data="admin_logo")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

async def set_animation_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعيين نوع حركة اللوجو"""
    query = update.callback_query
    
    from database import set_logo_animation
    
    # استخراج نوع الحركة من callback_data
    animation_type = query.data.replace("set_anim_", "")
    
    animation_names = {
        'static': 'لوجو ثابت',
        'corner_rotation': 'حركة الزوايا',
        'bounce': 'ارتداد',
        'slide': 'انزلاق',
        'fade': 'ظهور/اختفاء',
        'zoom': 'تكبير/تصغير'
    }
    
    if set_logo_animation(animation_type):
        await query.answer(f"✅ تم تعيين حركة اللوجو إلى: {animation_names.get(animation_type)}", show_alert=True)
    else:
        await query.answer("❌ فشل تعيين الحركة!", show_alert=True)
    
    # العودة لقائمة إدارة اللوجو
    return await manage_logo(update, context)

async def show_position_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة اختيار موضع اللوجو"""
    query = update.callback_query
    await query.answer()
    
    from database import get_logo_position
    current_position = get_logo_position()
    
    position_names = {
        'top_right': 'يمين أعلى',
        'top_left': 'يسار أعلى',
        'bottom_right': 'يمين أسفل',
        'bottom_left': 'يسار أسفل',
        'center': 'وسط الشاشة',
        'top_center': 'وسط أعلى',
        'bottom_center': 'وسط أسفل',
        'center_right': 'وسط يمين',
        'center_left': 'وسط يسار'
    }
    
    text = (
        f"📍 **اختر موضع اللوجو:**\n\n"
        f"الموضع الحالي: **{position_names.get(current_position, 'غير معروف')}**\n\n"
        f"اختر الموضع المطلوب للوجو على الفيديو:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📍 يمين أعلى", callback_data="set_pos_top_right"),
         InlineKeyboardButton("📍 يسار أعلى", callback_data="set_pos_top_left")],
        [InlineKeyboardButton("📍 وسط أعلى", callback_data="set_pos_top_center")],
        [InlineKeyboardButton("📍 وسط يمين", callback_data="set_pos_center_right"),
         InlineKeyboardButton("⭐ وسط الشاشة", callback_data="set_pos_center"),
         InlineKeyboardButton("📍 وسط يسار", callback_data="set_pos_center_left")],
        [InlineKeyboardButton("📍 وسط أسفل", callback_data="set_pos_bottom_center")],
        [InlineKeyboardButton("📍 يمين أسفل", callback_data="set_pos_bottom_right"),
         InlineKeyboardButton("📍 يسار أسفل", callback_data="set_pos_bottom_left")],
        [InlineKeyboardButton("🔙 العودة", callback_data="admin_logo")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

async def set_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعيين موضع اللوجو"""
    query = update.callback_query
    
    from database import set_logo_position
    
    # استخراج الموضع من callback_data
    position = query.data.replace("set_pos_", "")
    
    position_names = {
        'top_right': 'يمين أعلى',
        'top_left': 'يسار أعلى',
        'bottom_right': 'يمين أسفل',
        'bottom_left': 'يسار أسفل',
        'center': 'وسط الشاشة',
        'top_center': 'وسط أعلى',
        'bottom_center': 'وسط أسفل',
        'center_right': 'وسط يمين',
        'center_left': 'وسط يسار'
    }
    
    if set_logo_position(position):
        await query.answer(f"✅ تم تعيين موضع اللوجو إلى: {position_names.get(position)}", show_alert=True)
    else:
        await query.answer("❌ فشل تعيين الموضع!", show_alert=True)
    
    # العودة لقائمة إدارة اللوجو
    return await manage_logo(update, context)

async def show_size_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة اختيار حجم اللوجو"""
    query = update.callback_query
    await query.answer()
    
    from database import get_logo_size
    size_name, size_px = get_logo_size()
    
    size_names = {
        'small': 'صغير (100px)',
        'medium': 'متوسط (150px)',
        'large': 'كبير (200px)'
    }
    
    text = (
        f"📏 **اختر حجم اللوجو:**\n\n"
        f"الحجم الحالي: **{size_names.get(size_name, 'غير معروف')}**\n\n"
        f"الحجم المتوسط موصى به لأغلب الفيديوهات 🎯"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔹 صغير (100px)", callback_data="set_size_small")],
        [InlineKeyboardButton("🔸 متوسط (150px) - موصى به ⭐", callback_data="set_size_medium")],
        [InlineKeyboardButton("🔶 كبير (200px)", callback_data="set_size_large")],
        [InlineKeyboardButton("🔙 العودة", callback_data="admin_logo")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

async def set_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعيين حجم اللوجو"""
    query = update.callback_query
    
    from database import set_logo_size
    
    # استخراج الحجم من callback_data
    size = query.data.replace("set_size_", "")
    
    size_names = {
        'small': 'صغير (100px)',
        'medium': 'متوسط (150px)',
        'large': 'كبير (200px)'
    }
    
    if set_logo_size(size):
        await query.answer(f"✅ تم تعيين حجم اللوجو إلى: {size_names.get(size)}", show_alert=True)
    else:
        await query.answer("❌ فشل تعيين الحجم!", show_alert=True)
    
    # العودة لقائمة إدارة اللوجو
    return await manage_logo(update, context)

async def show_opacity_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة اختيار شفافية اللوجو"""
    query = update.callback_query
    await query.answer()
    
    from database import get_logo_opacity
    opacity_pct, _ = get_logo_opacity()
    
    text = (
        f"💎 **اختر شفافية اللوجو:**\n\n"
        f"الشفافية الحالية: **{opacity_pct}%**\n\n"
        f"• 40-50%: شبه شفاف جداً\n"
        f"• 60-70%: متوسط - موصى به ⭐\n"
        f"• 80-90%: واضح جداً\n\n"
        f"الشفافية المتوسطة (60-70%) موازنة مثالية!"
    )
    
    keyboard = [
        [InlineKeyboardButton("40% - شبه شفاف", callback_data="set_opacity_40")],
        [InlineKeyboardButton("50% - شفاف", callback_data="set_opacity_50")],
        [InlineKeyboardButton("60% - متوسط خفيف ⭐", callback_data="set_opacity_60")],
        [InlineKeyboardButton("70% - متوسط (الحالي) ⭐", callback_data="set_opacity_70")],
        [InlineKeyboardButton("80% - واضح", callback_data="set_opacity_80")],
        [InlineKeyboardButton("90% - واضح جداً", callback_data="set_opacity_90")],
        [InlineKeyboardButton("🔙 العودة", callback_data="admin_logo")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

async def set_opacity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعيين شفافية اللوجو"""
    query = update.callback_query
    
    from database import set_logo_opacity
    
    # استخراج الشفافية من callback_data
    opacity = int(query.data.replace("set_opacity_", ""))
    
    if set_logo_opacity(opacity):
        await query.answer(f"✅ تم تعيين شفافية اللوجو إلى: {opacity}%", show_alert=True)
    else:
        await query.answer("❌ فشل تعيين الشفافية!", show_alert=True)
    
    # العودة لقائمة إدارة اللوجو
    return await manage_logo(update, context)


async def show_target_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة اختيار الفئة المستهدفة لتطبيق اللوجو - نسخة مبسطة"""
    query = update.callback_query
    await query.answer()

    from database import get_logo_target
    current_target, current_target_name = get_logo_target()

    text = (
        f"🎯 **اختر الفئة المستهدفة لتطبيق اللوجو:**\n\n"
        f"✅ **الإعداد الحالي:** {current_target_name}\n\n"
        f"💡 **الخيارات المتاحة:**\n"
        f"• 👥 الجميع: سيظهر اللوجو لكل المستخدمين\n"
        f"• 💎 المشتركين فقط: سيظهر اللوجو لمشتركي VIP فقط\n"
        f"• 🆓 غير المشتركين: سيظهر اللوجو لغير المشتركين فقط"
    )

    keyboard = [
        [InlineKeyboardButton("👥 الجميع (VIP + مجاني)", callback_data="logo_target_all")],
        [InlineKeyboardButton("💎 المشتركين فقط", callback_data="logo_target_vip")],
        [InlineKeyboardButton("🆓 غير المشتركين فقط", callback_data="logo_target_free")],
        [InlineKeyboardButton("↩️ العودة", callback_data="admin_logo")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU


async def handle_logo_target_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعيين الفئة المستهدفة لتطبيق اللوجو - نسخة مبسطة"""
    query = update.callback_query
    await query.answer()

    from database import set_logo_target

    # استخراج الفئة المستهدفة من callback_data
    target = query.data.replace("logo_target_", "")

    # القيم المبسطة والأسماء
    target_names = {
        'all': '👥 الجميع (VIP + مجاني)',
        'vip': '💎 المشتركين فقط',
        'free': '🆓 غير المشتركين فقط'
    }

    if target in target_names:
        set_logo_target(target)
        await query.answer(f"✅ تم تعيين الفئة المستهدفة إلى: {target_names[target]}", show_alert=True)
    else:
        await query.answer("❌ خطأ في اختيار الفئة!", show_alert=True)

    # العودة لقائمة إدارة اللوجو
    return await manage_logo(update, context)


async def toggle_logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تبديل حالة اللوجو"""
    query = update.callback_query
    action = query.data
    
    from database import set_logo_status
    
    if action == "logo_enable":
        set_logo_status(True)
        await query.answer("✅ تم تفعيل اللوجو المتحرك!", show_alert=True)
    elif action == "logo_disable":
        set_logo_status(False)
        await query.answer("❌ تم إيقاف اللوجو!", show_alert=True)
    
    # العودة للقائمة الرئيسية
    return await admin_panel(update, context)

async def manage_libraries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة المنصات مع الكوكيز المدمجة"""
    query = update.callback_query
    await query.answer()

    message_text = (
        "🌐 **إدارة المنصات والكوكيز**\n\n"
        "اختر المنصة لعرض التفاصيل وإدارة الكوكيز:\n"
    )

    # قائمة المنصات
    keyboard = [
        [InlineKeyboardButton("🎥 YouTube", callback_data="platform_youtube")],
        [InlineKeyboardButton("📘 Facebook", callback_data="platform_facebook")],
        [InlineKeyboardButton("📸 Instagram", callback_data="platform_instagram")],
        [InlineKeyboardButton("🧵 Threads", callback_data="platform_threads")],  # ⭐ إضافة Threads
        [InlineKeyboardButton("🎵 TikTok", callback_data="platform_tiktok")],
        [InlineKeyboardButton("📌 Pinterest", callback_data="platform_pinterest")],
        [InlineKeyboardButton("🐦 Twitter/X", callback_data="platform_twitter")],
        [InlineKeyboardButton("🤖 Reddit", callback_data="platform_reddit")],
        [InlineKeyboardButton("🎬 Vimeo", callback_data="platform_vimeo")],
        [InlineKeyboardButton("📺 Dailymotion", callback_data="platform_dailymotion")],
        [InlineKeyboardButton("🎮 Twitch", callback_data="platform_twitch")],
        [InlineKeyboardButton("↩️ العودة", callback_data="admin_back")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU

async def show_platform_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تفاصيل منصة معينة مع حالة الكوكيز"""
    query = update.callback_query
    await query.answer()

    # استخراج اسم المنصة من callback_data
    platform = query.data.replace('platform_', '')

    platform_names = {
        'youtube': 'YouTube',
        'facebook': 'Facebook',
        'instagram': 'Instagram',
        'threads': 'Threads',  # ⭐ إضافة Threads
        'tiktok': 'TikTok',
        'pinterest': 'Pinterest',
        'twitter': 'Twitter/X',
        'reddit': 'Reddit',
        'vimeo': 'Vimeo',
        'dailymotion': 'Dailymotion',
        'twitch': 'Twitch'
    }

    platform_emojis = {
        'youtube': '🎥',
        'facebook': '📘',
        'instagram': '📸',
        'threads': '🧵',  # ⭐ إضافة Threads
        'tiktok': '🎵',
        'pinterest': '📌',
        'twitter': '🐦',
        'reddit': '🤖',
        'vimeo': '🎬',
        'dailymotion': '📺',
        'twitch': '🎮'
    }

    name = platform_names.get(platform, platform)
    emoji = platform_emojis.get(platform, '🌐')

    # فحص حالة الكوكيز
    cookie_status = "❌ غير موجودة"
    cookie_age = "N/A"
    cookie_count = 0
    cookie_warning = ""

    try:
        from handlers.cookie_manager import cookie_manager
        cookie_info = cookie_manager.get_platform_cookie_status(platform)

        if cookie_info.get('exists', False):
            age_days = cookie_info.get('age_days', 0)
            cookie_count = cookie_info.get('cookie_count', 0)
            cookie_age = f"{age_days} يوم"

            if age_days < 7:
                cookie_status = "✅ جيدة"
            elif age_days < 30:
                cookie_status = "⚠️ قديمة قليلاً"
            else:
                cookie_status = "🔴 قديمة جداً"

            # ⭐ تحذير إذا كانت الكوكيز قليلة
            if cookie_count < 5:
                cookie_warning = f"\n⚠️ **تحذير:** عدد الكوكيز قليل جداً ({cookie_count})\n💡 Instagram Story يحتاج على الأقل 10-15 كوكيز\n"
            elif cookie_count < 10:
                cookie_warning = f"\n⚠️ **ملاحظة:** عدد الكوكيز ({cookie_count}) قد لا يكفي للستوري\n"
    except Exception as e:
        logger.error(f"خطأ في فحص كوكيز {platform}: {e}")

    # حفظ المنصة الحالية
    context.user_data['current_platform'] = platform

    message_text = (
        f"{emoji} **{name}**\n\n"
        f"🍪 **حالة الكوكيز:** {cookie_status}\n"
        f"📅 **العمر:** {cookie_age}\n"
        f"🔢 **عدد الكوكيز:** {cookie_count}\n"
        f"{cookie_warning}\n"
        f"اختر الإجراء المطلوب:"
    )

    keyboard = [
        [InlineKeyboardButton("🧪 اختبار الكوكيز", callback_data=f"test_{platform}")],
        [InlineKeyboardButton("⬆️ رفع كوكيز جديدة", callback_data=f"upload_{platform}")],
    ]

    # إضافة زر اختبار الستوري لـ Instagram و Facebook و Threads
    if platform in ['instagram', 'facebook', 'threads']:
        keyboard.insert(1, [InlineKeyboardButton("📖 اختبار الستوري", callback_data=f"test_story_{platform}")])

    keyboard.append([InlineKeyboardButton("↩️ العودة", callback_data="admin_libraries")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU

async def test_platform_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار الكوكيز لمنصة معينة"""
    query = update.callback_query
    await query.answer("جاري الاختبار...")

    # استخراج اسم المنصة
    platform = query.data.replace('test_', '').replace('story_', '')
    is_story_test = 'story' in query.data

    await query.edit_message_text(
        f"⏳ جاري اختبار الكوكيز {'للستوري' if is_story_test else ''}...\n"
        f"قد يستغرق هذا بضع ثوانٍ."
    )

    try:
        from handlers.cookie_manager import cookie_manager

        # اختبار الكوكيز باستخدام validate_cookies
        result = await cookie_manager.validate_cookies(platform)

        if result:
            status_emoji = "✅"
            status_text = "نجح الاختبار"
            message_text = (
                f"{status_emoji} **{status_text}**\n\n"
                f"📋 **التفاصيل:**\n"
                f"✅ الكوكيز صالحة وتعمل بشكل صحيح\n"
            )

            if is_story_test:
                message_text += "\n📖 تم اختبار الستوري بنجاح"
        else:
            status_emoji = "❌"
            status_text = "فشل الاختبار"
            message_text = (
                f"{status_emoji} **{status_text}**\n\n"
                f"⚠️ الكوكيز غير صالحة أو منتهية الصلاحية\n"
                f"📌 يُرجى رفع ملف كوكيز جديد"
            )

    except Exception as e:
        logger.error(f"خطأ في اختبار {platform}: {e}")
        message_text = f"❌ **حدث خطأ في الاختبار**\n\n⚠️ {str(e)}"

    keyboard = [
        [InlineKeyboardButton("↩️ العودة", callback_data=f"platform_{platform}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU

async def upload_platform_cookie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية رفع كوكيز لمنصة"""
    query = update.callback_query
    await query.answer()

    platform = query.data.replace('upload_', '')
    context.user_data['upload_platform'] = platform

    platform_names = {
        'youtube': 'YouTube',
        'facebook': 'Facebook',
        'instagram': 'Instagram',
        'threads': 'Threads',  # ⭐ إضافة Threads
        'tiktok': 'TikTok',
        'pinterest': 'Pinterest',
        'twitter': 'Twitter/X',
        'reddit': 'Reddit',
        'vimeo': 'Vimeo',
        'dailymotion': 'Dailymotion',
        'twitch': 'Twitch'
    }

    name = platform_names.get(platform, platform)

    message_text = (
        f"📤 **رفع كوكيز {name}**\n\n"
        f"أرسل ملف الكوكيز (بصيغة .txt أو .json)\n\n"
        f"💡 تأكد من أن الملف يحتوي على كوكيز صالحة"
    )

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"platform_{platform}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return AWAITING_PLATFORM_COOKIE

async def receive_platform_cookie_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال ملف الكوكيز المرفوع"""
    platform = context.user_data.get('upload_platform')

    if not platform:
        await update.message.reply_text("❌ خطأ: لم يتم تحديد المنصة")
        return MAIN_MENU

    # التحقق من وجود ملف
    if not update.message.document:
        await update.message.reply_text("❌ الرجاء إرسال ملف كوكيز (.txt أو .json)")
        return AWAITING_PLATFORM_COOKIE

    file = update.message.document
    file_name = file.file_name

    # التحقق من نوع الملف
    if not (file_name.endswith('.txt') or file_name.endswith('.json')):
        await update.message.reply_text("❌ نوع الملف غير مدعوم. الرجاء إرسال ملف .txt أو .json")
        return AWAITING_PLATFORM_COOKIE

    try:
        # تحميل الملف
        file_obj = await context.bot.get_file(file.file_id)
        file_path = f"cookies/{platform}_cookies.txt"

        import os
        os.makedirs("cookies", exist_ok=True)

        await file_obj.download_to_drive(file_path)

        # التحقق من صحة الكوكيز
        from handlers.cookie_manager import cookie_manager
        validation = cookie_manager.validate_cookie_file(file_path, platform)

        if validation.get('valid', False):
            message_text = (
                f"✅ **تم رفع الكوكيز بنجاح!**\n\n"
                f"📋 المنصة: {platform}\n"
                f"📝 الملف: {file_name}\n\n"
                f"💡 يمكنك الآن اختبار الكوكيز"
            )
        else:
            message_text = (
                f"⚠️ **تم رفع الملف لكن هناك تحذير:**\n\n"
                f"{validation.get('message', 'قد تكون الكوكيز غير صحيحة')}\n\n"
                f"💡 جرب اختبار الكوكيز للتأكد"
            )

    except Exception as e:
        logger.error(f"خطأ في رفع كوكيز {platform}: {e}")
        message_text = f"❌ **فشل رفع الكوكيز**\n\n⚠️ {str(e)}"

    keyboard = [
        [InlineKeyboardButton("🧪 اختبار الكوكيز", callback_data=f"test_{platform}")],
        [InlineKeyboardButton("↩️ العودة", callback_data=f"platform_{platform}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    # تنظيف
    context.user_data.pop('upload_platform', None)

    return MAIN_MENU

async def library_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تفاصيل المكتبات"""
    query = update.callback_query
    await query.answer()
    
    from database import get_library_status, get_library_settings
    
    library_status = get_library_status()
    settings = get_library_settings()
    
    message_text = "📚 **تفاصيل المكتبات**\n\n"
    
    for lib_name, status in library_status.items():
        message_text += f"🔧 **{lib_name}**\n"
        message_text += f"• الحالة: {'🟢 نشط' if status.get('status') == 'active' else '🔴 غير نشط'}\n"
        message_text += f"• النسخة: {status.get('version', 'غير محدد')}\n"
        message_text += f"• معدل النجاح: {status.get('success_rate', 0)}%\n"
        if status.get('last_check'):
            last_check = status['last_check'].strftime('%Y-%m-%d %H:%M')
            message_text += f"• آخر فحص: {last_check}\n"
        message_text += "\n"
    
    # معلومات إضافية
    primary_lib = settings.get('primary_library', 'yt-dlp')
    auto_update = settings.get('auto_update', True)
    
    message_text += f"🎯 **المكتبة الأساسية:** {primary_lib}\n"
    message_text += f"🔄 **التحديث التلقائي:** {'✅ مفعّل' if auto_update else '❌ معطّل'}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 العودة للمكتبات", callback_data="admin_libraries")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

async def library_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات الأداء"""
    query = update.callback_query
    await query.answer()
    
    from database import get_performance_metrics, reset_performance_metrics
    
    performance = get_performance_metrics()
    
    total_downloads = performance.get('total_downloads', 0)
    successful = performance.get('successful_downloads', 0)
    failed = performance.get('failed_downloads', 0)
    avg_speed = performance.get('avg_download_speed', 0)
    
    success_rate = 0
    if total_downloads > 0:
        success_rate = (successful / total_downloads) * 100
    
    last_reset = performance.get('last_reset')
    reset_date = last_reset.strftime('%Y-%m-%d %H:%M') if last_reset else 'غير محدد'
    
    message_text = (
        "📈 **إحصائيات الأداء التفصيلية**\n\n"
        f"📊 **الإحصائيات العامة:**\n"
        f"• إجمالي التحميلات: `{total_downloads}`\n"
        f"• تحميلات ناجحة: `{successful}` ✅\n"
        f"• تحميلات فاشلة: `{failed}` ❌\n"
        f"• معدل النجاح: `{success_rate:.1f}%`\n"
        f"• متوسط السرعة: `{avg_speed:.1f} MB/s`\n\n"
        f"📅 **آخر إعادة تعيين:** {reset_date}\n\n"
        f"🎯 **تفسير النتائج:**\n"
        f"• معدل النجاح فوق 90%: ممتاز 🟢\n"
        f"• معدل النجاح 80-90%: جيد 🟡\n"
        f"• معدل النجاح تحت 80%: يحتاج تحسين 🔴\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 إعادة تعيين الإحصائيات", callback_data="library_reset_stats")],
        [InlineKeyboardButton("🔙 العودة للمكتبات", callback_data="admin_libraries")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

async def library_approvals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض وإدارة طلبات الموافقة"""
    query = update.callback_query
    await query.answer()
    
    from database import get_pending_approvals, approve_platform_request, deny_platform_request
    
    pending_approvals = get_pending_approvals()
    
    if not pending_approvals:
        message_text = "✅ **لا توجد طلبات موافقة معلقة**\n\nجميع طلبات التفعيل تمت معالجتها."
        keyboard = [[InlineKeyboardButton("🔙 العودة للمكتبات", callback_data="admin_libraries")]]
    else:
        message_text = f"📩 **طلبات الموافقة المعلقة** ({len(pending_approvals)})\n\n"
        
        keyboard = []
        for i, request in enumerate(pending_approvals[:3], 1):  # أول 3 طلبات
            platform = request.get('platform', 'غير محدد')
            requester = request.get('requested_by', 'غير محدد')
            request_date = request.get('request_date').strftime('%Y-%m-%d %H:%M')
            
            message_text += f"{i}. 🎯 **{platform}**\n"
            message_text += f"   👤 بواسطة: {requester}\n"
            message_text += f"   📅 التاريخ: {request_date}\n\n"
            
            # أزرار للموافقة/الرفض
            keyboard.append([
                InlineKeyboardButton(f"✅ الموافقة على {platform}", callback_data=f"approve_{request['id']}"),
                InlineKeyboardButton(f"❌ رفض {platform}", callback_data=f"deny_{request['id']}")
            ])
        
        if len(pending_approvals) > 3:
            message_text += f"... و {len(pending_approvals) - 3} طلبات أخرى"
        
        keyboard.append([InlineKeyboardButton("🔙 العودة للمكتبات", callback_data="admin_libraries")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

async def handle_platform_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تفعيل/إلغاء تفعيل المنصات"""
    query = update.callback_query
    await query.answer()
    
    import re
    data = query.data
    
    if data.startswith('platform_enable_'):
        platform = data.replace('platform_enable_', '')
        from database import toggle_platform
        success = toggle_platform(platform, True)
        action = "تفعيل"
    elif data.startswith('platform_disable_'):
        platform = data.replace('platform_disable_', '')
        from database import toggle_platform
        success = toggle_platform(platform, False)
        action = "إلغاء تفعيل"
    else:
        await query.answer("❌ أمر غير معروف")
        return MAIN_MENU
    
    if success:
        await query.answer(f"✅ تم {action} منصة {platform} بنجاح")
    else:
        await query.answer(f"❌ فشل {action} منصة {platform}")
    
    # العودة لصفحة إدارة المكتبات
    return await manage_libraries(update, context)

async def handle_approval_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إجراءات الموافقة/الرفض"""
    query = update.callback_query
    await query.answer()
    
    from database import approve_platform_request, deny_platform_request
    
    if query.data.startswith('approve_'):
        request_id = query.data.replace('approve_', '')
        success = approve_platform_request(request_id, query.from_user.id)
        action = "الموافقة"
    elif query.data.startswith('deny_'):
        request_id = query.data.replace('deny_', '')
        success = deny_platform_request(request_id, query.from_user.id, "مرفوض بواسطة المدير")
        action = "الرفض"
    else:
        await query.answer("❌ إجراء غير معروف")
        return MAIN_MENU
    
    if success:
        await query.answer(f"✅ تم {action} الطلب بنجاح")
    else:
        await query.answer(f"❌ فشل {action} الطلب")
    
    # العودة لصفحة إدارة المكتبات
    return await manage_libraries(update, context)

async def library_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديث المكتبات"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔄 **تحديث المكتبات**\n\n"
        "⏳ جاري تحديث yt-dlp إلى آخر إصدار..."
    )
    
    try:
        import subprocess
        import sys

        # تحديث yt-dlp باستخدام ThreadPoolExecutor لتجنب التجميد
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            lambda: subprocess.run([
                sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"
            ], capture_output=True, text=True, timeout=300)
        )
        
        if result.returncode == 0:
            await query.edit_message_text(
                "✅ **تم التحديث بنجاح**\n\n"
                "🟢 تم تحديث yt-dlp إلى آخر إصدار\n"
                "🔄 سيتم تطبيق التحديث في التحميل التالي"
            )
        else:
            await query.edit_message_text(
                "❌ **فشل التحديث**\n\n"
                "⚠️ حدث خطأ أثناء تحديث المكتبة\n"
                f"📝 التفاصيل: {result.stderr[:200]}"
            )
    except Exception as e:
        await query.edit_message_text(
            "❌ **خطأ في التحديث**\n\n"
            f"⚠️ {str(e)[:200]}"
        )
    
    keyboard = [[InlineKeyboardButton("🔙 العودة للمكتبات", callback_data="admin_libraries")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            query.message.text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except:
        pass
    
    return MAIN_MENU

async def library_reset_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إعادة تعيين الإحصائيات"""
    query = update.callback_query
    await query.answer()
    
    from database import reset_performance_metrics
    
    success = reset_performance_metrics()
    
    if success:
        await query.answer("✅ تم إعادة تعيين الإحصائيات بنجاح")
    else:
        await query.answer("❌ فشل إعادة تعيين الإحصائيات")
    
    return await library_stats(update, context)

# ═══════════════════════════════════════════════════════════════
#  VIP Subscription Control Panel - Redesigned (Arabic Only)
# ═══════════════════════════════════════════════════════════════

async def show_vip_control_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة التحكم بنظام الاشتراك - عربي فقط"""
    query = update.callback_query
    await query.answer()

    from database import get_subscription_price
    from lang import get_text

    # جلب الحالة الحالية
    sub_enabled = is_subscription_enabled()
    notifications_enabled = is_welcome_broadcast_enabled()
    current_price = get_subscription_price()

    # رموز الحالة
    sub_status = "✅ مفعّل" if sub_enabled else "❌ معطّل"
    notif_status = "✅ مفعّل" if notifications_enabled else "❌ معطّل"

    message_text = (
        "💎 **لوحة التحكم بالاشتراك**\n\n"
        "⚙️ **الإعدادات الحالية:**\n"
        f"📊 الحالة: {sub_status}\n"
        f"💰 السعر الحالي: ${current_price} شهرياً\n"
        f"🔔 إشعار المستخدمين: {notif_status}\n\n"
        "📌 **اختر الإجراء المطلوب:**"
    )

    keyboard = [
        [InlineKeyboardButton("✅ تفعيل الاشتراك", callback_data="sub_enable")],
        [InlineKeyboardButton("❌ إيقاف الاشتراك", callback_data="sub_disable")],
        [InlineKeyboardButton("💰 تغيير السعر", callback_data="sub_change_price")],
        [InlineKeyboardButton("🔔 تفعيل / تعطيل الإشعارات", callback_data="sub_toggle_notif")],
        [InlineKeyboardButton("↩️ العودة للقائمة الرئيسية", callback_data="admin_back")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.debug(f"تم تجاهل خطأ تعديل الرسالة: {e}")

    return MAIN_MENU


## معالجات الأزرار مع نظام التأكيد

async def handle_sub_enable_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تأكيد تفعيل الاشتراك مع خيار إخبار الأعضاء"""
    query = update.callback_query
    await query.answer()

    message_text = (
        "⚙️ **هل تريد بالتأكيد تفعيل نظام الاشتراك؟**\n\n"
        "✅ سيظهر زر الاشتراك VIP لجميع المستخدمين.\n\n"
        "💬 **هل تريد إخبار جميع الأعضاء عن بدء الاشتراك؟**"
    )

    keyboard = [
        [InlineKeyboardButton("✅ نعم، أخبر الأعضاء", callback_data="sub_enable_notify_yes")],
        [InlineKeyboardButton("⏭️ لا، تفعيل بدون إخبار", callback_data="sub_enable_notify_no")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="admin_vip_control")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU


async def handle_sub_disable_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تأكيد إيقاف الاشتراك"""
    query = update.callback_query
    await query.answer()

    message_text = (
        "⚙️ **هل تريد بالتأكيد إيقاف نظام الاشتراك؟**\n\n"
        "❌ سيصبح البوت مجاني للجميع\n"
        "🎉 المشتركون وغير المشتركين سيحصلون على نفس المزايا"
    )

    keyboard = [
        [InlineKeyboardButton("✅ نعم، قم بالإيقاف", callback_data="sub_disable_yes")],
        [InlineKeyboardButton("❌ لا، إلغاء", callback_data="sub_action_cancel")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU


async def handle_sub_enable_notify_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تفعيل الاشتراك + إرسال إشعار لجميع المستخدمين"""
    query = update.callback_query
    await query.answer()

    success = set_subscription_enabled(True)

    if success:
        await query.answer("✅ تم تفعيل نظام الاشتراك بنجاح!", show_alert=True)

        # إرسال إشعار لجميع المستخدمين
        from database import get_all_users
        all_users = get_all_users()

        welcome_text = (
            "💎 **نظام الاشتراك VIP تم تفعيله!**\n\n"
            "✨ ستحصل قريباً على مزايا إضافية مثل:\n"
            "🎞️ تحميل أسرع، 💬 دعم مباشر، 🎁 هدايا خاصة\n"
            "📢 تابع القناة الرسمية @iraq_7kmmy لمزيد من التفاصيل 🔗"
        )

        success_count = 0
        fail_count = 0

        for user in all_users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=welcome_text,
                    parse_mode='Markdown'
                )
                success_count += 1
            except:
                fail_count += 1
                pass

        # إشعار بعدد الرسائل المرسلة
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=f"📊 تم إرسال الإشعار:\n✅ نجح: {success_count}\n❌ فشل: {fail_count}"
        )
    else:
        await query.answer("❌ فشل تفعيل الاشتراك!", show_alert=True)

    return await show_vip_control_panel(update, context)


async def handle_sub_enable_notify_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تفعيل الاشتراك بدون إرسال إشعار"""
    query = update.callback_query
    await query.answer()

    success = set_subscription_enabled(True)

    if success:
        await query.answer("✅ تم تفعيل نظام الاشتراك بنجاح (بدون إشعار)!", show_alert=True)
    else:
        await query.answer("❌ فشل تفعيل الاشتراك!", show_alert=True)

    return await show_vip_control_panel(update, context)


async def handle_sub_disable_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ إيقاف الاشتراك"""
    query = update.callback_query
    await query.answer()

    success = set_subscription_enabled(False)

    if success:
        await query.answer("❌ تم إيقاف نظام الاشتراك!", show_alert=True)
    else:
        await query.answer("❌ فشل إيقاف الاشتراك!", show_alert=True)

    return await show_vip_control_panel(update, context)


async def handle_sub_action_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء الإجراء"""
    query = update.callback_query
    await query.answer("❌ تم إلغاء الإجراء", show_alert=False)

    return await show_vip_control_panel(update, context)


async def handle_sub_change_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة تغيير السعر"""
    query = update.callback_query
    await query.answer()

    from database import get_subscription_price
    current_price = get_subscription_price()

    message_text = (
        "💰 **اختر السعر المناسب:**\n\n"
        f"السعر الحالي: ${current_price} شهرياً\n\n"
        "اختر سعر من القائمة أو أدخل سعر مخصص:"
    )

    keyboard = [
        [InlineKeyboardButton("$1 شهرياً", callback_data="sub_price_1")],
        [InlineKeyboardButton("$3 شهرياً (موصى به)", callback_data="sub_price_3")],
        [InlineKeyboardButton("$5 شهرياً", callback_data="sub_price_5")],
        [InlineKeyboardButton("💵 سعر مخصص", callback_data="sub_price_custom")],
        [InlineKeyboardButton("↩️ العودة", callback_data="admin_vip_control")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU


async def handle_sub_set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعيين سعر محدد"""
    query = update.callback_query
    await query.answer()

    from database import set_subscription_price

    # استخراج السعر من callback_data
    price_str = query.data.replace("sub_price_", "")

    if price_str == "custom":
        # طلب إدخال سعر مخصص
        message_text = (
            "💵 **أدخل السعر المخصص:**\n\n"
            "📝 مثال: 7\n"
            "⚠️ أدخل رقم فقط (بالدولار)\n\n"
            "💡 اكتب السعر وأرسله الآن:"
        )

        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="sub_change_price")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        # حفظ الحالة لاستقبال السعر المخصص
        context.user_data['awaiting_price'] = True

        return AWAITING_CUSTOM_PRICE

    try:
        price = float(price_str)
        success = set_subscription_price(price)

        if success:
            await query.answer(f"✅ تم تحديث السعر إلى ${price} شهرياً!", show_alert=True)
        else:
            await query.answer("❌ فشل تحديث السعر!", show_alert=True)
    except ValueError:
        await query.answer("❌ سعر غير صحيح!", show_alert=True)

    return await show_vip_control_panel(update, context)


async def receive_custom_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال السعر المخصص"""
    if not context.user_data.get('awaiting_price'):
        return MAIN_MENU

    from database import set_subscription_price

    price_text = update.message.text.strip()

    try:
        price = float(price_text)

        if price <= 0:
            await update.message.reply_text(
                "❌ **السعر غير صحيح!**\n\n✅ أدخل رقم موجب (مثال: 3)",
                parse_mode='Markdown'
            )
            return AWAITING_CUSTOM_PRICE

        success = set_subscription_price(price)

        if success:
            await update.message.reply_text(
                f"✅ **تم تحديث السعر بنجاح!**\n\n💰 السعر الجديد: ${price} شهرياً",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ **فشل تحديث السعر!** يرجى المحاولة مرة أخرى.",
                parse_mode='Markdown'
            )

        # حذف الحالة
        context.user_data.pop('awaiting_price', None)

        # العودة للوحة التحكم
        keyboard = [[InlineKeyboardButton("↩️ العودة للوحة التحكم", callback_data="admin_vip_control")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "اختر الإجراء التالي:",
            reply_markup=reply_markup
        )

        return MAIN_MENU

    except ValueError:
        await update.message.reply_text(
            "❌ **السعر غير صحيح!**\n\n✅ أدخل رقم فقط (مثال: 3)",
            parse_mode='Markdown'
        )
        return AWAITING_CUSTOM_PRICE


async def handle_sub_toggle_notif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تبديل حالة الإشعارات"""
    query = update.callback_query
    await query.answer()

    # الحصول على الحالة الحالية
    current_status = is_welcome_broadcast_enabled()
    new_status = not current_status

    # حفظ التغيير
    success = set_welcome_broadcast_enabled(new_status)

    if success:
        status_text = "✅ مفعّلة" if new_status else "❌ معطّلة"
        await query.answer(f"🔔 الإشعارات الآن: {status_text}", show_alert=True)
    else:
        await query.answer("❌ فشل تغيير حالة الإشعارات!", show_alert=True)

    return await show_vip_control_panel(update, context)


# ═══════════════════════════════════════════════════════════════
#  Audio Settings Panel
# ═══════════════════════════════════════════════════════════════

async def show_audio_settings_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة إعدادات تحميل الصوتيات"""
    query = update.callback_query
    await query.answer()

    from database import get_audio_settings, get_audio_limit_minutes, is_audio_enabled

    # جلب الإعدادات الحالية
    settings = get_audio_settings()
    audio_enabled = is_audio_enabled()
    audio_limit = get_audio_limit_minutes()

    status_text = "✅ مفعّل" if audio_enabled else "❌ معطّل"

    # عرض الحد الحالي
    if audio_limit == -1:
        limit_text = "♾️ غير محدود"
    else:
        limit_text = f"{audio_limit} دقيقة"

    message_text = (
        "🎧 **إعدادات تحميل الصوتيات**\n\n"
        f"📊 **الإعدادات الحالية:**\n"
        f"• الحالة العامة: {status_text}\n"
        f"• الحد الأقصى لغير المشتركين: {limit_text}\n"
        f"• للمشتركين VIP: ♾️ دائماً غير محدود\n\n"
        f"💡 **ملاحظات:**\n"
        f"• إذا كان المقطع الصوتي أطول من الحد المسموح، سيُمنع التحميل\n"
        f"• المشتركون VIP يمكنهم تحميل صوتيات بلا حدود\n\n"
        f"اختر الإجراء المطلوب:"
    )

    keyboard = [
        [InlineKeyboardButton("✅ تفعيل تحميل الصوتيات", callback_data="audio_enable")],
        [InlineKeyboardButton("❌ إيقاف تحميل الصوتيات", callback_data="audio_disable")],
        [
            InlineKeyboardButton("3️⃣ 3 دقائق", callback_data="audio_preset_3"),
            InlineKeyboardButton("5️⃣ 5 دقائق", callback_data="audio_preset_5")
        ],
        [
            InlineKeyboardButton("🔟 10 دقائق", callback_data="audio_preset_10"),
            InlineKeyboardButton("♾️ غير محدود", callback_data="audio_preset_unlimited")
        ],
        [InlineKeyboardButton("⏱️ حد مخصص", callback_data="audio_set_custom_limit")],
        [InlineKeyboardButton("↩️ العودة للقائمة الرئيسية", callback_data="admin_back")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.debug(f"تم تجاهل خطأ تعديل الرسالة: {e}")

    return MAIN_MENU


async def handle_audio_enable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تفعيل تحميل الصوتيات"""
    query = update.callback_query
    await query.answer()

    from database import set_audio_enabled

    success = set_audio_enabled(True)

    if success:
        await query.answer("✅ تم تفعيل تحميل الصوتيات بنجاح!", show_alert=True)
    else:
        await query.answer("❌ فشل تفعيل تحميل الصوتيات!", show_alert=True)

    return await show_audio_settings_panel(update, context)


async def handle_audio_disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إيقاف تحميل الصوتيات"""
    query = update.callback_query
    await query.answer()

    from database import set_audio_enabled

    success = set_audio_enabled(False)

    if success:
        await query.answer("❌ تم إيقاف تحميل الصوتيات!", show_alert=True)
    else:
        await query.answer("❌ فشل إيقاف تحميل الصوتيات!", show_alert=True)

    return await show_audio_settings_panel(update, context)


async def handle_audio_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الحد الزمني المحدد مسبقاً"""
    query = update.callback_query
    await query.answer()

    from database import set_audio_limit_minutes

    # استخراج القيمة من callback_data
    preset = query.data.replace("audio_preset_", "")

    if preset == "unlimited":
        limit = -1
        limit_text = "♾️ غير محدود"
    else:
        limit = float(preset)
        limit_text = f"{limit} دقيقة"

    success = set_audio_limit_minutes(limit)

    if success:
        await query.answer(f"✅ تم تعيين الحد إلى {limit_text}!", show_alert=True)
    else:
        await query.answer("❌ فشل تحديث الحد الزمني!", show_alert=True)

    return await show_audio_settings_panel(update, context)


async def handle_audio_set_custom_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طلب إدخال حد زمني مخصص"""
    query = update.callback_query
    await query.answer()

    text = (
        "⏱️ **أدخل الحد الزمني المخصص:**\n\n"
        "📝 مثال: 15 (يعني 15 دقيقة)\n"
        "⚠️ أدخل رقم فقط (بالدقائق)\n\n"
        "💡 اكتب الحد الزمني وأرسله الآن:"
    )

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_audio_settings")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    # حفظ الحالة لاستقبال الحد الزمني
    context.user_data['awaiting_audio_limit'] = True

    return AWAITING_AUDIO_LIMIT


async def receive_audio_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال الحد الزمني المخصص"""
    if not context.user_data.get('awaiting_audio_limit'):
        return MAIN_MENU

    from database import set_audio_limit_minutes

    limit_text = update.message.text.strip()

    try:
        limit = float(limit_text)

        if limit < 0:
            await update.message.reply_text(
                "❌ **الحد الزمني غير صحيح!**\n\n✅ أدخل رقم موجب (مثال: 10)",
                parse_mode='Markdown'
            )
            return AWAITING_AUDIO_LIMIT

        success = set_audio_limit_minutes(limit)

        if success:
            await update.message.reply_text(
                f"✅ **تم تحديث الحد الزمني بنجاح!**\n\n⏱️ الحد الجديد: {limit} دقيقة",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ **فشل تحديث الحد الزمني!** يرجى المحاولة مرة أخرى.",
                parse_mode='Markdown'
            )

        # حذف الحالة
        context.user_data.pop('awaiting_audio_limit', None)

        # العودة للوحة التحكم
        keyboard = [[InlineKeyboardButton("↩️ العودة للوحة إعدادات الصوت", callback_data="admin_audio_settings")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "اختر الإجراء التالي:",
            reply_markup=reply_markup
        )

        return MAIN_MENU

    except ValueError:
        await update.message.reply_text(
            "❌ **الحد الزمني غير صحيح!**\n\n✅ أدخل رقم فقط (مثال: 10)",
            parse_mode='Markdown'
        )
        return AWAITING_AUDIO_LIMIT


# ═══════════════════════════════════════════════════════════════
#  Error Reports Panel
# ═══════════════════════════════════════════════════════════════

async def show_error_reports_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة بلاغات المستخدمين"""
    query = update.callback_query
    await query.answer()

    from database import get_pending_error_reports

    pending_reports = get_pending_error_reports(limit=20)

    if not pending_reports:
        message_text = "✅ **لا توجد بلاغات معلقة**\n\nجميع البلاغات تمت معالجتها."
        keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="admin_back")]]
    else:
        message_text = f"🧾 **بلاغات المستخدمين المعلقة** ({len(pending_reports)})\n\n"

        keyboard = []
        for i, report in enumerate(pending_reports[:10], 1):  # أول 10 فقط
            user_id = report.get('user_id', 'غير محدد')
            username = report.get('username', 'مجهول')
            error_type = report.get('error_type', 'خطأ')
            created_at = report.get('created_at')

            if created_at:
                created_str = created_at.strftime('%m/%d %H:%M')
            else:
                created_str = 'N/A'

            # إزالة أحرف خاصة من اليوزر والنوع لتجنب مشاكل Markdown
            # استخدام backticks للأمان
            username_safe = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            error_type_safe = error_type.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

            message_text += f"{i}️⃣ `{username_safe}` — {error_type_safe} ({created_str})\n"

            # زر لكل بلاغ
            report_id = str(report['_id'])
            keyboard.append([
                InlineKeyboardButton(
                    f"🔧 حل بلاغ #{i}",
                    callback_data=f"resolve_report:{report_id}"
                )
            ])

        if len(pending_reports) > 10:
            message_text += f"\n... و {len(pending_reports) - 10} بلاغات أخرى"

        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="admin_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU


AWAITING_ADMIN_NOTE = 7  # New conversation state

async def handle_resolve_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة حل بلاغ"""
    query = update.callback_query
    await query.answer()

    report_id = query.data.split(":")[1]

    from database import get_error_report_by_id
    import re

    report = get_error_report_by_id(report_id)

    if not report:
        await query.answer("❌ لم يتم العثور على البلاغ!", show_alert=True)
        return await show_error_reports_panel(update, context)

    user_id = report.get('user_id')
    username = report.get('username', 'مجهول')
    url = report.get('url', 'N/A')
    error_type = report.get('error_type', 'خطأ')
    error_message = report.get('error_message', 'لا توجد تفاصيل')
    created_at = report.get('created_at')

    # إنشاء رابط المراسلة المباشرة للمستخدم
    user_link = f"tg://user?id={user_id}"

    # تنسيق اليوزر مع رابط قابل للنقر
    # Escape أحرف Markdown الخاصة في اليوزرنيم
    if username and username != 'مجهول':
        username_safe = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)')
        user_display = f"[{username_safe}]({user_link})"
    else:
        user_display = f"[ID: {user_id}]({user_link})"

    # إزالة رموز ANSI من رسالة الخطأ
    clean_error = re.sub(r'\x1b\[[0-9;]*m', '', error_message)
    clean_error = re.sub(r'\[0;[0-9]+m', '', clean_error)
    clean_error = re.sub(r'\[0m', '', clean_error)

    # استخراج اسم النطاق من الرابط للعرض المختصر
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        path_short = parsed.path[:30] + '...' if len(parsed.path) > 30 else parsed.path
        url_display = f"{domain}{path_short}"
    except:
        url_display = url[:40] + '...' if len(url) > 40 else url

    # استخراج نوع المشكلة من رسالة الخطأ
    error_problem = clean_error.split(':')[0].strip() if ':' in clean_error else clean_error[:50]

    # التاريخ والوقت
    if created_at:
        time_str = created_at.strftime('%H:%M')
        date_str = created_at.strftime('%d-%m-%Y')
    else:
        time_str = 'N/A'
        date_str = 'N/A'

    # التصميم #6 - بطاقة معلومات
    message_text = (
        "┏━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃   📋 تفاصيل البلاغ    ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "┌ 👤 المستخدم\n"
        f"│ • الاسم: {user_display}\n"
        f"│ • الآيدي: `{user_id}`\n"
        "└─────────────────────\n\n"
        "┌ 🔴 الخطأ\n"
        f"│ • النوع: {error_type}\n"
        f"│ • المشكلة: {error_problem}\n"
        f"│ • الرابط: `{url_display}`\n"
        "└─────────────────────\n\n"
        f"🕐 {time_str} — 📅 {date_str}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 استخدم الأزرار أدناه للتواصل أو الحل"
    )

    keyboard = [
        [InlineKeyboardButton("✅ تم الحل (إرسال إشعار)", callback_data=f"confirm_resolve:{report_id}")],
        [InlineKeyboardButton("💬 مراسلة المستخدم", url=user_link)],
        [InlineKeyboardButton("❌ لم تُحل بعد", callback_data="admin_error_reports")],
        [InlineKeyboardButton("🔙 العودة", callback_data="admin_error_reports")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU


async def handle_confirm_resolve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حل البلاغ وإرسال إشعار"""
    query = update.callback_query
    await query.answer()

    report_id = query.data.split(":")[1]

    from database import get_error_report_by_id, resolve_error_report

    report = get_error_report_by_id(report_id)

    if not report:
        await query.answer("❌ لم يتم العثور على البلاغ!", show_alert=True)
        return await show_error_reports_panel(update, context)

    user_id = report.get('user_id')

    # حل البلاغ في قاعدة البيانات
    success = resolve_error_report(report_id)

    if success:
        # إرسال إشعار للمستخدم
        try:
            notification_text = (
                "✅ **تم تصليح مشكلتك!**\n\n"
                "يمكنك الآن التحميل مرة أخرى 🎧\n\n"
                "شكراً لصبرك! 💚"
            )

            await context.bot.send_message(
                chat_id=user_id,
                text=notification_text,
                parse_mode='Markdown'
            )

            logger.info(f"✅ تم إرسال إشعار الحل للمستخدم {user_id}")
            await query.answer("✅ تم حل البلاغ وإرسال إشعار للمستخدم!", show_alert=True)

        except Exception as e:
            log_warning(f"⚠️ فشل إرسال الإشعار للمستخدم {user_id}: {e}", module="handlers/admin.py")
            await query.answer("✅ تم حل البلاغ (لكن فشل إرسال الإشعار)", show_alert=True)

    else:
        await query.answer("❌ فشل حل البلاغ!", show_alert=True)

    return await show_error_reports_panel(update, context)


# ═══════════════════════════════════════════════════════════════
#  General Limits Control Panel
# ═══════════════════════════════════════════════════════════════

async def show_general_limits_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة إعدادات القيود العامة"""
    query = update.callback_query
    await query.answer()

    from database import get_free_time_limit, get_daily_download_limit_setting

    # جلب الإعدادات الحالية
    time_limit = get_free_time_limit()
    daily_limit = get_daily_download_limit_setting()

    message_text = (
        "⚙️ **إعدادات القيود العامة**\n\n"
        f"🕒 الحد الزمني لغير المشتركين: **{time_limit} دقيقة**\n"
        f"🔁 الحد اليومي المسموح به: **{daily_limit} مرات**\n\n"
        "💡 **ملاحظات:**\n"
        "• هذه القيود تطبق فقط على المستخدمين غير المشتركين\n"
        "• المشتركون VIP لديهم حرية كاملة بلا قيود\n\n"
        "اختر الإجراء المطلوب:"
    )

    keyboard = [
        [InlineKeyboardButton("🕒 تعديل الحد الزمني", callback_data="edit_time_limit")],
        [InlineKeyboardButton("🔁 تعديل الحد اليومي", callback_data="edit_daily_limit")],
        [InlineKeyboardButton("↩️ العودة للقائمة الرئيسية", callback_data="admin_back")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.debug(f"تم تجاهل خطأ تعديل الرسالة: {e}")

    return MAIN_MENU


async def handle_edit_time_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أزرار الإعدادات المسبقة للحد الزمني (V5.0.1)"""
    query = update.callback_query
    await query.answer()

    from database import get_free_time_limit
    current_limit = get_free_time_limit()

    text = (
        "🕒 **تعديل الحد الزمني**\n\n"
        f"⏱️ الحد الحالي: **{current_limit} دقيقة**\n\n"
        "اختر المدة الجديدة للمستخدمين غير المشتركين:\n\n"
        "💡 **ملاحظة:**\n"
        "• هذا الحد يحمي السيرفر من الحمل الزائد\n"
        "• المشتركون VIP لديهم تحميل غير محدود ♾️\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("3️⃣ دقائق", callback_data="set_limit_3"),
            InlineKeyboardButton("🔟 دقائق", callback_data="set_limit_10")
        ],
        [
            InlineKeyboardButton("3️⃣0️⃣ دقيقة", callback_data="set_limit_30"),
            InlineKeyboardButton("6️⃣0️⃣ دقيقة", callback_data="set_limit_60")
        ],
        [
            InlineKeyboardButton("♾️ غير محدود", callback_data="set_limit_unlimited")
        ],
        [
            InlineKeyboardButton("✍️ إدخال يدوي", callback_data="set_limit_custom")
        ],
        [
            InlineKeyboardButton("❌ إلغاء", callback_data="admin_general_limits")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU


async def handle_set_time_limit_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تطبيق الحد الزمني من الأزرار المسبقة (V5.0.1)"""
    query = update.callback_query
    await query.answer()

    from database import set_free_time_limit

    # Extract limit value from callback_data
    limit_value = query.data.replace("set_limit_", "")

    if limit_value == "unlimited":
        limit = -1  # -1 means unlimited
        limit_text = "♾️ غير محدود"
    else:
        limit = int(limit_value)
        limit_text = f"{limit} دقيقة"

    # Update database
    success = set_free_time_limit(limit)

    if success:
        # Log event
        try:
            import os
            os.makedirs('logs', exist_ok=True)
            with open('logs/limit_events.log', 'a', encoding='utf-8') as f:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                admin_id = query.from_user.id
                admin_name = query.from_user.username or query.from_user.first_name
                f.write(f"[{timestamp}] Admin @{admin_name} ({admin_id}) changed time limit to: {limit_text}\n")
        except Exception as e:
            logger.error(f"Failed to log limit change: {e}")

        await query.edit_message_text(
            f"✅ **تم تحديث الحد الزمني بنجاح!**\n\n"
            f"⏱️ المدة الجديدة: **{limit_text}** للأعضاء غير المشتركين\n\n"
            f"💡 **ملاحظة:**\n"
            f"• المشتركون VIP لديهم تحميل غير محدود\n"
            f"• هذا الحد يحمي السيرفر من الحمل الزائد\n",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ العودة للقيود", callback_data="admin_general_limits")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_back")]
            ])
        )
    else:
        await query.edit_message_text(
            "❌ **فشل تحديث الحد الزمني!**\n\nيرجى المحاولة مرة أخرى.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="edit_time_limit")]])
        )

    return MAIN_MENU


async def handle_set_time_limit_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طلب إدخال يدوي للحد الزمني (V5.0.1)"""
    query = update.callback_query
    await query.answer()

    text = (
        "✍️ **إدخال يدوي للحد الزمني**\n\n"
        "📝 أدخل الحد الزمني الجديد (بالدقائق)\n\n"
        "💡 **أمثلة:**\n"
        "• 5 = خمس دقائق\n"
        "• 15 = ربع ساعة\n"
        "• 120 = ساعتين\n"
        "• -1 = غير محدود ♾️\n\n"
        "اكتب الحد الزمني الجديد:"
    )

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="edit_time_limit")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    context.user_data['awaiting_time_limit'] = True

    return AWAITING_TIME_LIMIT


async def receive_time_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال الحد الزمني الجديد"""
    if not context.user_data.get('awaiting_time_limit'):
        return MAIN_MENU

    from database import set_free_time_limit

    limit_text = update.message.text.strip()

    try:
        limit = int(limit_text)

        if limit < 0:
            await update.message.reply_text(
                "❌ **الحد الزمني غير صحيح!**\n\n✅ أدخل رقم موجب (مثال: 10)",
                parse_mode='Markdown'
            )
            return AWAITING_TIME_LIMIT

        success = set_free_time_limit(limit)

        if success:
            await update.message.reply_text(
                f"✅ **تم تحديث الحد الزمني بنجاح!**\n\n🕒 الحد الجديد: **{limit} دقيقة**",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ **فشل تحديث الحد الزمني!** يرجى المحاولة مرة أخرى.",
                parse_mode='Markdown'
            )

        context.user_data.pop('awaiting_time_limit', None)

        keyboard = [[InlineKeyboardButton("↩️ العودة للوحة القيود", callback_data="admin_general_limits")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "اختر الإجراء التالي:",
            reply_markup=reply_markup
        )

        return MAIN_MENU

    except ValueError:
        await update.message.reply_text(
            "❌ **الحد الزمني غير صحيح!**\n\n✅ أدخل رقم صحيح فقط (مثال: 10)",
            parse_mode='Markdown'
        )
        return AWAITING_TIME_LIMIT


async def handle_edit_daily_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طلب إدخال حد يومي جديد"""
    query = update.callback_query
    await query.answer()

    text = (
        "🔁 **تعديل الحد اليومي**\n\n"
        "📝 أدخل الحد اليومي الجديد للمستخدمين غير المشتركين (عدد التحميلات)\n\n"
        "💡 مثال: 5 (يعني 5 تحميلات يومياً)\n"
        "⚠️ أدخل رقم صحيح فقط\n\n"
        "اكتب الحد اليومي الجديد:"
    )

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_general_limits")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    context.user_data['awaiting_daily_limit'] = True

    return AWAITING_DAILY_LIMIT


async def receive_daily_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال الحد اليومي الجديد"""
    if not context.user_data.get('awaiting_daily_limit'):
        return MAIN_MENU

    from database import set_daily_download_limit

    limit_text = update.message.text.strip()

    try:
        limit = int(limit_text)

        if limit < 0:
            await update.message.reply_text(
                "❌ **الحد اليومي غير صحيح!**\n\n✅ أدخل رقم موجب (مثال: 5)",
                parse_mode='Markdown'
            )
            return AWAITING_DAILY_LIMIT

        success = set_daily_download_limit(limit)

        if success:
            await update.message.reply_text(
                f"✅ **تم تحديث الحد اليومي بنجاح!**\n\n🔁 الحد الجديد: **{limit} تحميلات**",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ **فشل تحديث الحد اليومي!** يرجى المحاولة مرة أخرى.",
                parse_mode='Markdown'
            )

        context.user_data.pop('awaiting_daily_limit', None)

        keyboard = [[InlineKeyboardButton("↩️ العودة للوحة القيود", callback_data="admin_general_limits")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "اختر الإجراء التالي:",
            reply_markup=reply_markup
        )

        return MAIN_MENU

    except ValueError:
        await update.message.reply_text(
            "❌ **الحد اليومي غير صحيح!**\n\n✅ أدخل رقم صحيح فقط (مثال: 5)",
            parse_mode='Markdown'
        )
        return AWAITING_DAILY_LIMIT


# ═══════════════════════════════════════════════════════════════
#  Cookie Management System V5.0 Ultra Secure
# ═══════════════════════════════════════════════════════════════

async def show_cookie_management_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة إدارة Cookies"""
    query = update.callback_query
    await query.answer()

    from handlers.cookie_manager import cookie_manager

    # Get cookie status
    status = cookie_manager.get_cookie_status()

    # Build status text
    status_text = ""
    for platform, info in status.items():
        platform_emoji = {
            'facebook': '📘',
            'instagram': '📸',
            'tiktok': '🎵'
        }
        emoji = platform_emoji.get(platform, '📁')

        if info['exists']:
            age_days = info.get('age_days', 0)
            validated = info.get('validated', False)

            if age_days > 30:
                age_status = f"⚠️ {age_days} يوم"
            elif age_days > 14:
                age_status = f"🟡 {age_days} يوم"
            else:
                age_status = f"✅ {age_days} يوم"

            val_status = "✅" if validated else "⚠️"
            status_text += f"{emoji} {platform.capitalize()}: {val_status} ({age_status})\n"
        else:
            status_text += f"{emoji} {platform.capitalize()}: ❌ غير موجودة\n"

    message_text = (
        "🍪 **إدارة Cookies V5.0**\n\n"
        f"**الحالة الحالية:**\n{status_text}\n"
        "💡 **المميزات:**\n"
        "• تشفير AES-256 تلقائي\n"
        "• اختبار صلاحية فوري\n"
        "• دعم Stories للمنصات\n"
        "• فحص أسبوعي تلقائي\n\n"
        "اختر الإجراء المطلوب:"
    )

    keyboard = [
        [InlineKeyboardButton("📋 عرض التفاصيل", callback_data="cookie_status_detail")],
        [InlineKeyboardButton("🧪 اختبار جميع الـ Cookies", callback_data="cookie_test_all")],
        [InlineKeyboardButton("📸 اختبار Stories الآن", callback_data="cookie_test_stories")],
        [InlineKeyboardButton("🔐 معلومات التشفير", callback_data="cookie_encryption_info")],
        [InlineKeyboardButton("🗑️ حذف جميع الـ Cookies", callback_data="cookie_delete_all")],
        [InlineKeyboardButton("↩️ العودة", callback_data="admin_back")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU


async def show_cookie_status_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تفاصيل حالة Cookies"""
    query = update.callback_query
    await query.answer()

    from handlers.cookie_manager import cookie_manager, show_cookie_status

    # Use the existing show_cookie_status function
    await show_cookie_status(update, context)

    return MAIN_MENU


async def handle_cookie_test_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار جميع Cookies"""
    query = update.callback_query
    await query.answer()

    from handlers.cookie_manager import test_all_cookies

    # Use the existing test_all_cookies function
    await test_all_cookies(update, context)

    return MAIN_MENU


async def handle_cookie_test_stories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار تحميل Stories"""
    query = update.callback_query
    await query.answer()

    from handlers.cookie_manager import test_story_download

    # Use the existing test_story_download function
    await test_story_download(update, context)

    return MAIN_MENU


async def show_cookie_encryption_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات التشفير"""
    query = update.callback_query
    await query.answer()

    from handlers.cookie_manager import COOKIE_KEY_FILE
    import json

    try:
        if COOKIE_KEY_FILE.exists():
            with open(COOKIE_KEY_FILE, 'r') as f:
                key_data = json.load(f)

            created_at = key_data.get('created_at', 'Unknown')
            algorithm = key_data.get('algorithm', 'AES-256')

            message_text = (
                "🔐 **معلومات التشفير**\n\n"
                f"🔑 الخوارزمية: `{algorithm}`\n"
                f"📅 تاريخ الإنشاء: `{created_at[:10]}`\n"
                f"📁 المسار: `cookie_key.json`\n\n"
                "✅ **الأمان:**\n"
                "• تشفير AES-256 (Fernet)\n"
                "• حذف تلقائي للملفات المؤقتة\n"
                "• تخزين آمن في `/cookies_encrypted/`\n"
                "• لا يتم حفظ الملفات غير المشفرة\n\n"
                "⚠️ **تحذير:**\n"
                "لا تشارك ملف `cookie_key.json` مع أحد!"
            )
        else:
            message_text = (
                "⚠️ **لم يتم إنشاء مفتاح التشفير بعد**\n\n"
                "سيتم إنشاؤه تلقائياً عند رفع أول ملف cookies"
            )
    except Exception as e:
        message_text = f"❌ خطأ في قراءة معلومات التشفير: {str(e)}"

    keyboard = [[InlineKeyboardButton("↩️ العودة", callback_data="admin_cookies")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU


async def handle_cookie_delete_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف جميع Cookies"""
    query = update.callback_query
    await query.answer()

    from handlers.cookie_manager import delete_all_cookies

    # Use the existing delete_all_cookies function
    await delete_all_cookies(update, context)

    return MAIN_MENU


# ═══════════════════════════════════════════════════════════════
#  Platform Cookie Upload Integration (V5.1)
# ═══════════════════════════════════════════════════════════════

async def handle_upload_cookie_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية رفع الكوكيز لمنصة محددة (V5.1)"""
    query = update.callback_query
    await query.answer()

    # Extract platform from callback_data: "upload_cookie_facebook"
    platform = query.data.replace("upload_cookie_", "")
    context.user_data['cookie_upload_platform'] = platform

    # Get platform display name
    platform_names = {
        'youtube': 'YouTube',
        'facebook': 'Facebook',
        'instagram': 'Instagram',
        'threads': 'Threads',  # ⭐ إضافة Threads
        'tiktok': 'TikTok',
        'pinterest': 'Pinterest',
        'twitter': 'Twitter/X',
        'reddit': 'Reddit',
        'vimeo': 'Vimeo',
        'dailymotion': 'Dailymotion',
        'twitch': 'Twitch'
    }
    platform_name = platform_names.get(platform, platform.capitalize())

    # Check if this platform uses linked cookies
    try:
        from handlers.cookie_manager import cookie_manager, PLATFORM_COOKIE_LINKS

        cookie_file = PLATFORM_COOKIE_LINKS.get(platform.lower())
        linked_info = ""

        if cookie_file and cookie_file != platform.lower():
            linked_platform = cookie_file.capitalize()
            linked_info = f"\n\n🔗 **ملاحظة:** {platform_name} يستخدم كوكيز {linked_platform}"

    except Exception as e:
        logger.error(f"Error getting cookie link info: {e}")
        linked_info = ""

    text = (
        f"🍪 **رفع كوكيز {platform_name}**\n\n"
        f"📤 أرسل ملف الكوكيز الآن أو الصق محتوى الملف\n\n"
        f"📋 **التنسيق المطلوب:**\n"
        f"• Netscape cookies.txt format\n"
        f"• يمكنك تصدير الكوكيز من المتصفح باستخدام إضافة Cookie Exporter\n"
        f"• يتم التشفير تلقائيًا بـ AES-256{linked_info}\n\n"
        f"❌ للإلغاء، اضغط /cancel"
    )

    await query.edit_message_text(
        text,
        parse_mode='Markdown'
    )

    return AWAITING_PLATFORM_COOKIE


async def handle_platform_cookie_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة رفع الكوكيز للمنصة المحددة - FIXED VERSION
    يدعم الملفات والنصوص الملصوقة + اكتشاف تلقائي قوي
    """
    platform = context.user_data.get('cookie_upload_platform')
    auto_detect = False

    try:
        from handlers.cookie_manager import cookie_manager, PLATFORM_COOKIE_LINKS

        # رسالة حالة أولية
        status_msg = await update.message.reply_text("⏳ جاري معالجة الكوكيز...")

        # ==================== تحديد مصدر البيانات ====================

        # حالة 1: ملف مرفق
        if update.message.document:
            file = await update.message.document.get_file()
            file_content = await file.download_as_bytearray()
            cookie_data = file_content.decode('utf-8')
        # حالة 2: نص مباشر (لصق)
        elif update.message.text and not update.message.text.startswith('/'):
            cookie_data = update.message.text
            auto_detect = True
        # حالة 3: لا توجد بيانات
        else:
            await status_msg.edit_text(
                "❌ يرجى إرسال ملف الكوكيز أو لصق محتواه مباشرة\n\n"
                "💡 استخدم إضافة Cookie-Editor لتصدير الكوكيز"
            )
            context.user_data.pop('cookie_upload_platform', None)
            return AWAITING_PLATFORM_COOKIE

        # ==================== الاكتشاف التلقائي ====================

        # محاولة اكتشاف المنصة من محتوى الكوكيز
        detected_platform = None
        if auto_detect or not platform:
            await status_msg.edit_text("🔍 جاري تحليل محتوى الكوكيز...")

            # تحليل أولي للكشف عن المنصة
            if "facebook.com" in cookie_data.lower():
                detected_platform = "facebook"
            elif "instagram.com" in cookie_data.lower():
                detected_platform = "instagram"
            elif "tiktok.com" in cookie_data.lower():
                detected_platform = "tiktok"
            elif "youtube.com" in cookie_data.lower():
                detected_platform = "youtube"
            elif "twitter.com" in cookie_data.lower() or "x.com" in cookie_data.lower():
                detected_platform = "twitter"

            if detected_platform:
                platform = detected_platform
                await status_msg.edit_text(f"✅ تم اكتشاف تلقائي: {platform.capitalize()}")

        # التحقق من وجود المنصة
        if not platform:
            await status_msg.edit_text(
                "❌ خطأ: لم يتم تحديد المنصة\n\n"
                "💡 تأكد من أن ملف الكوكيز يحتوي على بيانات صحيحة"
            )
            context.user_data.pop('cookie_upload_platform', None)
            return MAIN_MENU

        # ==================== تحليل الكوكيز ====================

        # تحليل تنسيق Netscape
        await status_msg.edit_text("🔍 جاري تحليل تنسيق الكوكيز...")

        success, parsed_data, detected_platform, cookie_count = cookie_manager.parse_netscape_cookies(cookie_data)

        # التحقق من نجاح التحليل
        if not success or not parsed_data:
            error_details = ""
            if "No valid cookies" in str(parsed_data):
                error_details = "❌ لم يتم العثور على كوكيز صالحة"
            elif "Expired cookies" in str(parsed_data):
                error_details = "⚠️ جميع الكوكيز منتهية الصلاحية"
            else:
                error_details = "❌ تنسيق غير صحيح أو بيانات تالفة"

            await status_msg.edit_text(
                f"❌ فشل تحليل الكوكيز\n\n"
                f"{error_details}\n\n"
                f"📋 المتطلبات:\n"
                f"• تنسيق Netscape HTTP Cookie File\n"
                f"• كوكيز غير منتهية\n"
                f"• حقل .domain مطلوب\n\n"
                f"💡 استخدم: Cookie-Editor أو Get cookies.txt"
            )

            # إعادة تعيين الحالة
            context.user_data.pop('cookie_upload_platform', None)
            return MAIN_MENU

        # ==================== حفظ الكوكيز ====================

        # حفظ الكوكيز المشفرة
        save_result = cookie_manager.save_encrypted_cookies(
            platform=platform,
            cookie_data=parsed_data,
            validate=True
        )

        if save_result['success']:
            # نجاح
            platform_names = {
                'youtube': 'YouTube',
                'facebook': 'Facebook',
                'instagram': 'Instagram',
                'threads': 'Threads',  # ⭐ إضافة Threads
                'tiktok': 'TikTok',
                'pinterest': 'Pinterest',
                'twitter': 'Twitter/X',
                'reddit': 'Reddit',
                'vimeo': 'Vimeo',
                'dailymotion': 'Dailymotion',
                'twitch': 'Twitch'
            }
            platform_name = platform_names.get(platform, platform.capitalize())

            await status_msg.edit_text(
                f"✅ تم حفظ كوكيز {platform_name} بنجاح!\n\n"
                f"📊 المعلومات:\n"
                f"• عدد الكوكيز: {cookie_count}\n"
                f"• المنصة: {platform_name}\n"
                f"• التشفير: AES-256\n"
                f"• حالة التحقق: {'✅ صالحة' if save_result.get('validated') else '⚠️ غير مفحوصة'}\n\n"
                f"💡 اختبار الآن؟ استخدم زر 'اختبار الكوكيز'"
            )

            # تسجيل الحدث
            logger.info(f"✅ Cookies saved for {platform}: {cookie_count} cookies")

        else:
            # فشل
            await status_msg.edit_text(
                f"❌ فشل حفظ الكوكيز\n\n"
                f"الخطأ: {save_result.get('error', 'خطأ غير معروف')}\n\n"
                f"💡 حاول مرة أخرى أو تأكد من صلاحية الكوكيز"
            )
            logger.error(f"❌ Failed to save cookies: {save_result.get('error')}")

        # ==================== التنظيف ====================

        # إعادة تعيين حالة المنصة
        context.user_data.pop('cookie_upload_platform', None)

        # أزرار التنقل
        keyboard = [
            [InlineKeyboardButton("🔄 إضافة كوكيز أخرى", callback_data=f"upload_cookie_{platform}")],
            [InlineKeyboardButton("🔙 إدارة المنصات", callback_data="admin_libraries")],
            [InlineKeyboardButton("🏠 لوحة التحكم", callback_data="admin_main")]
        ]

        await update.message.reply_text(
            "اختر إجراءً تالياً:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return MAIN_MENU

    except Exception as e:
        logger.error(f"❌ Error in handle_platform_cookie_upload: {e}")
        await update.message.reply_text(
            f"❌ خطأ غير متوقع: {str(e)}\n\n"
            f"💡 تأكد من:\n"
            f"• تنسيق الكوكيز صحيح\n"
            f"• الملف غير تالٍ\n"
            f"• المنصة محددة بشكل صحيح"
        )

        # إعادة تعيين الحالة في حال الخطأ
        context.user_data.pop('cookie_upload_platform', None)

        return MAIN_MENU


async def cancel_platform_cookie_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء عملية رفع الكوكيز (V5.1)"""
    context.user_data.pop('cookie_upload_platform', None)
    await update.message.reply_text(
        "❌ تم إلغاء رفع الكوكيز",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 العودة للمنصات", callback_data="manage_libraries")
        ]])
    )
    return MAIN_MENU


# ═══════════════════════════════════════════════════════════════
#  Broadcast System Enhancement - Individual User Messaging
# ═══════════════════════════════════════════════════════════════

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء نظام الإرسال الجماعي المُحسّن"""
    query = update.callback_query
    await query.answer()

    text = (
        "📢 **نظام الإرسال الجماعي**\n\n"
        "اختر نوع الإرسال:"
    )

    keyboard = [
        [InlineKeyboardButton("📩 إرسال لجميع المستخدمين", callback_data="broadcast_all")],
        [InlineKeyboardButton("👤 إرسال لمستخدم محدد", callback_data="broadcast_individual")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return MAIN_MENU


async def broadcast_all_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الإرسال لجميع المستخدمين"""
    query = update.callback_query
    await query.answer()

    text = (
        "📢 **إرسال رسالة لجميع المستخدمين**\n\n"
        "أرسل الرسالة التي تريد إرسالها للجميع:\n\n"
        "⚠️ تأكد من صياغة الرسالة بعناية!"
    )

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )

    context.user_data['broadcast_type'] = 'all'

    return BROADCAST_MESSAGE


async def broadcast_individual_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الإرسال لمستخدم محدد"""
    query = update.callback_query
    await query.answer()

    text = (
        "👤 **إرسال رسالة لمستخدم محدد**\n\n"
        "أرسل معرف المستخدم (User ID):\n\n"
        "💡 مثال: 123456789"
    )

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )

    context.user_data['broadcast_type'] = 'individual'

    return AWAITING_USER_ID_BROADCAST


async def receive_user_id_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال معرف المستخدم للإرسال الفردي"""
    user_input = update.message.text.strip()

    # التحقق من صحة معرف المستخدم
    is_valid, validated_user_id, error_msg = validate_user_id(user_input)

    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\n"
            "أرسل User ID صحيح (رقم): مثال 123456789"
        )
        return AWAITING_USER_ID_BROADCAST

    # التحقق من وجود المستخدم في قاعدة البيانات
    user_data = get_user(validated_user_id)

    if not user_data:
        await update.message.reply_text(
            "❌ المستخدم غير موجود في قاعدة البيانات!\n"
            "تأكد من أن المستخدم قام بإرسال /start للبوت."
        )
        return AWAITING_USER_ID_BROADCAST

    # حفظ معرف المستخدم
    context.user_data['target_user_id'] = validated_user_id

    user_name = user_data.get('full_name', 'غير معروف')
    username = user_data.get('username', 'لا يوجد')

    text = (
        f"✅ **تم العثور على المستخدم:**\n\n"
        f"👤 الاسم: {user_name}\n"
        f"🆔 المعرف: {validated_user_id}\n"
        f"🔗 اليوزر: @{username if username != 'لا يوجد' else 'غير متوفر'}\n\n"
        f"📝 **أرسل الرسالة الآن:**"
    )

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return AWAITING_MESSAGE_BROADCAST


async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال الرسالة الجماعية (محسّن)"""
    message_text = update.message.text
    broadcast_type = context.user_data.get('broadcast_type', 'all')

    logger.info(f"📢 بدء إرسال بث جماعي - النوع: {broadcast_type}, الرسالة: {message_text[:50]}")

    if broadcast_type == 'all':
        # إرسال لجميع المستخدمين
        all_users = get_all_users()
        logger.info(f"📊 عدد المستخدمين: {len(all_users)}")

        await update.message.reply_text(
            f"📤 جاري الإرسال إلى {len(all_users)} مستخدم..."
        )

        success_count = 0
        failed_count = 0

        for user in all_users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=message_text
                )
                success_count += 1
            except Exception as e:
                log_warning(f"فشل إرسال لـ {user['user_id']}: {e}", module="handlers/admin.py")
                failed_count += 1

        result_text = (
            f"✅ **تم الإرسال!**\n\n"
            f"✔️ نجح: {success_count}\n"
            f"❌ فشل: {failed_count}\n"
            f"📊 الإجمالي: {len(all_users)}"
        )

    else:
        # إرسال لمستخدم محدد
        target_user_id = context.user_data.get('target_user_id')

        if not target_user_id:
            await update.message.reply_text("❌ خطأ! لم يتم تحديد المستخدم.")
            return MAIN_MENU

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=message_text
            )

            result_text = f"✅ **تم إرسال الرسالة بنجاح!**\n\n📨 إلى المستخدم: {target_user_id}"

        except Exception as e:
            log_warning(f"فشل إرسال لـ {target_user_id}: {e}", module="handlers/admin.py")
            result_text = f"❌ **فشل إرسال الرسالة!**\n\n⚠️ تحقق من صحة معرف المستخدم."

    keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="admin_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        result_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    # حذف الحالة
    context.user_data.pop('broadcast_type', None)
    context.user_data.pop('target_user_id', None)

    return MAIN_MENU


async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    return await admin_panel(update, context)

async def admin_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إغلاق لوحة التحكم"""
    query = update.callback_query
    await query.answer(cache_time=0)  # Stop spinner immediately
    await query.edit_message_text("✅ تم إغلاق لوحة التحكم")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة"""
    await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END

# ConversationHandler للوحة التحكم
admin_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('admin', admin_command_handler),  # ✅ معالج أمر /admin
        CallbackQueryHandler(admin_panel, pattern='^admin_panel$'),  # ✅ معالج زر لوحة التحكم من /start
    ],
    states={
        MAIN_MENU: [
            CommandHandler('admin', admin_panel),  # ✅ السماح بإعادة فتح اللوحة من داخل conversation
            CallbackQueryHandler(admin_panel, pattern='^admin$'),  # Handle "Admin" button clicks
            CallbackQueryHandler(admin_panel, pattern='^admin_panel$'),  # Handle "Admin Panel" button clicks
            CallbackQueryHandler(admin_panel, pattern='^admin_main$'),  # Handle "Back to main" button clicks
            CallbackQueryHandler(show_statistics, pattern='^admin_stats$'),
            CallbackQueryHandler(upgrade_user_start, pattern='^admin_upgrade$'),
            CallbackQueryHandler(admin_add_subscription_start, pattern='^admin_add_subscription$'),
            CallbackQueryHandler(admin_cancel_subscription_start, pattern='^admin_cancel_subscription$'),
            CallbackQueryHandler(confirm_cancel_subscription, pattern='^confirm_cancel_sub$'),
            CallbackQueryHandler(manage_logo, pattern='^admin_logo$'),
            CallbackQueryHandler(toggle_logo, pattern='^logo_(enable|disable)$'),
            CallbackQueryHandler(show_animation_selector, pattern='^logo_change_animation$'),
            CallbackQueryHandler(set_animation_type, pattern='^set_anim_'),
            CallbackQueryHandler(show_position_selector, pattern='^logo_change_position$'),
            CallbackQueryHandler(set_position, pattern='^set_pos_'),
            CallbackQueryHandler(show_size_selector, pattern='^logo_change_size$'),
            CallbackQueryHandler(set_size, pattern='^set_size_'),
            CallbackQueryHandler(show_opacity_selector, pattern='^logo_change_opacity$'),
            CallbackQueryHandler(set_opacity, pattern='^set_opacity_'),
            CallbackQueryHandler(show_target_selector, pattern='^logo_change_target$'),
            CallbackQueryHandler(handle_logo_target_set, pattern='^logo_target_'),
            # إدارة المكتبات الجديدة
            CallbackQueryHandler(manage_libraries, pattern='^admin_libraries$'),
            CallbackQueryHandler(manage_libraries, pattern='^manage_libraries$'),  # Back button from cookie upload
            CallbackQueryHandler(library_details, pattern='^library_details$'),
            CallbackQueryHandler(library_stats, pattern='^library_stats$'),
            CallbackQueryHandler(library_approvals, pattern='^library_approvals$'),
            CallbackQueryHandler(library_update, pattern='^library_update$'),
            CallbackQueryHandler(library_reset_stats, pattern='^library_reset_stats$'),
            # معالجات المنصات والموافقة
            CallbackQueryHandler(handle_platform_toggle, pattern='^platform_(enable|disable)_'),
            CallbackQueryHandler(handle_approval_action, pattern='^(approve|deny)_'),
            # معالجات إدارة المنصات والكوكيز الجديدة
            CallbackQueryHandler(show_platform_details, pattern='^platform_'),
            CallbackQueryHandler(test_platform_cookie, pattern='^test_'),
            CallbackQueryHandler(upload_platform_cookie_start, pattern='^upload_'),
            # معالجات VIP Control - Redesigned
            CallbackQueryHandler(show_vip_control_panel, pattern='^admin_vip_control$'),
            CallbackQueryHandler(handle_sub_enable_confirm, pattern='^sub_enable$'),
            CallbackQueryHandler(handle_sub_disable_confirm, pattern='^sub_disable$'),
            CallbackQueryHandler(handle_sub_enable_notify_yes, pattern='^sub_enable_notify_yes$'),
            CallbackQueryHandler(handle_sub_enable_notify_no, pattern='^sub_enable_notify_no$'),
            CallbackQueryHandler(handle_sub_disable_yes, pattern='^sub_disable_yes$'),
            CallbackQueryHandler(handle_sub_action_cancel, pattern='^sub_action_cancel$'),
            CallbackQueryHandler(handle_sub_change_price, pattern='^sub_change_price$'),
            CallbackQueryHandler(handle_sub_set_price, pattern='^sub_price_'),
            CallbackQueryHandler(handle_sub_toggle_notif, pattern='^sub_toggle_notif$'),
            # Mission 10: Download Logs
            CallbackQueryHandler(show_download_logs, pattern='^admin_download_logs$'),
            # Audio Settings
            CallbackQueryHandler(show_audio_settings_panel, pattern='^admin_audio_settings$'),
            CallbackQueryHandler(handle_audio_enable, pattern='^audio_enable$'),
            CallbackQueryHandler(handle_audio_disable, pattern='^audio_disable$'),
            CallbackQueryHandler(handle_audio_preset, pattern='^audio_preset_'),
            CallbackQueryHandler(handle_audio_set_custom_limit, pattern='^audio_set_custom_limit$'),
            # Error Reports
            CallbackQueryHandler(show_error_reports_panel, pattern='^admin_error_reports$'),
            CallbackQueryHandler(handle_resolve_report, pattern='^resolve_report:'),
            CallbackQueryHandler(handle_confirm_resolve, pattern='^confirm_resolve:'),
            # General Limits Control
            CallbackQueryHandler(show_general_limits_panel, pattern='^admin_general_limits$'),
            CallbackQueryHandler(handle_edit_time_limit, pattern='^edit_time_limit$'),
            CallbackQueryHandler(handle_edit_daily_limit, pattern='^edit_daily_limit$'),
            # General Limits Presets (V5.0.1)
            CallbackQueryHandler(handle_set_time_limit_preset, pattern=r'^set_limit_\d+$'),
            CallbackQueryHandler(handle_set_time_limit_preset, pattern=r'^set_limit_unlimited$'),
            CallbackQueryHandler(handle_set_time_limit_custom, pattern=r'^set_limit_custom$'),
            # Cookie Management System V5.0
            CallbackQueryHandler(show_cookie_management_panel, pattern='^admin_cookies$'),
            CallbackQueryHandler(show_cookie_status_detail, pattern='^cookie_status_detail$'),
            CallbackQueryHandler(handle_cookie_test_all, pattern='^cookie_test_all$'),
            CallbackQueryHandler(handle_cookie_test_stories, pattern='^cookie_test_stories$'),
            CallbackQueryHandler(show_cookie_encryption_info, pattern='^cookie_encryption_info$'),
            CallbackQueryHandler(handle_cookie_delete_all, pattern='^cookie_delete_all$'),
            # Cookie deletion confirmation callbacks
            CallbackQueryHandler(confirm_delete_all_cookies_callback, pattern='^confirm_delete_all_cookies$'),
            CallbackQueryHandler(cancel_delete_cookies_callback, pattern='^cancel_delete_cookies$'),
            # Platform Cookie Upload (V5.1)
            CallbackQueryHandler(handle_upload_cookie_button, pattern='^upload_cookie_'),
            # Broadcast System Enhanced
            CallbackQueryHandler(broadcast_start, pattern='^admin_broadcast$'),
            CallbackQueryHandler(broadcast_all_start, pattern='^broadcast_all$'),
            CallbackQueryHandler(broadcast_individual_start, pattern='^broadcast_individual$'),
            # القائمة القديمة
            CallbackQueryHandler(list_users, pattern='^admin_list_users$'),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
            CallbackQueryHandler(admin_panel, pattern='^admin_main$'),
            CallbackQueryHandler(admin_close, pattern='^admin_close$'),
        ],
        AWAITING_USER_ID: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
            CallbackQueryHandler(admin_panel, pattern='^admin_main$'),
        ],
        AWAITING_DAYS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_days),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
        BROADCAST_MESSAGE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
        AWAITING_CUSTOM_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_price),
            CallbackQueryHandler(handle_sub_change_price, pattern='^sub_change_price$'),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
        AWAITING_AUDIO_LIMIT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_audio_limit),
            CallbackQueryHandler(show_audio_settings_panel, pattern='^admin_audio_settings$'),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
        AWAITING_TIME_LIMIT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time_limit),
            CallbackQueryHandler(show_general_limits_panel, pattern='^admin_general_limits$'),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
        AWAITING_DAILY_LIMIT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_daily_limit),
            CallbackQueryHandler(show_general_limits_panel, pattern='^admin_general_limits$'),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
        AWAITING_USER_ID_BROADCAST: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id_broadcast),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
        AWAITING_MESSAGE_BROADCAST: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
        AWAITING_PLATFORM_COOKIE: [
            MessageHandler(filters.Document.ALL, receive_platform_cookie_file),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        CommandHandler('admin', admin_panel),  # ✅ السماح بإعادة فتح اللوحة من أي state
    ],
    # ✅ إزالة per_message=True لأنه يمنع الأزرار من العمل عبر رسائل مختلفة
    # نستخدم الإعدادات الافتراضية: per_chat=True, per_user=True
)