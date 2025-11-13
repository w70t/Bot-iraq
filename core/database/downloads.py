from datetime import datetime, timedelta
from .base import users_collection, db

# استخدام logger من config
try:
    from config.logger import get_logger
except ImportError:
    import logging
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)

# إنشاء مجموعة التحميلات
try:
    downloads_collection = db.downloads if db is not None else None
except Exception as e:
    logger.error(f"❌ فشل إنشاء مجموعة التحميلات: {e}")
    downloads_collection = None


def increment_download_count(user_id: int):
    """زيادة عداد التحميلات"""
    try:
        today = datetime.now().date()

        users_collection.update_one(
            {'user_id': user_id},
            {
                '$inc': {'download_count': 1},
                '$push': {
                    'daily_downloads': {
                        'date': datetime.combine(today, datetime.min.time()),
                        'count': 1
                    }
                }
            }
        )
        logger.info(f"✅ تم زيادة عداد التحميلات للمستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل زيادة العداد: {e}")
        return False


def get_daily_download_count(user_id: int) -> int:
    """جلب عدد التحميلات اليومية"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return 0

        today = datetime.now().date()
        daily_downloads = user.get('daily_downloads', [])

        today_count = sum(
            1 for download in daily_downloads
            if isinstance(download.get('date'), datetime) and download['date'].date() == today
        )

        return today_count
    except Exception as e:
        logger.error(f"❌ فشل جلب العداد اليومي: {e}")
        return 0


def get_total_downloads_count() -> int:
    """جلب إجمالي التحميلات"""
    try:
        pipeline = [
            {'$group': {'_id': None, 'total': {'$sum': '$download_count'}}}
        ]
        result = list(users_collection.aggregate(pipeline))
        if result:
            return result[0]['total']
        return 0
    except Exception as e:
        logger.error(f"❌ فشل جلب الإجمالي: {e}")
        return 0


def reset_daily_downloads():
    """إعادة تعيين التحميلات اليومية (يتم تشغيله تلقائياً)"""
    try:
        yesterday = datetime.now() - timedelta(days=1)
        users_collection.update_many(
            {},
            {
                '$pull': {
                    'daily_downloads': {
                        'date': {'$lt': yesterday}
                    }
                }
            }
        )
        logger.info("✅ تم تنظيف السجلات القديمة")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تنظيف السجلات: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
#  Mission 10: Download Tracking & Admin Logs
# ═══════════════════════════════════════════════════════════════

def track_download(
    user_id: int,
    platform: str,
    mode: str,
    quality: str = None,
    format: str = None,
    status: str = 'completed',
    url: str = None,
    file_size: int = 0,
    error_msg: str = None
):
    """
    تتبع تحميل مفصل

    Args:
        user_id: معرف المستخدم
        platform: المنصة (youtube/instagram/facebook)
        mode: الوضع (video/audio)
        quality: الجودة (360/720/1080) للفيديو
        format: الصيغة (mp3/m4a) للصوت
        status: الحالة (completed/canceled/failed)
        url: رابط التحميل
        file_size: حجم الملف بالبايت
        error_msg: رسالة الخطأ إن وجدت
    """
    try:
        if downloads_collection is None:
            logger.warning("⚠️ مجموعة التحميلات غير متاحة")
            return False

        download_data = {
            'user_id': user_id,
            'platform': platform,
            'mode': mode,
            'quality': quality,
            'format': format,
            'status': status,
            'url': url,
            'file_size': file_size,
            'error_msg': error_msg,
            'timestamp': datetime.now(),
            'date': datetime.now().date()
        }

        downloads_collection.insert_one(download_data)

        # تحديث عداد التحميلات للمستخدم
        increment_download_count(user_id)

        logger.info(f"✅ تم تتبع التحميل: {user_id} - {platform} - {mode} - {status}")
        return True

    except Exception as e:
        logger.error(f"❌ فشل تتبع التحميل: {e}")
        return False


def get_user_downloads(user_id: int, limit: int = 50):
    """جلب سجل تحميلات المستخدم"""
    try:
        if downloads_collection is None:
            return []

        downloads = list(downloads_collection.find(
            {'user_id': user_id}
        ).sort('timestamp', -1).limit(limit))

        return downloads
    except Exception as e:
        logger.error(f"❌ فشل جلب تحميلات المستخدم: {e}")
        return []


def get_download_stats(start_date=None, end_date=None):
    """
    جلب إحصائيات التحميلات للأدمن

    Args:
        start_date: تاريخ البداية (datetime)
        end_date: تاريخ النهاية (datetime)

    Returns:
        dict: إحصائيات التحميلات
    """
    try:
        if downloads_collection is None:
            return {}

        # تحديد نطاق التاريخ
        query = {}
        if start_date or end_date:
            query['timestamp'] = {}
            if start_date:
                query['timestamp']['$gte'] = start_date
            if end_date:
                query['timestamp']['$lte'] = end_date

        # جلب جميع التحميلات في النطاق
        downloads = list(downloads_collection.find(query))

        # حساب الإحصائيات
        total_downloads = len(downloads)
        completed = len([d for d in downloads if d.get('status') == 'completed'])
        canceled = len([d for d in downloads if d.get('status') == 'canceled'])
        failed = len([d for d in downloads if d.get('status') == 'failed'])

        # إحصائيات حسب الوضع
        video_downloads = len([d for d in downloads if d.get('mode') == 'video'])
        audio_downloads = len([d for d in downloads if d.get('mode') == 'audio'])

        # إحصائيات حسب المنصة
        platforms = {}
        for download in downloads:
            platform = download.get('platform', 'unknown')
            platforms[platform] = platforms.get(platform, 0) + 1

        # أعلى المستخدمين تحميلاً
        user_downloads = {}
        for download in downloads:
            user_id = download.get('user_id')
            if user_id:
                user_downloads[user_id] = user_downloads.get(user_id, 0) + 1

        top_users = sorted(user_downloads.items(), key=lambda x: x[1], reverse=True)[:10]

        stats = {
            'total_downloads': total_downloads,
            'completed': completed,
            'canceled': canceled,
            'failed': failed,
            'video_downloads': video_downloads,
            'audio_downloads': audio_downloads,
            'platforms': platforms,
            'top_users': top_users,
            'success_rate': (completed / total_downloads * 100) if total_downloads > 0 else 0
        }

        return stats

    except Exception as e:
        logger.error(f"❌ فشل جلب إحصائيات التحميلات: {e}")
        return {}


def get_daily_download_stats():
    """جلب إحصائيات التحميلات اليومية"""
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = datetime.now()

        return get_download_stats(start_date=today_start, end_date=today_end)
    except Exception as e:
        logger.error(f"❌ فشل جلب إحصائيات اليوم: {e}")
        return {}


def generate_daily_report():
    """
    توليد تقرير يومي شامل

    Returns:
        str: نص التقرير بصيغة Markdown
    """
    try:
        stats = get_daily_download_stats()

        if not stats or stats.get('total_downloads', 0) == 0:
            return (
                "📊 **تقرير يومي - Daily Report**\n\n"
                f"📅 التاريخ / Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
                "ℹ️ لا توجد تحميلات اليوم\n"
                "No downloads today"
            )

        # بناء التقرير
        report = (
            "📊 **تقرير التحميلات اليومي / Daily Downloads Report**\n"
            "═════════════════════════════════════\n\n"
            f"📅 **التاريخ / Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"📥 **إجمالي التحميلات / Total Downloads:** {stats['total_downloads']}\n"
            f"✅ **مكتملة / Completed:** {stats['completed']}\n"
            f"❌ **ملغاة / Canceled:** {stats['canceled']}\n"
            f"⚠️ **فاشلة / Failed:** {stats['failed']}\n"
            f"📈 **معدل النجاح / Success Rate:** {stats['success_rate']:.1f}%\n\n"
            "─────────────────────────────────────\n\n"
            f"🎬 **تحميلات فيديو / Video Downloads:** {stats['video_downloads']}\n"
            f"🎧 **تحميلات صوت / Audio Downloads:** {stats['audio_downloads']}\n\n"
            "─────────────────────────────────────\n\n"
            "🌐 **المنصات / Platforms:**\n"
        )

        # إضافة إحصائيات المنصات
        for platform, count in stats['platforms'].items():
            report += f"   • {platform.capitalize()}: {count}\n"

        # إضافة أعلى المستخدمين
        if stats['top_users']:
            report += "\n─────────────────────────────────────\n\n"
            report += "👥 **أعلى المستخدمين / Top Users:**\n"
            for idx, (user_id, count) in enumerate(stats['top_users'][:5], 1):
                report += f"   {idx}. User {user_id}: {count} downloads\n"

        report += "\n═════════════════════════════════════\n"
        report += f"⏰ **وقت التقرير / Report Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return report

    except Exception as e:
        logger.error(f"❌ فشل توليد التقرير اليومي: {e}")
        return "❌ فشل توليد التقرير / Failed to generate report"


# ═══════════════════════════════════════════════════════════════
#  Download Success Rate Tracking
# ═══════════════════════════════════════════════════════════════

def track_download_success(user_id: int, success: bool):
    """تتبع نجاح/فشل التحميلات"""
    try:
        if users_collection is None:
            return False

        users_collection.update_one(
            {'user_id': user_id},
            {
                '$inc': {
                    'download_success_count' if success else 'download_fail_count': 1
                },
                '$setOnInsert': {
                    'download_success_count': 0,
                    'download_fail_count': 0
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"❌ فشل تتبع حالة التحميل: {e}")
        return False


def get_download_success_rate() -> float:
    """حساب معدل نجاح التحميلات"""
    try:
        if users_collection is None:
            return 0.0

        pipeline = [
            {
                '$group': {
                    '_id': None,
                    'total_success': {'$sum': '$download_success_count'},
                    'total_fail': {'$sum': '$download_fail_count'}
                }
            }
        ]
        result = list(users_collection.aggregate(pipeline))

        if result and len(result) > 0:
            success = result[0].get('total_success', 0)
            fail = result[0].get('total_fail', 0)
            total = success + fail

            if total > 0:
                return (success / total * 100)

        return 0.0
    except Exception as e:
        logger.error(f"❌ فشل حساب معدل النجاح: {e}")
        return 0.0


def get_user_download_stats(user_id: int) -> dict:
    """جلب إحصائيات التحميل للمستخدم"""
    try:
        if users_collection is None:
            return {'success': 0, 'fail': 0, 'rate': 0.0}

        user = users_collection.find_one({'user_id': user_id})

        if not user:
            return {'success': 0, 'fail': 0, 'rate': 0.0}

        success = user.get('download_success_count', 0)
        fail = user.get('download_fail_count', 0)
        total = success + fail

        rate = (success / total * 100) if total > 0 else 0.0

        return {
            'success': success,
            'fail': fail,
            'total': total,
            'rate': rate
        }
    except Exception as e:
        logger.error(f"❌ فشل جلب إحصائيات المستخدم: {e}")
        return {'success': 0, 'fail': 0, 'rate': 0.0}
