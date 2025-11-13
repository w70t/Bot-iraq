"""
Admin handlers module - معالجات المشرفين
"""
from .admin import admin_conv_handler, admin_command_simple

# استيراد health_check إذا كان موجوداً
try:
    from .health_check import health_check_command, system_stats_command
    __all__ = [
        'admin_conv_handler',
        'admin_command_simple',
        'health_check_command',
        'system_stats_command'
    ]
except ImportError:
    __all__ = [
        'admin_conv_handler',
        'admin_command_simple'
    ]

# استيراد الدوال الإضافية من admin.py
try:
    from .admin import (
        handle_admin_panel_callback,
        show_statistics,
        handle_user_management,
        handle_broadcast_message,
        handle_settings_menu
    )
    __all__.extend([
        'handle_admin_panel_callback',
        'show_statistics',
        'handle_user_management',
        'handle_broadcast_message',
        'handle_settings_menu'
    ])
except ImportError as e:
    # إذا لم تكن الدالة موجودة، نتجاهلها
    pass
