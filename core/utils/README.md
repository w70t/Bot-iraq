# Core Utils - دليل الاستخدام

## 📚 نظرة عامة

هذه الحزمة تحتوي على جميع الأدوات المساعدة الأساسية للبوت.

---

## 📦 الملفات

### 1. validators.py
دوال التحقق من صحة المدخلات

```python
from core.utils.validators import validate_url, validate_user_id, validate_days

# مثال
is_valid = validate_url("https://example.com")
is_valid, user_id, error = validate_user_id("123456")
is_valid, days, error = validate_days("30")
```

### 2. formatters.py
دوال تنسيق البيانات للعرض

```python
from core.utils.formatters import format_file_size, format_duration, escape_markdown, clean_filename

# مثال
size_str = format_file_size(1024000)  # "1000.00 KB"
duration_str = format_duration(3665)  # "01:01:05"
safe_text = escape_markdown("Hello *world*")
safe_name = clean_filename("invalid:file<name>.txt")
```

### 3. helpers.py
دوال مساعدة عامة

```python
from core.utils.helpers import (
    # Config & Messages
    load_messages, load_config, get_message, get_config,

    # Bot Menu
    setup_bot_menu,

    # Decorators
    rate_limit, admin_only,

    # Logging
    send_critical_log, send_video_report, log_warning,

    # Cleanup
    cleanup_temp_files, cleanup_old_files
)

# مثال - استخدام decorator
@rate_limit(seconds=10)
@admin_only
async def my_command(update, context):
    await update.message.reply_text("Hello Admin!")
```

---

## 🔄 استيراد شامل

يمكنك استيراد كل شيء دفعة واحدة:

```python
from core.utils import *
```

---

## ⚠️ ملاحظات

- جميع الدوال تستخدم `logger` من `config.logger`
- الدوال الداخلية (التي تبدأ بـ `_`) يُفضل عدم استخدامها مباشرة
- decorators مثل `@rate_limit` و `@admin_only` جاهزة للاستخدام

---

## 📖 المزيد

للمزيد من التفاصيل، راجع:
- `/home/user/Bot-iraq/REFACTORING_REPORT.md`
