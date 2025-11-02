#!/usr/bin/env python3
"""
ملف وظائف محدث مع إصلاح FFmpeg للصورة المتحركة
"""

import os
import subprocess
import logging
import re
from telegram import BotCommand, BotCommandScopeChat
from telegram.ext import Application
import json

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
    """يقوم بتحميل الإعدادات من ملف JSON"""
    global CONFIG
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
        logger.info("✅ تم تحميل ملف الإعدادات بنجاح.")
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
    دالة موحدة ومبسطة لإضافة اللوجو
    جميع الحركات تحترم الموضع المختار من المستخدم
    
    📍 **شرح المميزات:**
    • static: ثابت تماماً في الموضع المحدد (لا يتحرك)
    • المتحركات: تتحرك حول الموضع المحدد (وسط، تحت، إلخ)
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
        
        # الأمر
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-i', logo_path,
            '-filter_complex', filter_complex,
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '28',
            '-movflags', '+faststart',
            '-shortest',
            output_path
        ]
        
        logger.info(f"🔄 تنفيذ FFmpeg ({animation_type} في الموضع {position})")
        
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