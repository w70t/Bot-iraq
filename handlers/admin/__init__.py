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

# استيراد الدوال الأساسية من admin.py
try:
    from .admin import (
        handle_admin_panel_callback,
        admin_back,
        admin_panel,
        admin_close
    )

    __all__.extend([
        'handle_admin_panel_callback',
        'admin_back',
        'admin_panel',
        'admin_close'
    ])
except ImportError as e:
    # إذا لم تكن بعض الدوال موجودة، نتجاهلها
    pass
