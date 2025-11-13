from datetime import datetime
from .base import db

# استخدام logger من config
try:
    from config import logger
except ImportError:
    import logging
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)


def set_logo_status(enabled: bool):
    """تفعيل/إيقاف اللوجو للجميع"""
    try:
        # حفظ الحالة في مستند خاص بالإعدادات
        db.settings.update_one(
            {'_id': 'logo_settings'},
            {'$set': {'enabled': enabled, 'updated_at': datetime.now()}},
            upsert=True
        )
        logger.info(f"✅ تم {'تفعيل' if enabled else 'إيقاف'} اللوجو")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة اللوجو: {e}")
        return False


def is_logo_enabled() -> bool:
    """التحقق من حالة اللوجو"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings:
            return settings.get('enabled', True)
        return True  # افتراضياً مفعّل
    except Exception as e:
        logger.error(f"❌ فشل جلب حالة اللوجو: {e}")
        return True


# ==================== إدارة حركات اللوجو ====================

def set_logo_animation(animation_type: str):
    """تعيين نوع حركة اللوجو"""
    try:
        valid_types = ['static', 'corner_rotation', 'bounce', 'slide', 'fade', 'zoom']

        if animation_type not in valid_types:
            animation_type = 'static'  # افتراضي

        db.settings.update_one(
            {'_id': 'logo_settings'},
            {
                '$set': {
                    'animation_type': animation_type,
                    'updated_at': datetime.now()
                }
            },
            upsert=True
        )

        logger.info(f"✅ تم تعيين حركة اللوجو إلى: {animation_type}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تعيين حركة اللوجو: {e}")
        return False


def get_logo_animation() -> str:
    """جلب نوع حركة اللوجو الحالية"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings and 'animation_type' in settings:
            return settings['animation_type']
        return 'static'  # افتراضي
    except Exception as e:
        logger.error(f"❌ فشل جلب حركة اللوجو: {e}")
        return 'static'


# ==================== إعدادات اللوجو المتقدمة ====================

def set_logo_position(position: str):
    """تعيين موضع اللوجو"""
    try:
        valid_positions = [
            'top_right',      # زاوية يمين أعلى
            'top_left',       # زاوية يسار أعلى
            'bottom_right',   # زاوية يمين أسفل
            'bottom_left',    # زاوية يسار أسفل
            'center',         # وسط الشاشة
            'top_center',     # وسط أعلى
            'bottom_center',  # وسط أسفل
            'center_right',   # وسط يمين
            'center_left'     # وسط يسار
        ]

        if position not in valid_positions:
            position = 'top_right'  # افتراضي

        db.settings.update_one(
            {'_id': 'logo_settings'},
            {
                '$set': {
                    'position': position,
                    'updated_at': datetime.now()
                }
            },
            upsert=True
        )

        logger.info(f"✅ تم تعيين موضع اللوجو إلى: {position}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تعيين موضع اللوجو: {e}")
        return False


def get_logo_position() -> str:
    """جلب موضع اللوجو الحالي"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings and 'position' in settings:
            return settings['position']
        return 'top_right'  # افتراضي
    except Exception as e:
        logger.error(f"❌ فشل جلب موضع اللوجو: {e}")
        return 'top_right'


def set_logo_size(size: str):
    """تعيين حجم اللوجو"""
    try:
        valid_sizes = {
            'small': 100,   # صغير
            'medium': 150,  # متوسط
            'large': 200    # كبير
        }

        if size not in valid_sizes:
            size = 'medium'  # افتراضي

        db.settings.update_one(
            {'_id': 'logo_settings'},
            {
                '$set': {
                    'size': size,
                    'size_pixels': valid_sizes[size],
                    'updated_at': datetime.now()
                }
            },
            upsert=True
        )

        logger.info(f"✅ تم تعيين حجم اللوجو إلى: {size} ({valid_sizes[size]}px)")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تعيين حجم اللوجو: {e}")
        return False


def get_logo_size() -> tuple:
    """جلب حجم اللوجو الحالي (اسم، بكسل)"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings and 'size' in settings:
            return settings['size'], settings.get('size_pixels', 150)
        return 'medium', 150  # افتراضي
    except Exception as e:
        logger.error(f"❌ فشل جلب حجم اللوجو: {e}")
        return 'medium', 150


def set_logo_opacity(opacity: int):
    """تعيين شفافية اللوجو (40-90)"""
    try:
        # التحقق من القيمة
        if opacity < 40:
            opacity = 40
        elif opacity > 90:
            opacity = 90

        db.settings.update_one(
            {'_id': 'logo_settings'},
            {
                '$set': {
                    'opacity': opacity,
                    'opacity_decimal': opacity / 100.0,
                    'updated_at': datetime.now()
                }
            },
            upsert=True
        )

        logger.info(f"✅ تم تعيين شفافية اللوجو إلى: {opacity}%")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تعيين شفافية اللوجو: {e}")
        return False


def get_logo_opacity() -> tuple:
    """جلب شفافية اللوجو الحالية (نسبة، عشري)"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings and 'opacity' in settings:
            return settings['opacity'], settings.get('opacity_decimal', 0.7)
        return 70, 0.7  # افتراضي
    except Exception as e:
        logger.error(f"❌ فشل جلب شفافية اللوجو: {e}")
        return 70, 0.7


def get_all_logo_settings() -> dict:
    """جلب جميع إعدادات اللوجو"""
    try:
        animation = get_logo_animation()
        position = get_logo_position()
        size_name, size_px = get_logo_size()
        opacity_pct, opacity_dec = get_logo_opacity()
        target_id, target_name = get_logo_target()

        return {
            'animation': animation,
            'position': position,
            'size_name': size_name,
            'size_pixels': size_px,
            'opacity_percent': opacity_pct,
            'opacity_decimal': opacity_dec,
            'target_id': target_id,
            'target_name': target_name
        }
    except Exception as e:
        logger.error(f"❌ فشل جلب إعدادات اللوجو: {e}")
        return {
            'animation': 'corner_rotation',
            'position': 'top_right',
            'size_name': 'medium',
            'size_pixels': 150,
            'opacity_percent': 70,
            'opacity_decimal': 0.7,
            'target_id': 'free_only',
            'target_name': 'المستخدمون العاديون فقط'
        }


# ====================================
# إعدادات الفئة المستهدفة للوجو
# ====================================

def set_logo_target(target: str):
    """
    تعيين الفئة المستهدفة لتطبيق اللوجو

    Args:
        target: خيارات شاملة تشمل جميع أنواع المستخدمين
    """
    try:
        # قائمة شاملة بجميع الخيارات المتاحة
        valid_targets = [
            'free_with_points',    # العاديون (مع النقاط)
            'free_no_points',      # العاديون (بدون النقاط)
            'free_all',            # جميع العاديون
            'vip_with_points',     # VIP (مع النقاط)
            'vip_no_points',       # VIP (بدون النقاط)
            'vip_all',             # جميع VIP
            'everyone_with_points', # الجميع (مع النقاط)
            'everyone_no_points',  # الجميع (بدون النقاط)
            'everyone_all',        # الجميع (الجميع)
            'no_credits_only',     # المستخدمون بدون نقاط فقط
            'everyone_except_no_credits'  # الجميع عدا من لديهم نقاط
        ]

        if target not in valid_targets:
            logger.warning(f"⚠️ فئة مستهدفة غير صحيحة: {target}, استخدام free_all")
            target = 'free_all'

        db.settings.update_one(
            {'_id': 'logo_settings'},
            {'$set': {'target': target}},
            upsert=True
        )

        target_names = {
            'free_with_points': 'العاديون - يظهر للجميع (لا يهم النقاط)',
            'free_no_points': 'العاديون - فقط من ليس لديهم نقاط',
            'free_all': 'جميع العاديون',
            'vip_with_points': 'VIP - يظهر للجميع (لا يهم النقاط)',
            'vip_no_points': 'VIP - فقط من ليس لديهم نقاط',
            'vip_all': 'جميع VIP',
            'everyone_with_points': 'الجميع - يظهر للجميع (لا يهم النقاط)',
            'everyone_no_points': 'الجميع - فقط من ليس لديهم نقاط',
            'everyone_all': 'الجميع',
            'no_credits_only': 'المستخدمون بدون نقاط فقط',
            'everyone_except_no_credits': 'الجميع عدا من لديهم نقاط'
        }
        logger.info(f"✅ تم تعيين الفئة المستهدفة للوجو إلى: {target_names[target]}")
    except Exception as e:
        logger.error(f"❌ فشل تعيين الفئة المستهدفة: {e}")


def get_logo_target() -> tuple:
    """
    جلب الفئة المستهدفة الحالية لتطبيق اللوجو

    Returns:
        tuple: (target_id, target_name_ar)
    """
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        target = settings.get('target', 'free_all') if settings else 'free_all'

        # التحقق من صحة الخيار، إذا لم يكن صحيحاً استخدم القيمة الافتراضية
        valid_targets = [
            'free_with_points', 'free_no_points', 'free_all',
            'vip_with_points', 'vip_no_points', 'vip_all',
            'everyone_with_points', 'everyone_no_points', 'everyone_all',
            'no_credits_only', 'everyone_except_no_credits'
        ]

        if target not in valid_targets:
            target = 'free_all'

        target_names = {
            'free_with_points': 'العاديون - يظهر للجميع (لا يهم النقاط)',
            'free_no_points': 'العاديون - فقط من ليس لديهم نقاط',
            'free_all': 'جميع العاديون',
            'vip_with_points': 'VIP - يظهر للجميع (لا يهم النقاط)',
            'vip_no_points': 'VIP - فقط من ليس لديهم نقاط',
            'vip_all': 'جميع VIP',
            'everyone_with_points': 'الجميع - يظهر للجميع (لا يهم النقاط)',
            'everyone_no_points': 'الجميع - فقط من ليس لديهم نقاط',
            'everyone_all': 'الجميع',
            'no_credits_only': 'المستخدمون بدون نقاط فقط',
            'everyone_except_no_credits': 'الجميع عدا من لديهم نقاط'
        }

        return target, target_names.get(target, 'جميع العاديون')
    except Exception as e:
        logger.error(f"❌ فشل جلب الفئة المستهدفة: {e}")
        return 'free_only', 'المستخدمون العاديون فقط'
