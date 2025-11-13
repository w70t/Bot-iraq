"""
Download handlers module - معالجات التحميل
"""
from .download import (
    handle_download,
    handle_quality_selection,
    cancel_download,
    cancel_download_callback,
    handle_batch_download,
    handle_playlist_download,
    handle_batch_quality_choice,
    toggle_video_selection,
    proceed_to_quality_selection,
    is_playlist_url
)
from .multi_download_handler import (
    handle_multi_download,
    show_mode_selection,
    show_quality_selection,
    show_audio_format_selection,
    download_videos,
    download_audio,
    handle_download_cancel
)
from .video_info import handle_video_message

__all__ = [
    # Single download
    'handle_download',
    'handle_quality_selection',
    'cancel_download',
    'cancel_download_callback',
    'handle_batch_download',
    'handle_playlist_download',
    'handle_batch_quality_choice',
    'toggle_video_selection',
    'proceed_to_quality_selection',
    'is_playlist_url',

    # Multi download
    'handle_multi_download',
    'show_mode_selection',
    'show_quality_selection',
    'show_audio_format_selection',
    'download_videos',
    'download_audio',
    'handle_download_cancel',

    # Video info
    'handle_video_message'
]
