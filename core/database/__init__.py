"""
Database Module - نظام قاعدة البيانات
يوفر جميع الدوال للتعامل مع قاعدة البيانات MongoDB
"""

# Base - الاتصال والإعدادات الأساسية
from .base import (
    MONGODB_URI,
    ADMIN_IDS,
    client,
    db,
    users_collection,
    settings_collection,
    init_db,
    ensure_db_connection
)

# Users - إدارة المستخدمين
from .users import (
    is_admin,
    add_user,
    get_user,
    get_all_users,
    update_user_language,
    get_user_language,
    update_user_interaction,
    delete_user,
    get_user_stats,
    get_users_count
)

# Subscriptions - إدارة الاشتراكات
from .subscriptions import (
    is_subscribed,
    add_subscription,
    remove_subscription,
    get_global_settings,
    set_subscription_enabled,
    set_welcome_broadcast_enabled,
    is_subscription_enabled,
    is_welcome_broadcast_enabled,
    set_subscription_price,
    get_subscription_price
)

# Downloads - إدارة التحميلات
from .downloads import (
    increment_download_count,
    get_daily_download_count,
    get_total_downloads_count,
    reset_daily_downloads,
    track_download,
    get_user_downloads,
    get_download_stats,
    get_daily_download_stats,
    generate_daily_report,
    track_download_success,
    get_download_success_rate,
    get_user_download_stats,
    downloads_collection
)

# Logos - إدارة اللوجو
from .logos import (
    set_logo_status,
    is_logo_enabled,
    set_logo_animation,
    get_logo_animation,
    set_logo_position,
    get_logo_position,
    set_logo_size,
    get_logo_size,
    set_logo_opacity,
    get_logo_opacity,
    get_all_logo_settings,
    set_logo_target,
    get_logo_target
)

# Libraries - إدارة المكتبات والمنصات
from .libraries import (
    init_library_settings,
    get_library_settings,
    update_library_setting,
    toggle_platform,
    is_platform_allowed,
    get_allowed_platforms,
    add_admin_approval_request,
    get_pending_approvals,
    approve_platform_request,
    deny_platform_request,
    update_library_status,
    get_library_status,
    record_download_attempt,
    get_performance_metrics,
    reset_performance_metrics
)

# Referrals - نظام الإحالة
from .referrals import (
    generate_referral_code,
    track_referral,
    add_referral_points,
    use_no_logo_credit,
    get_referral_stats,
    get_no_logo_credits
)

# Errors - نظام بلاغات الأخطاء
from .errors import (
    create_error_report,
    get_pending_error_reports,
    get_all_error_reports,
    resolve_error_report,
    get_error_report_by_id,
    delete_error_report,
    get_error_stats,
    error_reports_collection
)

# Settings - الإعدادات العامة (الصوتيات والقيود)
from .settings import (
    get_audio_settings,
    set_audio_enabled,
    set_audio_limit_minutes,
    is_audio_enabled,
    get_audio_limit_minutes,
    get_general_limits,
    set_free_time_limit,
    get_free_time_limit,
    set_daily_download_limit,
    get_daily_download_limit_setting
)

__all__ = [
    # Base
    'MONGODB_URI',
    'ADMIN_IDS',
    'client',
    'db',
    'users_collection',
    'settings_collection',
    'init_db',
    'ensure_db_connection',

    # Users
    'is_admin',
    'add_user',
    'get_user',
    'get_all_users',
    'update_user_language',
    'get_user_language',
    'update_user_interaction',
    'delete_user',
    'get_user_stats',
    'get_users_count',

    # Subscriptions
    'is_subscribed',
    'add_subscription',
    'remove_subscription',
    'get_global_settings',
    'set_subscription_enabled',
    'set_welcome_broadcast_enabled',
    'is_subscription_enabled',
    'is_welcome_broadcast_enabled',
    'set_subscription_price',
    'get_subscription_price',

    # Downloads
    'increment_download_count',
    'get_daily_download_count',
    'get_total_downloads_count',
    'reset_daily_downloads',
    'track_download',
    'get_user_downloads',
    'get_download_stats',
    'get_daily_download_stats',
    'generate_daily_report',
    'track_download_success',
    'get_download_success_rate',
    'get_user_download_stats',
    'downloads_collection',

    # Logos
    'set_logo_status',
    'is_logo_enabled',
    'set_logo_animation',
    'get_logo_animation',
    'set_logo_position',
    'get_logo_position',
    'set_logo_size',
    'get_logo_size',
    'set_logo_opacity',
    'get_logo_opacity',
    'get_all_logo_settings',
    'set_logo_target',
    'get_logo_target',

    # Libraries
    'init_library_settings',
    'get_library_settings',
    'update_library_setting',
    'toggle_platform',
    'is_platform_allowed',
    'get_allowed_platforms',
    'add_admin_approval_request',
    'get_pending_approvals',
    'approve_platform_request',
    'deny_platform_request',
    'update_library_status',
    'get_library_status',
    'record_download_attempt',
    'get_performance_metrics',
    'reset_performance_metrics',

    # Referrals
    'generate_referral_code',
    'track_referral',
    'add_referral_points',
    'use_no_logo_credit',
    'get_referral_stats',
    'get_no_logo_credits',

    # Errors
    'create_error_report',
    'get_pending_error_reports',
    'get_all_error_reports',
    'resolve_error_report',
    'get_error_report_by_id',
    'delete_error_report',
    'get_error_stats',
    'error_reports_collection',

    # Settings
    'get_audio_settings',
    'set_audio_enabled',
    'set_audio_limit_minutes',
    'is_audio_enabled',
    'get_audio_limit_minutes',
    'get_general_limits',
    'set_free_time_limit',
    'get_free_time_limit',
    'set_daily_download_limit',
    'get_daily_download_limit_setting'
]
