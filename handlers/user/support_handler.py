"""
معالج نظام الدعم (Support Creator System)
يعرض معلومات الدعم عبر Binance و Instagram
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import get_user_language

logger = logging.getLogger(__name__)

async def show_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    عرض رسالة الدعم الرئيسية مع خيارات الدفع
    """
    user_id = update.effective_user.id
    lang = get_user_language(user_id)

    # معرف الدفع Binance
    BINANCE_WALLET = os.getenv("BINANCE_WALLET", "86847466")

    # الرسالة الثنائية اللغة
    support_message = (
        "💝 **شكراً على دعمك! / Thank you for your support!**\n\n"
        "════════════════════\n\n"
        "يمكنك دعم تطوير البوت عبر:\n"
        "You can support the bot development via:\n\n"
        "💰 **Binance Pay**\n"
        f"📋 Pay ID: `{BINANCE_WALLET}`\n\n"
        "📸 **Instagram**\n"
        "👤 Username: @7kmmy\n"
        "🔗 [instagram.com/7kmmy](https://instagram.com/7kmmy)\n\n"
        "════════════════════\n\n"
        "🙏 دعمك يساعدنا في:\n"
        "Your support helps us:\n\n"
        "✨ تطوير مزايا جديدة / Add new features\n"
        "⚡ تحسين الأداء / Improve performance\n"
        "🛡️ تقديم دعم أفضل / Provide better support\n\n"
        "💖 شكراً لكونك جزءاً من مجتمعنا!\n"
        "Thank you for being part of our community!"
    )

    # إنشاء الأزرار
    keyboard = [
        [InlineKeyboardButton("📱 عرض رمز QR / Show QR Code", callback_data="support_show_qr")],
        [InlineKeyboardButton("🌐 فتح Instagram / Open Instagram", url="https://instagram.com/7kmmy")],
        [InlineKeyboardButton("🔙 العودة / Back", callback_data="support_back")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # إرسال أو تعديل الرسالة
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        # فحص إذا كانت الرسالة مختلفة قبل التعديل
        if query.message.text != support_message:
            await query.edit_message_text(
                text=support_message,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
    else:
        await update.message.reply_text(
            support_message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )


def create_placeholder_qr(qr_image_path: str) -> bool:
    """
    إنشاء صورة بديلة لرمز QR إذا لم تكن موجودة
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        # إنشاء صورة بخلفية بيضاء
        img = Image.new('RGB', (500, 500), color='white')
        draw = ImageDraw.Draw(img)

        # رسم مربع للإشارة إلى مكان QR
        draw.rectangle([(50, 50), (450, 450)], outline='#FF9800', width=5)

        # إضافة نص توضيحي
        text = "QR Code\nNot Found\n\nPlease upload\nQR image to:\nassets/binance_qr.jpeg"

        # رسم النص في المنتصف
        draw.multiline_text(
            (250, 250),
            text,
            fill='#FF9800',
            anchor="mm",
            align="center"
        )

        # حفظ الصورة
        os.makedirs(os.path.dirname(qr_image_path), exist_ok=True)
        img.save(qr_image_path)
        logger.info(f"Created placeholder QR image at: {qr_image_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create placeholder QR: {e}")
        return False


async def show_qr_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    إرسال رمز QR الخاص بـ Binance Pay
    يدعم عدة صيغ للصورة: .jpeg, .JPG, .jpg, .png
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    lang = get_user_language(user_id)

    # مسار الصورة (استخدام مسار مطلق)
    import os.path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_dir, "assets")

    # البحث عن صورة QR بأي من الامتدادات المدعومة
    qr_extensions = ['jpeg', 'JPG', 'jpg', 'png', 'JPEG', 'PNG']
    qr_image_path = None

    for ext in qr_extensions:
        potential_path = os.path.join(assets_dir, f"binance_qr.{ext}")
        if os.path.exists(potential_path):
            qr_image_path = potential_path
            logger.info(f"✅ Found QR image at: {qr_image_path}")
            break

    # إذا لم يتم العثور على الصورة
    if not qr_image_path:
        logger.warning(f"QR image not found in {assets_dir}. Tried extensions: {qr_extensions}")

        # محاولة إنشاء placeholder
        placeholder_path = os.path.join(assets_dir, "binance_qr.jpeg")
        if not create_placeholder_qr(placeholder_path):
            # فشل إنشاء placeholder - إرسال رسالة نصية فقط
            await query.answer("❌ QR image missing", show_alert=True)

            error_message = (
                "❌ عذراً، رمز QR غير متوفر حالياً.\n"
                "Sorry, QR code is not available at the moment.\n\n"
                f"📋 يمكنك استخدام Pay ID: `{os.getenv('BINANCE_WALLET', '86847466')}`\n"
                f"You can use Pay ID: `{os.getenv('BINANCE_WALLET', '86847466')}`"
            )

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=error_message,
                parse_mode='Markdown'
            )
            return
        else:
            qr_image_path = placeholder_path

    # رسالة مرفقة مع الصورة
    caption = (
        "💰 **Binance Pay QR Code**\n\n"
        f"📋 Pay ID: `{os.getenv('BINANCE_WALLET', '86847466')}`\n\n"
        "📸 امسح الرمز من تطبيق Binance\n"
        "Scan the code from Binance app\n\n"
        "🙏 شكراً لدعمك! / Thank you for your support!"
    )

    try:
        # إرسال الصورة
        with open(qr_image_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo,
                caption=caption,
                parse_mode='Markdown'
            )

        # إرسال تأكيد
        logger.info(f"QR code sent successfully to user {user_id}")
        await query.answer("✅ تم إرسال رمز QR / QR code sent!")

    except FileNotFoundError as e:
        logger.error(f"QR file not found: {e}")
        await query.answer("❌ ملف QR غير موجود / QR file not found", show_alert=True)
    except Exception as e:
        logger.error(f"فشل إرسال رمز QR: {e}", exc_info=True)
        await query.answer("❌ حدث خطأ في إرسال رمز QR / Error sending QR code", show_alert=True)


async def support_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    العودة إلى القائمة الرئيسية
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    lang = get_user_language(user_id)

    # رسالة العودة
    back_message = (
        "✅ تم العودة للقائمة الرئيسية\n"
        "Returned to main menu"
    ) if lang == "ar" else (
        "✅ Returned to main menu\n"
        "تم العودة للقائمة الرئيسية"
    )

    try:
        await query.delete_message()
    except Exception:
        pass

    # إرسال رسالة بسيطة
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=back_message
    )
