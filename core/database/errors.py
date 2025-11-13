from datetime import datetime
from .base import db
from config.logger import get_logger

# إنشاء logger instance
logger = get_logger(__name__)

# إنشاء مجموعة البلاغات
try:
    error_reports_collection = db.error_reports if db is not None else None
except Exception as e:
    logger.error(f"❌ فشل إنشاء مجموعة البلاغات: {e}")
    error_reports_collection = None


# ═══════════════════════════════════════════════════════════════
#  Error Reporting System
# ═══════════════════════════════════════════════════════════════

def create_error_report(user_id: int, username: str, url: str, error_type: str, error_message: str):
    """
    إنشاء بلاغ خطأ جديد

    Args:
        user_id: معرف المستخدم
        username: اسم المستخدم
        url: رابط الفيديو الذي فشل
        error_type: نوع الخطأ (مثل: TimedOut, NetworkError, etc.)
        error_message: رسالة الخطأ التفصيلية
    """
    try:
        if error_reports_collection is None:
            logger.warning("⚠️ مجموعة البلاغات غير متاحة")
            return None

        report_data = {
            'user_id': user_id,
            'username': username,
            'url': url,
            'error_type': error_type,
            'error_message': error_message,
            'status': 'pending',  # pending, resolved
            'created_at': datetime.now(),
            'resolved_at': None,
            'admin_note': None
        }

        result = error_reports_collection.insert_one(report_data)
        logger.info(f"✅ تم إنشاء بلاغ خطأ: {result.inserted_id}")

        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"❌ فشل إنشاء بلاغ الخطأ: {e}")
        return None


def get_pending_error_reports(limit: int = 50):
    """جلب البلاغات المعلقة (غير المحلولة)"""
    try:
        if error_reports_collection is None:
            return []

        reports = list(error_reports_collection.find(
            {'status': 'pending'}
        ).sort('created_at', -1).limit(limit))

        return reports
    except Exception as e:
        logger.error(f"❌ فشل جلب البلاغات المعلقة: {e}")
        return []


def get_all_error_reports(limit: int = 100):
    """جلب جميع البلاغات (معلقة ومحلولة)"""
    try:
        if error_reports_collection is None:
            return []

        reports = list(error_reports_collection.find().sort('created_at', -1).limit(limit))

        return reports
    except Exception as e:
        logger.error(f"❌ فشل جلب البلاغات: {e}")
        return []


def resolve_error_report(report_id: str, admin_note: str = None):
    """
    تحديد بلاغ كـ "محلول"

    Args:
        report_id: معرف البلاغ
        admin_note: ملاحظة اختيارية من المدير
    """
    try:
        if error_reports_collection is None:
            return False

        from bson.objectid import ObjectId

        update_data = {
            'status': 'resolved',
            'resolved_at': datetime.now()
        }

        if admin_note:
            update_data['admin_note'] = admin_note

        result = error_reports_collection.update_one(
            {'_id': ObjectId(report_id)},
            {'$set': update_data}
        )

        if result.modified_count > 0:
            logger.info(f"✅ تم حل البلاغ: {report_id}")
            return True
        else:
            logger.warning(f"⚠️ لم يتم العثور على البلاغ: {report_id}")
            return False
    except Exception as e:
        logger.error(f"❌ فشل حل البلاغ: {e}")
        return False


def get_error_report_by_id(report_id: str):
    """جلب بلاغ محدد بواسطة المعرف"""
    try:
        if error_reports_collection is None:
            return None

        from bson.objectid import ObjectId

        report = error_reports_collection.find_one({'_id': ObjectId(report_id)})

        return report
    except Exception as e:
        logger.error(f"❌ فشل جلب البلاغ: {e}")
        return None


def delete_error_report(report_id: str):
    """حذف بلاغ"""
    try:
        if error_reports_collection is None:
            return False

        from bson.objectid import ObjectId

        result = error_reports_collection.delete_one({'_id': ObjectId(report_id)})

        if result.deleted_count > 0:
            logger.info(f"✅ تم حذف البلاغ: {report_id}")
            return True
        else:
            logger.warning(f"⚠️ لم يتم العثور على البلاغ: {report_id}")
            return False
    except Exception as e:
        logger.error(f"❌ فشل حذف البلاغ: {e}")
        return False


def get_error_stats():
    """جلب إحصائيات الأخطاء"""
    try:
        if error_reports_collection is None:
            return {}

        total = error_reports_collection.count_documents({})
        pending = error_reports_collection.count_documents({'status': 'pending'})
        resolved = error_reports_collection.count_documents({'status': 'resolved'})

        # إحصائيات حسب نوع الخطأ
        error_types = {}
        reports = list(error_reports_collection.find())
        for report in reports:
            error_type = report.get('error_type', 'unknown')
            error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            'total': total,
            'pending': pending,
            'resolved': resolved,
            'error_types': error_types
        }
    except Exception as e:
        logger.error(f"❌ فشل جلب إحصائيات الأخطاء: {e}")
        return {}
