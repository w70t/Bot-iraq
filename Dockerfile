# استخدام Python 3.9 كصورة أساسية
FROM python:3.9-slim

# إعداد متغيرات البيئة
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# إعداد مجلد العمل
WORKDIR /app

# تحديث النظام وتثبيت FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات أولاً (للاستفادة من Docker caching)
COPY requirements.txt .

# تثبيت المتطلبات
RUN pip install --no-cache-dir -r requirements.txt

# نسخ ملفات التطبيق
COPY . .

# إنشاء مجلد للفيديوهات
RUN mkdir -p videos

# تشغيل البوت
CMD ["python", "bot.py"]