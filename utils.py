#!/usr/bin/env python3
"""
Compatibility Layer for utils.py
طبقة التوافق لملف utils.py - يستورد من الـ modules الجديدة

⚠️ هذا الملف موجود فقط للتوافق مع الكود القديم
    يرجى استخدام الاستيرادات المباشرة من core.utils و core.media
"""

# ==================== Import from config ====================
from config.messages import get_message
from config.settings import get_config
from config.logger import get_logger

# ==================== Import from core.utils ====================
from core.utils import (
    # Validators
    validate_url,
    validate_user_id,
    validate_days,

    # Formatters
    format_file_size,
    format_duration,
    escape_markdown,
    clean_filename,

    # Config & Messages
    load_messages,
    load_config,
    MESSAGES,
    CONFIG,

    # Bot Menu
    setup_bot_menu,

    # Rate Limiting
    rate_limit,

    # User Cache
    get_cached_user_data,
    clear_user_cache,

    # Admin Protection
    admin_only,

    # Logging System
    send_critical_log,
    send_video_report,
    log_warning,
    log_error_to_file,
    get_error_stats,
    reset_error_stats,

    # Daily Reports
    send_daily_report,
    setup_daily_report_job,

    # Cookie Management
    check_cookies_daily,
    check_cookies_weekly,
    backup_cookies_weekly,
    setup_cookie_check_job,

    # Error Tracking & Reports
    send_error_logs_to_admin,
    setup_error_tracking_job,

    # Cleanup
    cleanup_temp_files,
    cleanup_old_files,
)

# ==================== Import from core.media ====================
from core.media import (
    # Watermark
    get_logo_overlay_position,
    apply_simple_watermark,
    apply_animated_watermark,
    apply_watermark,
)

# ==================== Logger ====================
logger = get_logger(__name__)

# ==================== All Exports ====================
__all__ = [
    # Config
    'get_message',
    'get_config',
    'get_logger',

    # Validators
    'validate_url',
    'validate_user_id',
    'validate_days',

    # Formatters
    'format_file_size',
    'format_duration',
    'escape_markdown',
    'clean_filename',

    # Config & Messages
    'load_messages',
    'load_config',
    'MESSAGES',
    'CONFIG',

    # Bot Menu
    'setup_bot_menu',

    # Rate Limiting
    'rate_limit',

    # User Cache
    'get_cached_user_data',
    'clear_user_cache',

    # Admin Protection
    'admin_only',

    # Logging System
    'send_critical_log',
    'send_video_report',
    'log_warning',
    'log_error_to_file',
    'get_error_stats',
    'reset_error_stats',

    # Daily Reports
    'send_daily_report',
    'setup_daily_report_job',

    # Cookie Management
    'check_cookies_daily',
    'check_cookies_weekly',
    'backup_cookies_weekly',
    'setup_cookie_check_job',

    # Error Tracking & Reports
    'send_error_logs_to_admin',
    'setup_error_tracking_job',

    # Cleanup
    'cleanup_temp_files',
    'cleanup_old_files',

    # Watermark
    'get_logo_overlay_position',
    'apply_simple_watermark',
    'apply_animated_watermark',
    'apply_watermark',

    # Logger
    'logger',
]
