#!/usr/bin/env python3
"""
دوال التنسيق والعرض
Formatting utilities for displaying data
"""

import os
import re
from config.logger import get_logger

logger = get_logger(__name__)


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
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # تحديد طول أقصى
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    return filename
