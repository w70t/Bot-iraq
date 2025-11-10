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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ThreadPoolExecutor for async subprocess execution
executor = ThreadPoolExecutor(max_workers=3)

# حالات المحادثة
MAIN_MENU, AWAITING_USER_ID, AWAITING_DAYS, BROADCAST_MESSAGE = range(4)

async def handle_admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج زر Admin Panel من الأزرار التفاعلية"""
    query = update.callback_query
    user_id = query.from_user.id

    # التحقق من صلاحيات الأدمن
    if not is_admin(user_id):
        await query.answer("🚫 You don't have permission to access this section.", show_alert=True)
        return

    # إذا كان أدمن، عرض لوحة التحكم
    await query.answer()
    return await admin_panel(update, context)

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة التحكم الرئيسية"""
    user_id = update.effective_user.id

    # جلب حالة اللوجو
    from database import is_logo_enabled
    logo_status = is_logo_enabled()
    logo_text = "✅ مفعّل" if logo_status else "❌ معطّل"
    
    # جلب حالة المكتبات
    from database import get_allowed_platforms, get_library_settings
    settings = get_library_settings()
    allowed_platforms = get_allowed_platforms()
    # ⭐ تحديث العدد الإجمالي للمنصات المدعومة
    total_platforms = 10  # YouTube, Facebook, Instagram, TikTok, Pinterest, Twitter, Reddit, Vimeo, Dailymotion, Twitch
    enabled_platforms = len(allowed_platforms)
    library_status = f"{enabled_platforms}/{total_platforms} منصات"

    # جلب حالة الاشتراك
    sub_enabled = is_subscription_enabled()
    sub_status = "✅" if sub_enabled else "🚫"

    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("📥 سجل التحميلات", callback_data="admin_download_logs")],
        [InlineKeyboardButton("⭐ ترقية عضو", callback_data="admin_upgrade")],
        [InlineKeyboardButton(f"💎 التحكم بالاشتراك ({sub_status})", callback_data="admin_vip_control")],
        [InlineKeyboardButton(f"🎨 اللوجو ({logo_text})", callback_data="admin_logo")],
        [InlineKeyboardButton(f"📚 المكتبات ({library_status})", callback_data="admin_libraries")],
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
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    return MAIN_MENU

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
    """بدء عملية ترقية المستخدم"""
    query = update.callback_query
    await query.answer()
    
    text = (
        "⭐ ترقية عضو إلى VIP\n\n"
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
    
    keyboard = [
        [InlineKeyboardButton("✅ تفعيل اللوجو", callback_data="logo_enable"),
         InlineKeyboardButton("❌ إيقاف اللوجو", callback_data="logo_disable")],
        [InlineKeyboardButton("🎬 تغيير نوع الحركة", callback_data="logo_change_animation")],
        [InlineKeyboardButton("📍 تغيير الموضع", callback_data="logo_change_position")],
        [InlineKeyboardButton("📏 تغيير الحجم", callback_data="logo_change_size")],
        [InlineKeyboardButton("💎 تغيير الشفافية", callback_data="logo_change_opacity")],
        [InlineKeyboardButton("👥 تغيير الفئة المستهدفة", callback_data="logo_change_target")],
        [InlineKeyboardButton("🔙 العودة", callback_data="admin_back")]
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
    """عرض قائمة اختيار الفئة المستهدفة لتطبيق اللوجو"""
    query = update.callback_query
    await query.answer()
    
    from database import get_logo_target
    current_target, current_target_name = get_logo_target()
    
    text = (
        f"🎯 اختر الفئة المستهدفة لتطبيق اللوجو:\n\n"
        f"💡 **شرح مبسط:**\n\n"
        f"👥 **العاديون:**\n"
        f"• مع النقاط: ضع اللوجو على العاديين (لا يهم النقاط)\n"
        f"• بدون النقاط: ضع اللوجو على العاديين الذين **ليس** لديهم نقاط\n"
        f"• جميع العاديون: ضع اللوجو على كل العاديين\n\n"
        f"⭐ **VIP:**\n"
        f"• مع النقاط: ضع اللوجو على VIP (لا يهم النقاط)\n"
        f"• بدون النقاط: ضع اللوجو على VIP الذين **ليس** لديهم نقاط\n"
        f"• جميع VIP: ضع اللوجو على كل VIP\n\n"
        f"🌟 **الجميع:**\n"
        f"• مع النقاط: ضع اللوجو على الجميع (لا يهم النقاط)\n"
        f"• بدون النقاط: ضع اللوجو على من **ليس** لديهم نقاط\n"
        f"• الجميع: ضع اللوجو على كل المستخدمين\n\n"
        f"✅ الخيار الحالي: {current_target_name}\n\n"
        f"📌 **مثال:** إذا اخترت \"العاديون - بدون النقاط\"، سيظهر اللوجو فقط للمستخدمين العاديين الذين ليس لديهم نقاط مجانية"
    )
    
    keyboard = [
        [InlineKeyboardButton("👥 العاديون", callback_data="logo_category_free")],
        [InlineKeyboardButton("⭐ VIP", callback_data="logo_category_vip")],
        [InlineKeyboardButton("🌟 الجميع", callback_data="logo_category_everyone")],
        [InlineKeyboardButton("🔙 العودة", callback_data="admin_logo")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )
    
    return MAIN_MENU


async def show_logo_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إظهار الخيارات التفصيلية للفئات"""
    query = update.callback_query
    await query.answer()
    
    from database import get_logo_target
    current_target, _ = get_logo_target()
    
    category = query.data.replace("logo_category_", "")
    
    if category == "free":
        text = "👥 العاديون - اختر الخيار:\n\n• مع النقاط = ضع اللوجو على كل العاديين\n• بدون النقاط = ضع اللوجو على العاديين بدون نقاط\n• الجميع = كل العاديين"
        buttons = [
            [InlineKeyboardButton(
                "✅ مع النقاط (كل العاديين)" if current_target == 'free_with_points' else "⚪ مع النقاط (كل العاديين)",
                callback_data="set_target_free_with_points"
            )],
            [InlineKeyboardButton(
                "✅ بدون النقاط (من ليس لديه نقاط)" if current_target == 'free_no_points' else "⚪ بدون النقاط (من ليس لديه نقاط)",
                callback_data="set_target_free_no_points"
            )],
            [InlineKeyboardButton(
                "✅ جميع العاديون" if current_target == 'free_all' else "⚪ جميع العاديون",
                callback_data="set_target_free_all"
            )]
        ]
    elif category == "vip":
        text = "⭐ VIP - اختر الخيار:\n\n• مع النقاط = ضع اللوجو على كل VIP\n• بدون النقاط = ضع اللوجو على VIP بدون نقاط\n• الجميع = كل VIP"
        buttons = [
            [InlineKeyboardButton(
                "✅ مع النقاط (كل VIP)" if current_target == 'vip_with_points' else "⚪ مع النقاط (كل VIP)",
                callback_data="set_target_vip_with_points"
            )],
            [InlineKeyboardButton(
                "✅ بدون النقاط (من ليس لديه نقاط)" if current_target == 'vip_no_points' else "⚪ بدون النقاط (من ليس لديه نقاط)",
                callback_data="set_target_vip_no_points"
            )],
            [InlineKeyboardButton(
                "✅ جميع VIP" if current_target == 'vip_all' else "⚪ جميع VIP",
                callback_data="set_target_vip_all"
            )]
        ]
    elif category == "everyone":
        text = "🌟 الجميع - اختر الخيار:\n\n• مع النقاط = ضع اللوجو على الجميع\n• بدون النقاط = ضع اللوجو على من ليس لديه نقاط\n• الجميع = كل المستخدمين"
        buttons = [
            [InlineKeyboardButton(
                "✅ مع النقاط (الجميع)" if current_target == 'everyone_with_points' else "⚪ مع النقاط (الجميع)",
                callback_data="set_target_everyone_with_points"
            )],
            [InlineKeyboardButton(
                "✅ بدون النقاط (من ليس لديه نقاط)" if current_target == 'everyone_no_points' else "⚪ بدون النقاط (من ليس لديه نقاط)",
                callback_data="set_target_everyone_no_points"
            )],
            [InlineKeyboardButton(
                "✅ الجميع" if current_target == 'everyone_all' else "⚪ الجميع",
                callback_data="set_target_everyone_all"
            )]
        ]
    else:
        # في حالة الخطأ، العودة للقائمة الرئيسية
        return await show_target_selector(update, context)
    
    # إضافة زر العودة
    buttons.append([InlineKeyboardButton("🔙 العودة لقائمة الفئات", callback_data="set_target_main")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return MAIN_MENU


async def show_main_target_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية لاختيار الفئة"""
    query = update.callback_query
    await query.answer()
    return await show_target_selector(update, context)


async def set_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعيين الفئة المستهدفة لتطبيق اللوجو"""
    query = update.callback_query
    
    from database import set_logo_target
    
    # استخراج الفئة المستهدفة من callback_data
    target = query.data.replace("set_target_", "")
    
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
    
    set_logo_target(target)
    await query.answer(f"✅ تم تعيين الفئة المستهدفة إلى: {target_names[target]}", show_alert=True)
    
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

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الرسالة الجماعية"""
    query = update.callback_query
    await query.answer()
    
    text = (
        "📢 إرسال رسالة جماعية\n\n"
        "أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:\n\n"
        "⚠️ تأكد من صياغة الرسالة بعناية!"
    )
    
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )
    
    return BROADCAST_MESSAGE

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال الرسالة الجماعية"""
    message_text = update.message.text
    all_users = get_all_users()
    
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
        f"✅ تم الإرسال!\n\n"
        f"✔️ نجح: {success_count}\n"
        f"❌ فشل: {failed_count}\n"
        f"📊 الإجمالي: {len(all_users)}"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="admin_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        result_text,
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

async def manage_libraries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة المكتبات والمنصات"""
    query = update.callback_query
    await query.answer()
    
    # جلب إعدادات المكتبات
    from database import (
        get_library_settings, get_allowed_platforms, get_library_status,
        get_performance_metrics, get_pending_approvals
    )
    
    settings = get_library_settings()
    if not settings:
        await query.edit_message_text("❌ خطأ في تحميل إعدادات المكتبات")
        return MAIN_MENU
    
    allowed_platforms = get_allowed_platforms()
    library_status = get_library_status()
    performance = get_performance_metrics()
    pending_approvals = get_pending_approvals()
    
    # إنشاء نص التقرير
    total_downloads = performance.get('total_downloads', 0)
    success_rate = 0
    if total_downloads > 0:
        successful = performance.get('successful_downloads', 0)
        success_rate = (successful / total_downloads) * 100
    
    message_text = (
        "📚 **إدارة المكتبات والمنصات**\n\n"
        f"🟢 **المكتبة الأساسية:** {settings.get('primary_library', 'yt-dlp')}\n"
        f"🔄 **التحديث التلقائي:** {'✅ مفعّل' if settings.get('auto_update', True) else '❌ معطّل'}\n\n"
        f"📊 **إحصائيات الأداء:**\n"
        f"• إجمالي التحميلات: {total_downloads}\n"
        f"• معدل النجاح: {success_rate:.1f}%\n"
        f"• متوسط السرعة: {performance.get('avg_download_speed', 0):.1f} MB/s\n\n"
        f"🎯 **المنصات المسموحة:** {len(allowed_platforms)}/6\n"
    )
    
    # ⭐ إضافة معلومات المنصات - قائمة موسعة
    platform_emojis = {
        'youtube': '🔴',
        'facebook': '🔵', 
        'instagram': '🟣',
        'tiktok': '⚫',
        'pinterest': '🔴',
        'twitter': '⚪',
        'reddit': '🟠',
        'vimeo': '🔵',
        'dailymotion': '🟡',
        'twitch': '🟣'
    }
    
    platform_names = {
        'youtube': 'YouTube',
        'facebook': 'Facebook',
        'instagram': 'Instagram', 
        'tiktok': 'TikTok',
        'pinterest': 'Pinterest',
        'twitter': 'Twitter/X',
        'reddit': 'Reddit',
        'vimeo': 'Vimeo',
        'dailymotion': 'Dailymotion',
        'twitch': 'Twitch'
    }
    
    # عرض جميع المنصات
    all_platforms = ['youtube', 'facebook', 'instagram', 'tiktok', 'pinterest', 'twitter', 'reddit', 'vimeo', 'dailymotion', 'twitch']
    for platform in all_platforms:
        status = "✅" if platform in allowed_platforms else "❌"
        emoji = platform_emojis.get(platform, '🔗')
        name = platform_names.get(platform, platform)
        message_text += f"{status} {emoji} {name}\n"
    
    if pending_approvals:
        message_text += f"\n🔔 **طلبات الانتظار:** {len(pending_approvals)}"
    
    # إنشاء أزرار التحكم
    keyboard = [
        [InlineKeyboardButton("📊 عرض التفاصيل", callback_data="library_details")],
        [InlineKeyboardButton("🔄 تحديث المكتبات", callback_data="library_update")],
        [InlineKeyboardButton("📈 إحصائيات الأداء", callback_data="library_stats")],
        [InlineKeyboardButton("✅ طلبات الموافقة", callback_data="library_approvals")]
    ]
    
    if pending_approvals:
        keyboard.insert(0, [InlineKeyboardButton("📩 عرض الطلبات المعلقة", callback_data="library_approvals")])
    
    # إضافة أزرار المنصات - 3 منصات في كل صف
    platform_rows = []
    current_row = []
    
    for platform in all_platforms:
        status = "❌" if platform in allowed_platforms else "✅"
        name = platform_names.get(platform, platform)
        callback_data_str = f"platform_disable_{platform}" if platform in allowed_platforms else f"platform_enable_{platform}"
        
        # ⚠️ FIX: استخدام callback_data كمعامل مسمى بدلاً من موضعي
        current_row.append(InlineKeyboardButton(f"{status} {name}", callback_data=callback_data_str))
        
        # كل 3 منصات، ننشئ صف جديد
        if len(current_row) == 3:
            platform_rows.append(current_row)
            current_row = []
    
    # إضافة آخر صف إذا كان غير مكتمل
    if current_row:
        platform_rows.append(current_row)
    
    keyboard.extend(platform_rows)
    
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="admin_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
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
#  VIP Subscription Control Panel - Mission 5
# ═══════════════════════════════════════════════════════════════

async def show_vip_control_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة التحكم بنظام الاشتراك VIP"""
    query = update.callback_query
    await query.answer()

    # جلب الحالة الحالية
    sub_enabled = is_subscription_enabled()
    welcome_enabled = is_welcome_broadcast_enabled()

    # رموز الحالة
    sub_icon = "✅ Enabled" if sub_enabled else "🚫 Disabled"
    welcome_icon = "✅ Enabled" if welcome_enabled else "🚫 Disabled"

    message_text = (
        "💎 **لوحة التحكم بالاشتراك / Subscription Control Panel**\n\n"
        "📊 **الحالة الحالية / Current Status:**\n"
        f"💎 الاشتراك / Subscription: {sub_icon}\n"
        f"💬 رسالة الترحيب / Welcome Broadcast: {welcome_icon}\n\n"
        "اختر الإجراء المطلوب:"
    )

    keyboard = [
        [InlineKeyboardButton("✅ تفعيل الاشتراك / Enable Subscriptions", callback_data="vip_enable_sub")],
        [InlineKeyboardButton("❌ إيقاف الاشتراك / Disable Subscriptions", callback_data="vip_disable_sub")],
        [InlineKeyboardButton("💬 تفعيل/إلغاء رسالة الترحيب / Toggle Welcome", callback_data="vip_toggle_welcome")],
        [InlineKeyboardButton("📊 عرض الحالة الحالية / Show Current Status", callback_data="vip_show_status")],
        [InlineKeyboardButton("🔙 العودة / Back", callback_data="admin_back")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # فحص إذا كانت الرسالة مختلفة قبل التعديل
    try:
        if query.message.text != message_text:
            await query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        # إذا فشل التعديل، نتجاهل الخطأ
        logger.debug(f"تم تجاهل خطأ تعديل الرسالة: {e}")

    return MAIN_MENU


async def toggle_subscription_enabled(update: Update, context: ContextTypes.DEFAULT_TYPE, enable: bool):
    """تفعيل أو إيقاف نظام الاشتراك"""
    query = update.callback_query
    await query.answer()

    # حفظ التغيير في قاعدة البيانات
    success = set_subscription_enabled(enable)

    if not success:
        await query.answer("❌ فشل حفظ التغيير!", show_alert=True)
        return MAIN_MENU

    # الحالة الجديدة
    status_ar = "✅ مفعّل" if enable else "❌ معطّل"
    status_en = "✅ Enabled" if enable else "❌ Disabled"

    # إرسال تقرير إلى قناة السجلات
    import os
    from telegram import Bot

    LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
    admin_username = query.from_user.username or "Unknown"
    timestamp = datetime.now().strftime("%H:%M — %d-%m-%Y")

    if LOG_CHANNEL_ID:
        try:
            bot = context.bot
            log_text = (
                "🧭 *تغيير حالة نظام الاشتراك / Subscription Status Changed*\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👤 المسؤول / Admin: @{admin_username}\n"
                f"💠 الحالة الجديدة / New Status: {status_en}\n"
                f"🕒 الوقت / Time: {timestamp}\n"
                "━━━━━━━━━━━━━━━━━━"
            )
            await bot.send_message(
                chat_id=LOG_CHANNEL_ID,
                text=log_text,
                parse_mode='Markdown'
            )
        except Exception as e:
            log_warning(f"فشل إرسال تقرير الاشتراك إلى القناة: {e}", module="handlers/admin.py")

    # إرسال رسالة ترحيب لجميع المستخدمين إذا تم التفعيل
    if enable and is_welcome_broadcast_enabled():
        from database import get_all_users
        all_users = get_all_users()
        success_count = 0
        failed_count = 0

        welcome_text = (
            "💎 *نظام الاشتراك VIP تم تفعيله! / VIP Subscription System Enabled!*\n\n"
            "✨ ستحصل قريباً على مزايا إضافية مثل:\n"
            "🎞️ تحميل أسرع، 💬 دعم مباشر، 🎁 هدايا خاصة\n"
            "📢 تابع القناة الرسمية لمزيد من التفاصيل 🔗"
        )

        for user in all_users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=welcome_text,
                    parse_mode='Markdown'
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                log_warning(f"فشل إرسال رسالة ترحيب لـ {user['user_id']}: {e}", module="handlers/admin.py")

        broadcast_result = f"\n📢 تم إرسال رسالة ترحيب: ✅ {success_count} | ❌ {failed_count}"
    else:
        broadcast_result = ""

    # تأكيد خاص للأدمن
    confirmation_text = (
        "✅ *تم حفظ التغيير بنجاح! / Change saved successfully!*\n\n"
        f"💎 الحالة الجديدة / New Status: {status_en}\n"
        "📦 تم تحديث الإعدادات في قاعدة البيانات (MongoDB)"
        f"{broadcast_result}"
    )

    await query.answer("✅ تم الحفظ بنجاح!", show_alert=True)

    # العودة إلى لوحة VIP
    await show_vip_control_panel(update, context)


async def handle_vip_enable_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تفعيل الاشتراك"""
    return await toggle_subscription_enabled(update, context, True)


async def handle_vip_disable_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إيقاف الاشتراك"""
    return await toggle_subscription_enabled(update, context, False)


async def toggle_welcome_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تفعيل أو إيقاف رسالة الترحيب"""
    query = update.callback_query
    await query.answer()

    # الحصول على الحالة الحالية
    current_status = is_welcome_broadcast_enabled()
    new_status = not current_status

    # حفظ التغيير
    success = set_welcome_broadcast_enabled(new_status)

    if success:
        status_text = "✅ مفعّلة / Enabled" if new_status else "❌ معطّلة / Disabled"
        await query.answer(f"✅ رسالة الترحيب الآن: {status_text}", show_alert=True)
    else:
        await query.answer("❌ فشل حفظ التغيير!", show_alert=True)

    # العودة إلى لوحة VIP
    return await show_vip_control_panel(update, context)


async def show_current_vip_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الحالة الحالية لنظام الاشتراك"""
    query = update.callback_query
    await query.answer()

    from database import get_all_users

    # جلب الحالة الحالية
    sub_enabled = is_subscription_enabled()
    welcome_enabled = is_welcome_broadcast_enabled()
    all_users = get_all_users()
    total_users = len(all_users)

    # رموز الحالة
    sub_icon = "✅ Enabled" if sub_enabled else "🚫 Disabled"
    welcome_icon = "✅ Enabled" if welcome_enabled else "🚫 Disabled"

    status_text = (
        "📊 *الحالة الحالية / Current Status*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 الاشتراك / Subscription: {sub_icon}\n"
        f"💬 رسالة الترحيب / Welcome: {welcome_icon}\n"
        f"👥 عدد المستخدمين / Total Users: {total_users}\n\n"
        f"🕒 الوقت / Time: {datetime.now().strftime('%H:%M — %d-%m-%Y')}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    keyboard = [[InlineKeyboardButton("🔙 العودة / Back", callback_data="admin_vip_control")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # فحص إذا كانت الرسالة مختلفة قبل التعديل
    try:
        if query.message.text != status_text:
            await query.edit_message_text(
                status_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.debug(f"تم تجاهل خطأ تعديل الرسالة: {e}")

    return MAIN_MENU


async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    return await admin_panel(update, context)

async def admin_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إغلاق لوحة التحكم"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ تم إغلاق لوحة التحكم")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة"""
    await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END

# ConversationHandler للوحة التحكم
admin_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('admin', admin_panel)],
    states={
        MAIN_MENU: [
            CallbackQueryHandler(show_statistics, pattern='^admin_stats$'),
            CallbackQueryHandler(upgrade_user_start, pattern='^admin_upgrade$'),
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
            CallbackQueryHandler(show_main_target_menu, pattern='^set_target_main$'),
            CallbackQueryHandler(show_logo_category, pattern='^logo_category_'),
            CallbackQueryHandler(set_target, pattern='^set_target_'),
            # إدارة المكتبات الجديدة
            CallbackQueryHandler(manage_libraries, pattern='^admin_libraries$'),
            CallbackQueryHandler(library_details, pattern='^library_details$'),
            CallbackQueryHandler(library_stats, pattern='^library_stats$'),
            CallbackQueryHandler(library_approvals, pattern='^library_approvals$'),
            CallbackQueryHandler(library_update, pattern='^library_update$'),
            CallbackQueryHandler(library_reset_stats, pattern='^library_reset_stats$'),
            # معالجات المنصات والموافقة
            CallbackQueryHandler(handle_platform_toggle, pattern='^platform_(enable|disable)_'),
            CallbackQueryHandler(handle_approval_action, pattern='^(approve|deny)_'),
            # معالجات VIP Control - Mission 5
            CallbackQueryHandler(show_vip_control_panel, pattern='^admin_vip_control$'),
            CallbackQueryHandler(handle_vip_enable_sub, pattern='^vip_enable_sub$'),
            CallbackQueryHandler(handle_vip_disable_sub, pattern='^vip_disable_sub$'),
            CallbackQueryHandler(toggle_welcome_broadcast, pattern='^vip_toggle_welcome$'),
            CallbackQueryHandler(show_current_vip_status, pattern='^vip_show_status$'),
            # Mission 10: Download Logs
            CallbackQueryHandler(show_download_logs, pattern='^admin_download_logs$'),
            # القائمة القديمة
            CallbackQueryHandler(list_users, pattern='^admin_list_users$'),
            CallbackQueryHandler(broadcast_start, pattern='^admin_broadcast$'),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
            CallbackQueryHandler(admin_panel, pattern='^admin_main$'),
            CallbackQueryHandler(admin_close, pattern='^admin_close$'),
        ],
        AWAITING_USER_ID: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
            CallbackQueryHandler(admin_back, pattern='^admin_main$'),
        ],
        AWAITING_DAYS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_days),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
        BROADCAST_MESSAGE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)