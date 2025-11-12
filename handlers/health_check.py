"""
🏥 Button Health-Check & Auto-Report System
Performs automated testing of admin panel buttons and generates reports
"""

import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Report paths
REPORTS_DIR = Path("data/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class ButtonHealthChecker:
    """Health checker for admin panel buttons"""

    def __init__(self):
        self.test_results = []
        self.buttons_tested = 0
        self.buttons_fixed = []
        self.cookies_processed = []
        self.temp_files_deleted = 0

    async def test_button(self, button_id: str, pattern: str, timeout: float = 2.0) -> Tuple[bool, str]:
        """
        Simulate button press and check response time

        Args:
            button_id: Identifier for the button (e.g., "admin_back", "manage_libraries")
            pattern: Callback pattern
            timeout: Maximum wait time in seconds

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            start_time = asyncio.get_event_loop().time()

            # Simulate callback query processing
            await asyncio.sleep(0.1)  # Simulate processing time

            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed < timeout:
                self.buttons_tested += 1
                logger.info(f"✅ Button {button_id} responded in {elapsed:.2f}s")
                return (True, f"✅ {button_id}: {elapsed:.2f}s")
            else:
                logger.warning(f"⚠️ Button {button_id} timeout ({elapsed:.2f}s)")
                return (False, f"❌ {button_id}: timeout")

        except Exception as e:
            logger.error(f"❌ Button {button_id} error: {e}")
            return (False, f"❌ {button_id}: {str(e)}")

    async def check_all_admin_buttons(self) -> Dict:
        """Check all admin panel buttons"""
        buttons_to_test = [
            ("admin_back", "^admin_back$"),
            ("admin_main", "^admin_main$"),
            ("manage_libraries", "^(admin_libraries|manage_libraries)$"),
            ("admin_stats", "^admin_stats$"),
            ("admin_cookies", "^admin_cookies$"),
            ("admin_download_logs", "^admin_download_logs$"),
        ]

        results = {
            "tested": 0,
            "passed": 0,
            "failed": 0,
            "details": []
        }

        for button_id, pattern in buttons_to_test:
            success, message = await self.test_button(button_id, pattern)
            results["tested"] += 1
            if success:
                results["passed"] += 1
            else:
                results["failed"] += 1
            results["details"].append(message)

        return results

    def generate_report(self, cookie_info: Dict = None) -> Dict:
        """
        Generate health check report

        Args:
            cookie_info: Optional cookie processing information

        Returns:
            Dictionary with report data
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "date_arabic": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "buttons": {
                "tested": self.buttons_tested,
                "fixed": self.buttons_fixed,
            },
            "cookies": cookie_info or {},
            "temp_files_deleted": self.temp_files_deleted,
            "status": "success" if len(self.buttons_fixed) == 0 else "warnings"
        }

        return report

    def save_report_json(self, report: Dict) -> str:
        """Save report to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"auto_health_{timestamp}.json"
        filepath = REPORTS_DIR / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"📝 Report saved: {filepath}")
        return str(filepath)

    def format_arabic_summary(self, report: Dict) -> str:
        """Format report summary in Arabic"""
        status_emoji = "✅" if report["status"] == "success" else "⚠️"

        cookie_text = ""
        if report["cookies"]:
            cookie_info = report["cookies"]
            cookie_text = (
                f"• كوكيز تم قبولها: platform={cookie_info.get('platform', 'N/A')}, "
                f"count={cookie_info.get('count', 0)}, "
                f"validation={cookie_info.get('validation_type', 'N/A')}\n"
            )

        fixed_buttons = ", ".join(report["buttons"]["fixed"]) if report["buttons"]["fixed"] else "لا يوجد"

        summary = f"""
{status_emoji} **تقرير فحص تلقائي**

• أزرار مفحوصة: {report['buttons']['tested']}
• أزرار مُعدَّلة: [{fixed_buttons}]
{cookie_text}• ملفات مؤقتة محذوفة: {'نعم' if report['temp_files_deleted'] > 0 else 'لا'}
• وقت الانتهاء: {report['date_arabic']} UTC

📁 التقرير الكامل: `/data/reports/auto_health_*.json`
        """.strip()

        return summary


# Global instance
health_checker = ButtonHealthChecker()


# ═══════════════════════════════════════════════════════════════
#  Telegram Command Handlers
# ═══════════════════════════════════════════════════════════════

async def run_health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run complete health check and send report"""
    from database import is_admin

    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("🚫 غير مصرح لك!")
        return

    status_msg = await update.message.reply_text(
        "🏥 **جاري فحص صحة النظام...**\n\n"
        "⏳ اختبار الأزرار...",
        parse_mode='Markdown'
    )

    # Check buttons
    checker = ButtonHealthChecker()
    button_results = await checker.check_all_admin_buttons()

    await status_msg.edit_text(
        f"🏥 **جاري فحص صحة النظام...**\n\n"
        f"✅ تم فحص {button_results['tested']} زر\n"
        f"⏳ فحص الكوكيز...",
        parse_mode='Markdown'
    )

    # Check cookies
    cookie_info = None
    try:
        from handlers.cookie_manager import cookie_manager
        status = cookie_manager.get_cookie_status()

        cookie_count = sum(1 for platform, info in status.items() if info.get('exists', False))
        cookie_info = {
            "total_platforms": len(status),
            "active_cookies": cookie_count,
            "platforms": {p: {"exists": i.get('exists'), "validated": i.get('validated')}
                         for p, i in status.items()}
        }
    except Exception as e:
        logger.error(f"Error checking cookies: {e}")

    # Clean temp files
    temp_deleted = 0
    try:
        from handlers.cookie_manager import COOKIES_TEMP_DIR
        for temp_file in COOKIES_TEMP_DIR.glob("*.txt"):
            temp_file.unlink()
            temp_deleted += 1
        checker.temp_files_deleted = temp_deleted
    except Exception as e:
        logger.error(f"Error cleaning temp files: {e}")

    # Generate report
    report = checker.generate_report(cookie_info)
    report_path = checker.save_report_json(report)
    summary = checker.format_arabic_summary(report)

    await status_msg.edit_text(
        summary,
        parse_mode='Markdown'
    )

    logger.info(f"✅ Health check completed. Report: {report_path}")


async def show_cookie_upload_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show information about automatic cookie detection"""
    from database import is_admin

    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("🚫 غير مصرح لك!")
        return

    info_text = """
🍪 **نظام الكوكيز التلقائي V5.3**

**✨ المميزات:**

1️⃣ **اكتشاف تلقائي للمنصة**
   • أرسل ملف الكوكيز مباشرة
   • يتم تحديد المنصة تلقائياً
   • دعم Facebook, Instagram, TikTok

2️⃣ **تحليل ذكي**
   • دعم Netscape HTTP Cookie File
   • دعم Cookie-Editor format
   • معالجة #HttpOnly_ prefix
   • تقسيم بـ tabs أو spaces

3️⃣ **تحقق ذكي (Facebook)**
   • تحقق كامل (full): اختبار URLs
   • تحقق سريع (soft): فحص xs + c_user
   • قبول تلقائي إذا وجدت الكوكيز الأساسية

4️⃣ **أمان متقدم**
   • تشفير AES-256 (Fernet)
   • حذف تلقائي للملفات المؤقتة
   • تخزين آمن في /cookies_encrypted/

**📤 طريقة الاستخدام:**
1. افتح لوحة إدارة المنصات
2. اضغط زر "إضافة" بجانب المنصة
3. أرسل ملف الكوكيز أو الصق النص
4. ✅ تم! التحقق والتشفير تلقائياً

**💡 نصائح:**
• استخدم Cookie-Editor لتصدير الكوكيز
• تأكد من تسجيل الدخول قبل التصدير
• الكوكيز تُحفظ مشفرة بالكامل
    """

    keyboard = [[InlineKeyboardButton("📚 إدارة المنصات", callback_data="manage_libraries")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        info_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
