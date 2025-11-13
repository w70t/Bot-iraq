#!/usr/bin/env python3
"""
Core Media Package
حزمة معالجة الوسائط
"""

# ==================== Watermark ====================
from .watermark import (
    get_logo_overlay_position,
    apply_simple_watermark,
    apply_animated_watermark,
    apply_watermark,
)

# ==================== Progress ====================
from .progress import (
    # سيتم إضافة دوال شريط التقدم عند الحاجة
)

__all__ = [
    # Watermark
    'get_logo_overlay_position',
    'apply_simple_watermark',
    'apply_animated_watermark',
    'apply_watermark',

    # Progress
    # سيتم إضافة دوال شريط التقدم عند الحاجة
]
