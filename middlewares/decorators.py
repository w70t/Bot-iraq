"""
Decorators لتقليل تكرار الكود
"""
from functools import wraps
from config.logger import get_logger

logger = get_logger(__name__)

def admin_only(func):
    """
    Decorator للتحقق من صلاحيات الأدمن

    استخدام:
        @admin_only
        async def admin_command(update, context):
            ...
    """
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        from database import is_admin, get_user_language
        from config.messages import get_message

        user_id = update.effective_user.id

        if not is_admin(user_id):
            lang = get_user_language(user_id)
            message = get_message(lang, 'admin_only_command',
                                'عذراً، هذا الأمر متاح للمشرفين فقط.')

            try:
                await update.message.reply_text(message)
            except:
                try:
                    await update.callback_query.message.reply_text(message)
                except:
                    pass

            return None

        return await func(update, context, *args, **kwargs)

    return wrapper


def with_language(func):
    """
    Decorator لإضافة اللغة تلقائياً إلى context

    استخدام:
        @with_language
        async def my_command(update, context):
            lang = context.user_data['lang']
            ...
    """
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        from database import get_user_language, update_user_interaction

        user_id = update.effective_user.id
        lang = get_user_language(user_id)

        # إضافة اللغة إلى context
        if 'user_data' not in context.__dict__:
            context.user_data = {}
        context.user_data['lang'] = lang
        context.user_data['user_id'] = user_id

        # تحديث آخر تفاعل
        update_user_interaction(user_id)

        return await func(update, context, *args, **kwargs)

    return wrapper


def with_db_connection(func):
    """
    Decorator للتحقق من اتصال قاعدة البيانات

    استخدام:
        @with_db_connection
        async def save_data(update, context):
            ...
    """
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        from database import ensure_db_connection

        if not ensure_db_connection():
            logger.error("❌ Database connection lost")

            try:
                await update.message.reply_text(
                    "عذراً، حدث خطأ في الاتصال بقاعدة البيانات. حاول مرة أخرى لاحقاً."
                )
            except:
                try:
                    await update.callback_query.message.reply_text(
                        "عذراً، حدث خطأ في الاتصال بقاعدة البيانات. حاول مرة أخرى لاحقاً."
                    )
                except:
                    pass

            return None

        return await func(update, context, *args, **kwargs)

    return wrapper


def handle_errors(func):
    """
    Decorator موحد لمعالجة الأخطاء

    استخدام:
        @handle_errors
        async def risky_operation(update, context):
            ...
    """
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Error in {func.__name__}: {e}", exc_info=True)

            # محاولة إرسال رسالة خطأ للمستخدم
            error_message = "عذراً، حدث خطأ غير متوقع. تم تسجيل الخطأ وسيتم معالجته قريباً."

            try:
                if update.message:
                    await update.message.reply_text(error_message)
                elif update.callback_query:
                    await update.callback_query.message.reply_text(error_message)
            except:
                pass

            # محاولة إرسال تقرير الخطأ
            try:
                from utils import send_critical_log
                send_critical_log(
                    f"Error in {func.__name__}: {str(e)}",
                    module=func.__module__
                )
            except:
                pass

            return None

    return wrapper
