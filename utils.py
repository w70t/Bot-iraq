#!/usr/bin/env python3
"""
ملف وظائف محدث مع إصلاح FFmpeg للصورة المتحركة
"""

import os
import subprocess
import logging
import re
import threading
from time import time
from datetime import datetime
from telegram import BotCommand, BotCommandScopeChat
from telegram.ext import Application
import json

# ⭐ تحميل متغيرات البيئة
from dotenv import load_dotenv
load_dotenv()

# تهيئة الرسائل والإعدادات كمتغيرات عامة
MESSAGES = {}
CONFIG = {}

logger = logging.getLogger(__name__)

def load_messages():
    """تحميل الرسائل من ملف messages.json"""
    global MESSAGES
    try:
        with open('messages.json', 'r', encoding='utf-8') as f:
            MESSAGES = json.load(f)
    except Exception as e:
        logger.error(f"❌ فشل تحميل الرسائل: {e}")
        MESSAGES = {}

def load_config():
    """يقوم بتحميل الإعدادات من ملف JSON ودمجها مع متغيرات البيئة"""
    global CONFIG
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
        logger.info("✅ تم تحميل ملف الإعدادات بنجاح.")

        # ⭐ دمج المتغيرات السرية من ملف .env
        # إضافة بيانات Binance من متغيرات البيئة
        CONFIG['binance_api_key'] = os.getenv('BINANCE_API_KEY', 'YOUR_BINANCE_API_KEY_HERE')
        CONFIG['binance_secret_key'] = os.getenv('BINANCE_SECRET_KEY', 'YOUR_BINANCE_SECRET_KEY_HERE')

        # إضافة معلومات الدفع عبر Instagram من متغيرات البيئة
        CONFIG['instagram_payment'] = {
            'username': os.getenv('INSTAGRAM_PAYMENT_USERNAME', '7kmmy'),
            'message_ar': f"شكراً لاختيارك! تواصل عبر الإنستغرام @{os.getenv('INSTAGRAM_PAYMENT_USERNAME', '7kmmy')} للدفع",
            'message_en': f"Thank you for choosing! Contact @{os.getenv('INSTAGRAM_PAYMENT_USERNAME', '7kmmy')} on Instagram for payment"
        }

        # إضافة سعر الاشتراك من متغيرات البيئة
        CONFIG['subscription_price_usd'] = float(os.getenv('SUBSCRIPTION_PRICE_USD', '3.0'))

        logger.info("✅ تم دمج متغيرات البيئة مع الإعدادات.")

    except FileNotFoundError:
        logger.error("!!! ملف config.json غير موجود. سيتم استخدام إعدادات افتراضية.")
        CONFIG = {}
    except json.JSONDecodeError:
        logger.error("!!! خطأ في قراءة ملف config.json. تأكد من أن تنسيقه صحيح.")
        CONFIG = {}

def get_message(lang, key):
    """الحصول على رسالة محددة"""
    return MESSAGES.get(lang, {}).get(key, key)

def get_config():
    """يجلب الإعدادات المحملة"""
    return CONFIG

def get_logo_overlay_position(position):
    """
    الحصول على إحداثيات وضع اللوجو
    """
    positions = {
        'top_left': (10, 10),
        'top_right': ('W-w-10', 10),
        'bottom_left': (10, 'H-h-10'),
        'bottom_right': ('W-w-10', 'H-h-10'),
        'center': ('(W-w)/2', '(H-h)/2'),
        'center_right': ('W-w-10', '(H-h)/2'),
        'center_left': ('10', '(H-h)/2'),
        'top_center': ('(W-w)/2', '10'),
        'bottom_center': ('(W-w)/2', 'H-h-10'),
    }
    
    x, y = positions.get(position, positions['center_right'])
    return x, y

def apply_simple_watermark(input_path, output_path, logo_path, animation_type='corner_rotation', size=150, position='top_right', opacity=0.7):
    """
    دالة موحدة ومبسطة لإضافة اللوجو - محسّنة للأداء
    جميع الحركات تحترم الموضع المختار من المستخدم

    📍 **شرح المميزات:**
    • static: ثابت تماماً في الموضع المحدد (لا يتحرك)
    • المتحركات: تتحرك حول الموضع المحدد (وسط، تحت، إلخ)

    ⚡ **تحسينات الأداء:**
    • ultrafast preset لسرعة المعالجة
    • CRF 28 لتقليل حجم الملف
    • معالجة أولوية منخفضة لتقليل حمل CPU
    """
    try:
        # الحصول على إحداثيات الموضع المختار
        pos_x, pos_y = get_logo_overlay_position(position)
        
        # تحويل إلى string
        if isinstance(pos_x, str):
            overlay_x = pos_x
        else:
            overlay_x = str(pos_x)
            
        if isinstance(pos_y, str):
            overlay_y = pos_y
        else:
            overlay_y = str(pos_y)
        
        # الشفافية
        if opacity < 1.0:
            opacity_filter = f"[1:v]scale={size}:-1,format=rgba,colorchannelmixer=aa={opacity}[logo]"
        else:
            opacity_filter = f"[1:v]scale={size}:-1,format=rgba[logo]"
        
        # اختيار الحركة حسب النوع
        if animation_type == 'static':
            # 🔒 ثابت تماماً في الموضع المختار (لا يتحرك مطلقاً)
            filter_complex = f"{opacity_filter};[0:v][logo]overlay={overlay_x}:{overlay_y}"
            logger.info(f"🔒 تطبيق لوجو ثابت في الموضع: {position}")
            
        elif animation_type == 'corner_rotation':
            # 🔄 يتحرك بين 4 زوايا حول الموضع المختار
            # إذا اختار "وسط" → يدور حول الوسط في مربع صغير
            # إذا اختار "تحت" → يدور في الأسفل
            filter_complex = (
                f"{opacity_filter};"
                "[0:v][logo]overlay="
                f"x='{overlay_x}+if(lt(mod(n,240),60),-30,if(lt(mod(n,240),120),30,if(lt(mod(n,240),180),30,-30)))':"
                f"y='{overlay_y}+if(lt(mod(n,240),60),-30,if(lt(mod(n,240),120),-30,if(lt(mod(n,240),180),30,30)))'"
            )
            logger.info(f"🔄 تطبيق حركة الزوايا في الموضع: {position}")
            
        elif animation_type == 'bounce':
            # ⬆️ يرتد حول الموضع المختار (دائرة صغيرة)
            filter_complex = (
                f"{opacity_filter};"
                "[0:v][logo]overlay="
                f"x='{overlay_x}+30*sin(n/20)':"
                f"y='{overlay_y}+30*cos(n/20)'"
            )
            logger.info(f"⬆️ تطبيق حركة الارتداد في الموضع: {position}")
            
        elif animation_type == 'slide':
            # ➡️ ينزلق يميناً ويساراً حول الموضع المختار
            filter_complex = (
                f"{opacity_filter};"
                "[0:v][logo]overlay="
                f"x='{overlay_x}+50*sin(n/40)':"
                f"y='{overlay_y}'"
            )
            logger.info(f"➡️ تطبيق حركة الانزلاق في الموضع: {position}")
            
        elif animation_type == 'fade':
            # 💫 ثابت في الموضع المختار مع تأثير التلاشي
            filter_complex = f"{opacity_filter};[0:v][logo]overlay={overlay_x}:{overlay_y}"
            logger.info(f"💫 تطبيق حركة التلاشي في الموضع: {position}")
            
        elif animation_type == 'zoom':
            # 🔍 ثابت في الموضع المختار مع تأثير التكبير
            filter_complex = f"{opacity_filter};[0:v][logo]overlay={overlay_x}:{overlay_y}"
            logger.info(f"🔍 تطبيق حركة التكبير في الموضع: {position}")
            
        else:
            # افتراضي - ثابت في الموضع المحدد
            filter_complex = f"{opacity_filter};[0:v][logo]overlay={overlay_x}:{overlay_y}"
            logger.info(f"⚪ تطبيق حركة افتراضية في الموضع: {position}")
        
        # الأمر مع تحسينات الأداء
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-i', logo_path,
            '-filter_complex', filter_complex,
            '-c:a', 'copy',  # نسخ الصوت بدون إعادة ترميز
            '-c:v', 'libx264',
            '-preset', 'ultrafast',  # أسرع preset
            '-crf', '28',  # جودة معقولة مع حجم أصغر
            '-threads', '2',  # تحديد عدد الخيوط لتقليل استهلاك CPU
            '-movflags', '+faststart',
            '-shortest',
            output_path
        ]

        logger.info(f"🔄 تنفيذ FFmpeg ({animation_type} في الموضع {position})")

        # تشغيل FFmpeg مع أولوية منخفضة لتقليل استهلاك CPU
        try:
            import psutil
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.getcwd()
            )

            # تقليل أولوية العملية
            try:
                p = psutil.Process(process.pid)
                p.nice(10)  # أولوية منخفضة (0-19، 19 الأدنى)
            except Exception:
                pass

            # الانتظار حتى الانتهاء
            stdout, stderr = process.communicate(timeout=300)
            result = type('obj', (object,), {
                'returncode': process.returncode,
                'stdout': stdout,
                'stderr': stderr
            })()

        except ImportError:
            # إذا لم يكن psutil متاحاً، استخدم subprocess العادي
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=os.getcwd()
            )
        
        if result.returncode != 0:
            logger.error(f"❌ FFmpeg فشل ({animation_type})")
            logger.error(f"  stderr: {result.stderr[:300]}")
            return input_path
        
        if not os.path.exists(output_path):
            logger.error("❌ ملف الناتج غير موجود")
            return input_path
        
        file_size = os.path.getsize(output_path)
        if file_size < 1000:
            logger.error("❌ ملف الناتج فارغ")
            return input_path
        
        logger.info(f"✨ نجح اللوجو ({animation_type} في {position})! {file_size/1024/1024:.2f}MB")
        return output_path
        
    except subprocess.TimeoutExpired:
        logger.error("❌ FFmpeg انتهت مهلته")
        return input_path
    except Exception as e:
        logger.error(f"❌ خطأ في اللوجو ({animation_type}): {e}")
        return input_path

def apply_animated_watermark(input_path, output_path, logo_path, size=None):
    """
    دالة رئيسية محدثة لإضافة اللوجو المتحرك - إصلاح FFmpeg
    """
    logger.info(f"🎨 بدء معالجة اللوجو...")
    logger.info(f"  - input_path: {input_path}")
    logger.info(f"  - output_path: {output_path}")
    logger.info(f"  - logo_path: {logo_path}")
    logger.info(f"  - size: {size}")
    
    if not os.path.exists(logo_path):
        logger.error(f"❌ مسار اللوجو غير صحيح: {logo_path}")
        return input_path

    if not os.path.exists(input_path):
        logger.error(f"❌ مسار الفيديو المدخل غير صحيح: {input_path}")
        return input_path

    try:
        logger.info(f"✨ بدء إضافة اللوجو المتحرك: {input_path}")
        
        # جلب جميع الإعدادات من قاعدة البيانات
        try:
            from database import get_all_logo_settings
            settings = get_all_logo_settings()
            
            animation_type = settings.get('animation', 'corner_rotation')
            position = settings.get('position', 'top_right')
            size_px = settings.get('size_pixels', 150) if size is None else size
            opacity = settings.get('opacity_decimal', 0.7)
            
            logger.info(f"⚙️ إعدادات اللوجو: {animation_type}, {position}, {size_px}px, {int(opacity*100)}%")
            
        except Exception as db_error:
            logger.warning(f"⚠️ فشل قراءة إعدادات قاعدة البيانات: {db_error}")
            # استخدام إعدادات افتراضية
            animation_type = 'corner_rotation'
            position = 'top_right'
            size_px = 150 if size is None else size
            opacity = 0.7
            logger.info(f"⚙️ استخدام إعدادات افتراضية: {animation_type}, {position}, {size_px}px, {int(opacity*100)}%")
        
        # استخدام الدالة المبسطة الجديدة مع الإصلاح
        result_path = apply_simple_watermark(input_path, output_path, logo_path, animation_type, size_px, position, opacity)
        
        if result_path != input_path:
            logger.info(f"✨ تم تطبيق اللوجو بنجاح!")
            return result_path
        else:
            logger.warning(f"⚠️ فشل اللوجو المتحرك، محاولة اللوجو الثابت...")
            return apply_watermark(input_path, output_path, logo_path, position, size)
        
    except Exception as e:
        logger.error(f"❌ خطأ عام في اللوجو المتحرك: {str(e)}")
        logger.error(f"تفاصيل الخطأ: {str(e)}")
        return apply_watermark(input_path, output_path, logo_path, position, size)

def apply_watermark(input_path, output_path, logo_path, position='center', size=150):
    """
    يطبق لوجو ثابت على الفيديو (احتياطي)
    """
    if not os.path.exists(logo_path):
        logger.error(f"❌ مسار اللوجو غير صحيح: {logo_path}")
        return input_path

    if not os.path.exists(input_path):
        logger.error(f"❌ مسار الفيديو المدخل غير صحيح: {input_path}")
        return input_path

    try:
        logger.info(f"🎨 إضافة لوجو ثابت: {input_path}")
        
        # التأكد من أن size قيمة صحيحة
        if size is None or not isinstance(size, (int, float)):
            size = 150
            logger.warning(f"⚠️ تم تعيين حجم افتراضي: {size}")
        
        size = int(size)
        
        # جميع المواضع المتاحة
        positions = {
            'top_left': '10:10',
            'top_right': f'W-w-10:10',
            'bottom_left': f'10:H-h-10',
            'bottom_right': f'W-w-10:H-h-10',
            'center': f'(W-w)/2:(H-h)/2',
            'center_right': f'W-w-10:(H-h)/2',
            'center_left': f'10:(H-h)/2',
            'top_center': f'(W-w)/2:10',
            'bottom_center': f'(W-w)/2:H-h-10'
        }
        
        pos = positions.get(position, positions['center'])
        
        cmd = [
            'ffmpeg',
            '-y',
            '-i', input_path,
            '-i', logo_path,
            '-filter_complex',
            f'[1:v]scale={size}:-1[logo];[0:v][logo]overlay={pos}',
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-movflags', '+faststart',
            '-shortest',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size > 1000:
                logger.info(f"✅ نجح اللوجو الثابت ({file_size/1024/1024:.2f}MB)")
                return output_path
        
        logger.error(f"❌ فشل اللوجو الثابت")
        if result.stderr:
            logger.error(f"تفاصيل الخطأ: {result.stderr[:500]}")
        return input_path
        
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return input_path

async def setup_bot_menu(bot):
    """يقوم بإعداد قائمة الأوامر (Menu) للبوت"""
    logger.info("📋 إعداد قائمة أوامر البوت...")
    
    if not MESSAGES:
        load_messages()
    
    user_commands_ar = [
        BotCommand("start", get_message('ar', 'start_command_desc')),
        BotCommand("account", get_message('ar', 'account_command_desc')),
        BotCommand("help", get_message('ar', 'help_command_desc')),
    ]
    
    user_commands_en = [
        BotCommand("start", get_message('en', 'start_command_desc')),
        BotCommand("account", get_message('en', 'account_command_desc')),
        BotCommand("help", get_message('en', 'help_command_desc')),
    ]

    admin_commands_ar = user_commands_ar + [
        BotCommand("admin", get_message('ar', 'admin_command_desc')),
    ]
    
    admin_commands_en = user_commands_en + [
        BotCommand("admin", get_message('en', 'admin_command_desc')),
    ]

    await bot.set_my_commands(user_commands_ar)
    logger.info("✅ تم تعيين قائمة الأوامر العامة.")
    
    admin_ids_str = os.getenv("ADMIN_ID", "")
    admin_ids = [int(admin_id) for admin_id in admin_ids_str.split(',') if admin_id.strip()]
    
    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(admin_commands_ar, scope=BotCommandScopeChat(chat_id=admin_id))
            logger.info(f"✅ تم تعيين قائمة أوامر خاصة للمدير ID: {admin_id}")
        except Exception as e:
            logger.error(f"❌ فشل تعيين أوامر للمدير {admin_id}: {e}")

def format_file_size(size_bytes):
    """تحويل حجم الملف من bytes إلى صيغة قابلة للقراءة"""
    if not size_bytes:
        return "غير معروف"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def format_duration(seconds):
    """تحويل المدة من ثواني إلى صيغة قابلة للقراءة (HH:MM:SS)"""
    if not seconds:
        return "00:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def escape_markdown(text: str) -> str:
    """يقوم بتهريب الأحرف الخاصة في MarkdownV2"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def clean_filename(filename):
    """تنظيف اسم الملف من الأحرف غير الصالحة"""
    # إزالة الأحرف غير الصالحة
    import re
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # تحديد طول أقصى
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    return filename

# ==================== التحقق من صحة المدخلات ====================

def validate_url(url: str) -> bool:
    """
    التحقق من صحة الرابط

    Args:
        url: الرابط المراد التحقق منه

    Returns:
        bool: True إذا كان الرابط صحيحاً
    """
    import re

    # نمط بسيط للتحقق من الروابط
    url_pattern = re.compile(
        r'^https?://'  # http:// أو https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # منفذ اختياري
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return bool(url_pattern.match(url))

def validate_user_id(user_id_str: str) -> tuple:
    """
    التحقق من صحة معرف المستخدم

    Args:
        user_id_str: معرف المستخدم كنص

    Returns:
        tuple: (is_valid: bool, user_id: int or None, error_msg: str or None)
    """
    # محاولة التحويل إلى رقم
    try:
        user_id = int(user_id_str.strip())

        # معرفات تيليجرام موجبة
        if user_id <= 0:
            return False, None, "معرف المستخدم يجب أن يكون رقماً موجباً"

        # معرفات تيليجرام عادة أقل من 10 مليارات
        if user_id > 10_000_000_000:
            return False, None, "معرف المستخدم غير صحيح"

        return True, user_id, None

    except ValueError:
        return False, None, "معرف المستخدم يجب أن يكون رقماً صحيحاً"

def validate_days(days_str: str) -> tuple:
    """
    التحقق من صحة عدد الأيام

    Args:
        days_str: عدد الأيام كنص

    Returns:
        tuple: (is_valid: bool, days: int or None, error_msg: str or None)
    """
    try:
        days = int(days_str.strip())

        if days <= 0:
            return False, None, "عدد الأيام يجب أن يكون موجباً"

        if days > 3650:  # 10 سنوات كحد أقصى
            return False, None, "عدد الأيام كبير جداً (الحد الأقصى 3650 يوم)"

        return True, days, None

    except ValueError:
        return False, None, "عدد الأيام يجب أن يكون رقماً صحيحاً"

# ==================== تحديد معدل الطلبات (Rate Limiting) ====================

# قاموس لتتبع آخر طلب لكل مستخدم
_user_last_request = {}
_RATE_LIMIT_SECONDS = 10  # 10 ثواني بين كل طلب

def rate_limit(seconds: int = None):
    """
    ديكوراتور لتحديد معدل الطلبات - يمنع المستخدم من إرسال طلبات متكررة

    Args:
        seconds: عدد الثواني المطلوبة بين كل طلب (افتراضي: 10 ثواني)

    Usage:
        @rate_limit(seconds=10)
        async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # download code here
    """
    from functools import wraps
    from time import time

    limit = seconds if seconds is not None else _RATE_LIMIT_SECONDS

    def decorator(func):
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            current_time = time()

            # التحقق من آخر طلب للمستخدم
            last_request = _user_last_request.get(user_id, 0)
            time_passed = current_time - last_request

            if time_passed < limit:
                remaining = int(limit - time_passed)

                # الحصول على لغة المستخدم
                user_lang = 'ar'
                try:
                    from database import get_user_language
                    user_lang = get_user_language(user_id)
                except:
                    pass

                if user_lang == 'ar':
                    error_msg = f"⏱️ الرجاء الانتظار {remaining} ثانية قبل إرسال طلب جديد."
                else:
                    error_msg = f"⏱️ Please wait {remaining} seconds before sending a new request."

                await update.message.reply_text(error_msg)
                return None

            # تحديث وقت آخر طلب
            _user_last_request[user_id] = current_time

            # تنفيذ الأمر
            return await func(update, context, *args, **kwargs)

        return wrapper
    return decorator

# ==================== تخزين مؤقت لبيانات المستخدم ====================

from functools import lru_cache
from time import time

# Cache لبيانات المستخدم (يتم تحديثه كل 60 ثانية)
_user_cache = {}
_user_cache_ttl = 60  # ثانية
_cache_lock = threading.Lock()

def get_cached_user_data(user_id: int, fetch_func):
    """
    الحصول على بيانات المستخدم من الذاكرة المؤقتة أو جلبها من قاعدة البيانات

    Args:
        user_id: معرف المستخدم
        fetch_func: دالة لجلب البيانات من قاعدة البيانات

    Returns:
        بيانات المستخدم
    """
    current_time = time()

    with _cache_lock:
        # التحقق من وجود البيانات في الذاكرة المؤقتة
        if user_id in _user_cache:
            cached_data, timestamp = _user_cache[user_id]

            # إذا كانت البيانات لا تزال صالحة
            if current_time - timestamp < _user_cache_ttl:
                return cached_data

        # جلب البيانات من قاعدة البيانات
        user_data = fetch_func(user_id)

        # تخزين في الذاكرة المؤقتة
        _user_cache[user_id] = (user_data, current_time)

        return user_data

def clear_user_cache(user_id: int = None):
    """
    مسح الذاكرة المؤقتة لمستخدم معين أو جميع المستخدمين

    Args:
        user_id: معرف المستخدم (اختياري - إذا لم يُحدد، سيتم مسح الجميع)
    """
    with _cache_lock:
        if user_id:
            _user_cache.pop(user_id, None)
        else:
            _user_cache.clear()

# ==================== حماية الأوامر الإدارية ====================

def admin_only(func):
    """
    ديكوراتور للتحقق من صلاحيات الإدارة قبل تنفيذ الأوامر الإدارية

    Usage:
        @admin_only
        async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # admin code here
    """
    from functools import wraps

    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        # الحصول على معرف المستخدم
        user_id = update.effective_user.id

        # التحقق من صلاحيات الإدارة
        from database import is_admin

        if not is_admin(user_id):
            # رسالة رفض الوصول
            user_lang = 'ar'  # افتراضياً العربية
            try:
                from database import get_user_language
                user_lang = get_user_language(user_id)
            except:
                pass

            if user_lang == 'ar':
                error_msg = "⛔ عذراً، هذا الأمر متاح للمشرفين فقط."
            else:
                error_msg = "⛔ Sorry, this command is only available for administrators."

            await update.message.reply_text(error_msg)

            # سجل محاولة الوصول غير المصرح بها
            username = update.effective_user.username or update.effective_user.first_name
            logger.warning(f"⚠️ محاولة وصول غير مصرح: المستخدم {username} ({user_id}) حاول تنفيذ {func.__name__}")

            return None

        # تنفيذ الأمر إذا كان المستخدم admin
        return await func(update, context, *args, **kwargs)

    return wrapper

# ==================== نظام السجلات الاحترافي ====================

import threading
from datetime import datetime

# عداد الأخطاء في الذاكرة
_error_counter = {
    'critical': 0,
    'warning': 0,
    'last_reset': datetime.now()
}
_error_lock = threading.Lock()

def _increment_error_count(error_type: str):
    """زيادة عداد الأخطاء بشكل آمن"""
    with _error_lock:
        _error_counter[error_type] = _error_counter.get(error_type, 0) + 1

def get_error_stats() -> dict:
    """الحصول على إحصائيات الأخطاء"""
    with _error_lock:
        return _error_counter.copy()

def reset_error_stats():
    """إعادة تعيين إحصائيات الأخطاء"""
    with _error_lock:
        _error_counter['critical'] = 0
        _error_counter['warning'] = 0
        _error_counter['last_reset'] = datetime.now()

def _write_to_error_log(level: str, message: str, module: str):
    """كتابة الخطأ إلى ملف السجل المحلي"""
    try:
        log_file = 'bot_errors.log'
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] [{module}] {message}\n"

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Failed to write to error log: {e}")

def log_warning(message: str, module: str = "unknown"):
    """
    تسجيل تحذير محلي بدون إرسال إلى تيليجرام

    Args:
        message: رسالة التحذير
        module: اسم الوحدة/الملف
    """
    # تسجيل في السجل المحلي
    logger.warning(f"[{module}] {message}")

    # كتابة إلى ملف السجل
    _write_to_error_log("WARNING", message, module)

    # زيادة العداد
    _increment_error_count('warning')

def _send_telegram_message(chat_id: str, text: str, parse_mode: str = "Markdown"):
    """إرسال رسالة إلى تيليجرام باستخدام requests"""
    import requests

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token or not chat_id:
        return False

    try:
        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        response = requests.post(
            api_url,
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False
            },
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ فشل إرسال رسالة تيليجرام: {e}")
        return False

def _send_telegram_video(chat_id: str, video_path: str, caption: str):
    """إرسال فيديو إلى تيليجرام مع تعليق"""
    import requests

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token or not chat_id or not video_path:
        return False

    try:
        api_url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "Markdown"
        }

        # إذا كان الفيديو رابط URL
        if video_path.startswith("http"):
            data["video"] = video_path
            response = requests.post(api_url, data=data, timeout=20)
        else:
            # إذا كان الفيديو ملف محلي
            if not os.path.exists(video_path):
                logger.error(f"❌ ملف الفيديو غير موجود: {video_path}")
                return False

            with open(video_path, "rb") as video_file:
                files = {"video": video_file}
                response = requests.post(api_url, data=data, files=files, timeout=30)

        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ فشل إرسال فيديو تيليجرام: {e}")
        return False

def send_critical_log(message: str, module: str = "غير محدد"):
    """
    إرسال خطأ جسيم إلى قناة السجلات + إشعار الأدمن بتنسيق احترافي.
    استخدم هذه الدالة فقط للأخطاء الحرجة (فشل قاعدة البيانات، أعطال النظام، إلخ)

    Args:
        message: رسالة الخطأ
        module: اسم الوحدة/الملف الذي حدث فيه الخطأ

    Returns:
        bool: True إذا تم الإرسال بنجاح
    """
    from datetime import datetime

    # كتابة إلى ملف السجل المحلي
    _write_to_error_log("CRITICAL", message, module)

    # زيادة عداد الأخطاء الحرجة
    _increment_error_count('critical')

    log_channel_id = os.getenv("LOG_CHANNEL_ID")
    if not log_channel_id:
        logger.warning("⚠️ LOG_CHANNEL_ID غير محدد، لن يتم إرسال السجلات")
        return False

    # تنسيق الوقت بشكل جميل
    timestamp = datetime.utcnow().strftime("%H:%M — %d-%m-%Y")

    # بناء الرسالة بتنسيق احترافي محسّن
    text = (
        "🔥 *خطأ جسيم في النظام*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📁 *الوحدة:* `{module}`\n"
        f"🧩 *السبب:* خطأ غير متوقع\n"
        f"💬 *التفاصيل:* {message}\n"
        f"🕒 *الوقت:* {timestamp}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🚨 *تم إشعار الأدمن تلقائياً.*"
    )

    # إرسال إلى قناة السجلات
    success = _send_telegram_message(log_channel_id, text)

    # إشعار الأدمن
    admin_id = os.getenv("ADMIN_ID", "").split(',')[0].strip()
    if admin_id:
        admin_text = f"🚨 *تنبيه إداري عاجل:*\n\n{text}"
        _send_telegram_message(admin_id, admin_text)

    return success

def send_video_report(user_id: int, username: str, url: str, title: str,
                     size: str = "", video_path: str = None):
    """
    إرسال تقرير تحميل فيديو جديد إلى قناة الفيديوهات مع الفيديو نفسه بتنسيق احترافي.

    Args:
        user_id: معرف المستخدم في تيليجرام
        username: اسم المستخدم
        url: رابط الفيديو الأصلي
        title: عنوان الفيديو
        size: حجم الفيديو (اختياري)
        video_path: مسار الفيديو المحلي أو رابط URL (اختياري)

    Returns:
        bool: True إذا تم الإرسال بنجاح
    """
    from datetime import datetime

    log_channel_videos = os.getenv("LOG_CHANNEL_ID_VIDEOS")
    if not log_channel_videos:
        logger.warning("⚠️ LOG_CHANNEL_ID_VIDEOS غير محدد، لن يتم إرسال التقارير")
        return False

    # تنسيق الوقت
    timestamp = datetime.utcnow().strftime("%H:%M — %d-%m-%Y")

    # معالجة اسم المستخدم
    username_display = f"@{username}" if username else "بدون اسم مستخدم"

    # معالجة العنوان لتجنب مشاكل Markdown
    title_escaped = title.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

    # بناء الرسالة
    text = (
        "🎬 *تقرير تحميل فيديو جديد*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 *المستخدم:* {username_display} (`{user_id}`)\n"
        f"🔗 *الرابط:* [اضغط هنا لفتح الفيديو]({url})\n"
        f"🏷️ *العنوان:* {title_escaped}\n"
    )

    if size:
        text += f"📦 *الحجم:* {size}\n"

    text += f"🕒 *الوقت:* {timestamp}\n"
    text += "━━━━━━━━━━━━━━━━━━"

    # إرسال الفيديو مع التقرير أو التقرير فقط
    if video_path:
        text += "\n🎥 *الفيديو مرفق أدناه مباشرة*"
        success = _send_telegram_video(log_channel_videos, video_path, text)
    else:
        success = _send_telegram_message(log_channel_videos, text)

    return success


# ═══════════════════════════════════════════════════════════════
#  Mission 10: Daily Download Reports
# ═══════════════════════════════════════════════════════════════

async def send_daily_report(context):
    """
    إرسال تقرير يومي بإحصائيات التحميلات إلى LOG_CHANNEL_ID
    يتم استدعاؤها تلقائياً عبر job queue
    """
    from database import generate_daily_report

    log_channel_id = os.getenv("LOG_CHANNEL_ID")
    if not log_channel_id:
        logger.warning("⚠️ LOG_CHANNEL_ID غير محدد، لن يتم إرسال التقرير اليومي")
        return

    # توليد التقرير
    report = generate_daily_report()

    # إرسال التقرير
    try:
        await context.bot.send_message(
            chat_id=log_channel_id,
            text=report,
            parse_mode='Markdown'
        )
        logger.info("✅ تم إرسال التقرير اليومي بنجاح")
    except Exception as e:
        logger.error(f"❌ فشل إرسال التقرير اليومي: {e}")


def setup_daily_report_job(application):
    """
    إعداد مهمة إرسال التقرير اليومي
    يتم استدعاؤها من bot.py عند بدء التشغيل

    Args:
        application: كائن Application من python-telegram-bot
    """
    from datetime import time

    # إرسال التقرير يومياً في الساعة 23:59 بتوقيت UTC
    job_queue = application.job_queue

    if job_queue:
        job_queue.run_daily(
            send_daily_report,
            time=time(hour=23, minute=59, second=0),
            name='daily_download_report'
        )
        logger.info("✅ تم جدولة التقرير اليومي للساعة 23:59 UTC")
    else:
        logger.warning("⚠️ job_queue غير متاح، لن يتم جدولة التقرير اليومي")