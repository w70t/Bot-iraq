"""
نظام تتبع الأخطاء المتقدم للبوت
Advanced Error Tracking System

الميزات:
- تتبع جميع الأخطاء مع تفاصيل كاملة
- تصنيف الأخطاء حسب النوع
- حفظ تفاصيل الأخطاء في ملف JSON
- إرسال تقرير للمدير عند حدوث أخطاء
"""

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# مسار ملف الأخطاء
ERROR_LOG_FILE = Path("data/error_tracking.json")
ERROR_LOG_FILE.parent.mkdir(exist_ok=True)


class ErrorTracker:
    """نظام تتبع الأخطاء"""

    @staticmethod
    def track_error(
        error_type: str,
        error_message: str,
        context: Dict[str, Any],
        traceback_str: Optional[str] = None,
        user_id: Optional[int] = None,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        تتبع خطأ وحفظ تفاصيله

        Args:
            error_type: نوع الخطأ (download, cookie, network, etc.)
            error_message: رسالة الخطأ
            context: معلومات إضافية عن السياق
            traceback_str: معلومات تتبع المكدس
            user_id: معرف المستخدم
            url: الرابط الذي تسبب في الخطأ

        Returns:
            تفاصيل الخطأ المسجل
        """

        error_data = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "error_message": error_message,
            "user_id": user_id,
            "url": url,
            "context": context,
            "traceback": traceback_str
        }

        # حفظ في ملف
        ErrorTracker._save_to_file(error_data)

        # طباعة في السجل
        logger.error(
            f"🔴 [ERROR_TRACKER] {error_type.upper()}\n"
            f"   Message: {error_message}\n"
            f"   User: {user_id}\n"
            f"   URL: {url}\n"
            f"   Context: {json.dumps(context, ensure_ascii=False, indent=2)}"
        )

        return error_data

    @staticmethod
    def track_download_error(
        platform: str,
        url: str,
        error_message: str,
        user_id: Optional[int] = None,
        ydl_info: Optional[Dict] = None,
        cookies_used: bool = False,
        extractor_used: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        تتبع خطأ التحميل بشكل مفصل

        Args:
            platform: المنصة (facebook, instagram, etc.)
            url: الرابط
            error_message: رسالة الخطأ
            user_id: معرف المستخدم
            ydl_info: معلومات yt-dlp
            cookies_used: هل تم استخدام cookies
            extractor_used: اسم extractor المستخدم
        """

        context = {
            "platform": platform,
            "cookies_used": cookies_used,
            "extractor_used": extractor_used,
            "ydl_info": ydl_info or {}
        }

        # تحليل نوع الخطأ
        error_category = ErrorTracker._categorize_error(error_message, platform)

        context["error_category"] = error_category

        return ErrorTracker.track_error(
            error_type=f"download_{platform}",
            error_message=error_message,
            context=context,
            user_id=user_id,
            url=url
        )

    @staticmethod
    def _categorize_error(error_message: str, platform: str) -> str:
        """تصنيف الخطأ حسب النوع"""

        error_lower = error_message.lower()

        # أخطاء التحميل
        if "unsupported url" in error_lower:
            return "unsupported_url"
        elif "private" in error_lower or "login" in error_lower:
            return "private_content"
        elif "unavailable" in error_lower or "not found" in error_lower:
            return "content_not_found"
        elif "timeout" in error_lower:
            return "timeout"
        elif "network" in error_lower or "connection" in error_lower:
            return "network_error"
        elif "cookie" in error_lower:
            return "cookie_issue"
        elif "extractor" in error_lower:
            return "extractor_error"

        # أخطاء خاصة بمنصات
        if platform == "facebook" and "story" in error_lower:
            return "facebook_story_unsupported"
        elif platform == "instagram" and "story" in error_lower:
            return "instagram_story_issue"

        return "unknown"

    @staticmethod
    def _save_to_file(error_data: Dict[str, Any]):
        """حفظ الخطأ في ملف JSON"""

        try:
            # قراءة الأخطاء الموجودة
            if ERROR_LOG_FILE.exists():
                with open(ERROR_LOG_FILE, 'r', encoding='utf-8') as f:
                    errors = json.load(f)
            else:
                errors = []

            # إضافة الخطأ الجديد
            errors.append(error_data)

            # الحفاظ على آخر 500 خطأ فقط
            errors = errors[-500:]

            # حفظ في الملف
            with open(ERROR_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(errors, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"فشل حفظ الخطأ في الملف: {e}")

    @staticmethod
    def get_recent_errors(limit: int = 10, error_type: Optional[str] = None) -> list:
        """
        الحصول على الأخطاء الأخيرة

        Args:
            limit: عدد الأخطاء المطلوبة
            error_type: نوع الخطأ (اختياري للتصفية)

        Returns:
            قائمة بالأخطاء الأخيرة
        """

        try:
            if not ERROR_LOG_FILE.exists():
                return []

            with open(ERROR_LOG_FILE, 'r', encoding='utf-8') as f:
                errors = json.load(f)

            # تصفية حسب النوع إذا طُلب
            if error_type:
                errors = [e for e in errors if e.get("error_type") == error_type]

            # إرجاع الأحدث
            return errors[-limit:]

        except Exception as e:
            logger.error(f"فشل قراءة الأخطاء: {e}")
            return []

    @staticmethod
    def get_error_stats(hours: int = 24) -> Dict[str, Any]:
        """
        الحصول على إحصائيات الأخطاء

        Args:
            hours: عدد الساعات الأخيرة

        Returns:
            إحصائيات الأخطاء
        """

        try:
            if not ERROR_LOG_FILE.exists():
                return {"total": 0, "by_type": {}, "by_category": {}}

            with open(ERROR_LOG_FILE, 'r', encoding='utf-8') as f:
                errors = json.load(f)

            # تصفية حسب الوقت
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(hours=hours)

            recent_errors = [
                e for e in errors
                if datetime.fromisoformat(e["timestamp"]) > cutoff
            ]

            # حساب الإحصائيات
            stats = {
                "total": len(recent_errors),
                "by_type": {},
                "by_category": {},
                "by_platform": {}
            }

            for error in recent_errors:
                error_type = error.get("error_type", "unknown")
                category = error.get("context", {}).get("error_category", "unknown")
                platform = error.get("context", {}).get("platform", "unknown")

                stats["by_type"][error_type] = stats["by_type"].get(error_type, 0) + 1
                stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
                stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1

            return stats

        except Exception as e:
            logger.error(f"فشل حساب إحصائيات الأخطاء: {e}")
            return {"total": 0, "by_type": {}, "by_category": {}}

    @staticmethod
    def format_error_report(error_data: Dict[str, Any]) -> str:
        """
        تنسيق تقرير خطأ للإرسال للمدير

        Args:
            error_data: بيانات الخطأ

        Returns:
            تقرير منسق
        """

        report = (
            f"🔴 **تقرير خطأ جديد**\n\n"
            f"⏰ **الوقت:** {error_data['timestamp']}\n"
            f"📌 **النوع:** `{error_data['error_type']}`\n"
            f"👤 **المستخدم:** `{error_data.get('user_id', 'N/A')}`\n"
        )

        if error_data.get('url'):
            # عرض URL مختصر
            url = error_data['url']
            if len(url) > 60:
                url = url[:60] + "..."
            report += f"🔗 **الرابط:** `{url}`\n"

        context = error_data.get('context', {})
        if context:
            report += f"\n📊 **التفاصيل:**\n"

            if 'platform' in context:
                report += f"• المنصة: `{context['platform']}`\n"

            if 'error_category' in context:
                report += f"• الفئة: `{context['error_category']}`\n"

            if 'cookies_used' in context:
                report += f"• Cookies: {'✅' if context['cookies_used'] else '❌'}\n"

            if 'extractor_used' in context:
                report += f"• Extractor: `{context['extractor_used']}`\n"

        # رسالة الخطأ (مختصرة)
        error_msg = error_data['error_message']
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."

        report += f"\n❌ **الخطأ:**\n```\n{error_msg}\n```"

        return report


# دالة مساعدة سريعة
def track_download_error(
    platform: str,
    url: str,
    error: Exception,
    user_id: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    دالة سريعة لتتبع أخطاء التحميل

    Usage:
        try:
            # ... download code ...
        except Exception as e:
            track_download_error("facebook", url, e, user_id=123)
    """

    return ErrorTracker.track_download_error(
        platform=platform,
        url=url,
        error_message=str(error),
        user_id=user_id,
        **kwargs
    )
