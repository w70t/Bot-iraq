#!/usr/bin/env python3
"""
Core Utilities Package
حزمة الأدوات الأساسية
"""

# ==================== Validators ====================
from .validators import (
    validate_url,
    validate_user_id,
    validate_days,
)

# ==================== Formatters ====================
from .formatters import (
    format_file_size,
    format_duration,
    escape_markdown,
    clean_filename,
)

# ==================== Helpers ====================
from .helpers import (
    # Config & Messages
    load_messages,
    load_config,
    get_message,
    get_config,
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
    check_cookies_weekly,
    backup_cookies_weekly,
    setup_cookie_check_job,

    # Cleanup
    cleanup_temp_files,
    cleanup_old_files,
)

__all__ = [
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
    'get_message',
    'get_config',
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
    'check_cookies_weekly',
    'backup_cookies_weekly',
    'setup_cookie_check_job',

    # Cleanup
    'cleanup_temp_files',
    'cleanup_old_files',
]
