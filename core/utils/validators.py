#!/usr/bin/env python3
"""
دوال التحقق والتأكد من صحة المدخلات
Validation utilities for user inputs
"""

import re
from config.logger import get_logger

logger = get_logger(__name__)


def validate_url(url: str) -> bool:
    """
    التحقق من صحة الرابط

    Args:
        url: الرابط المراد التحقق منه

    Returns:
        bool: True إذا كان الرابط صحيحاً
    """
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
