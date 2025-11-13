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

# استيراد جميع الدوال من admin.py
try:
    from .admin import (
        handle_admin_panel_callback,
        show_statistics,
        upgrade_user_start,
        manage_logo,
        show_vip_control_panel,
        show_general_limits_panel,
        show_audio_settings_panel,
        manage_libraries,
        show_cookie_management_panel,
        show_error_reports_panel,
        list_users,
        broadcast_start,
        admin_close,
        show_download_logs,
        handle_platform_toggle,
        handle_approval_action,
        admin_back,
        admin_panel,
        toggle_logo,
        show_animation_selector,
        set_animation_type,
        show_position_selector,
        set_position,
        show_size_selector,
        set_size,
        show_opacity_selector,
        set_opacity,
        library_details,
        library_stats,
        library_approvals,
        library_update,
        library_reset_stats,
        handle_sub_enable_confirm,
        handle_sub_disable_confirm,
        handle_sub_enable_yes,
        handle_sub_disable_yes,
        handle_sub_action_cancel,
        handle_sub_change_price,
        handle_sub_set_price,
        handle_sub_toggle_notif,
        handle_audio_enable,
        handle_audio_disable,
        handle_audio_preset,
        handle_audio_set_custom_limit,
        handle_resolve_report,
        handle_confirm_resolve,
        handle_edit_time_limit,
        handle_edit_daily_limit,
        handle_set_time_limit_preset,
        handle_set_time_limit_custom,
        show_cookie_status_detail,
        handle_cookie_test_all,
        handle_cookie_test_stories,
        show_cookie_encryption_info,
        handle_cookie_delete_all,
        handle_upload_cookie_button
    )

    __all__.extend([
        'handle_admin_panel_callback',
        'show_statistics',
        'upgrade_user_start',
        'manage_logo',
        'show_vip_control_panel',
        'show_general_limits_panel',
        'show_audio_settings_panel',
        'manage_libraries',
        'show_cookie_management_panel',
        'show_error_reports_panel',
        'list_users',
        'broadcast_start',
        'admin_close',
        'show_download_logs',
        'handle_platform_toggle',
        'handle_approval_action',
        'admin_back',
        'admin_panel',
        'toggle_logo',
        'show_animation_selector',
        'set_animation_type',
        'show_position_selector',
        'set_position',
        'show_size_selector',
        'set_size',
        'show_opacity_selector',
        'set_opacity',
        'library_details',
        'library_stats',
        'library_approvals',
        'library_update',
        'library_reset_stats',
        'handle_sub_enable_confirm',
        'handle_sub_disable_confirm',
        'handle_sub_enable_yes',
        'handle_sub_disable_yes',
        'handle_sub_action_cancel',
        'handle_sub_change_price',
        'handle_sub_set_price',
        'handle_sub_toggle_notif',
        'handle_audio_enable',
        'handle_audio_disable',
        'handle_audio_preset',
        'handle_audio_set_custom_limit',
        'handle_resolve_report',
        'handle_confirm_resolve',
        'handle_edit_time_limit',
        'handle_edit_daily_limit',
        'handle_set_time_limit_preset',
        'handle_set_time_limit_custom',
        'show_cookie_status_detail',
        'handle_cookie_test_all',
        'handle_cookie_test_stories',
        'show_cookie_encryption_info',
        'handle_cookie_delete_all',
        'handle_upload_cookie_button'
    ])
except ImportError as e:
    # إذا لم تكن بعض الدوال موجودة، نتجاهلها
    pass
