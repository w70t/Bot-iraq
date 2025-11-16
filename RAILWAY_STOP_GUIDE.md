# دليل إيقاف البوت من Railway
# Guide to Stop Bot on Railway

## المشكلة / The Problem

البوت يعمل حالياً على Railway، لذلك لا يمكن تشغيله محلياً.
The bot is currently running on Railway, so it cannot run locally.

خطأ 409 Conflict يعني أن هناك instance آخر من البوت يعمل.
409 Conflict error means another instance of the bot is running.

---

## الحل / Solution

### الطريقة 1: إيقاف من Railway Dashboard

1. **افتح Railway:**
   ```
   https://railway.app/
   ```

2. **سجّل الدخول** لحسابك

3. **افتح مشروع البوت:**
   - ابحث عن المشروع `Bot-iraq` أو `VideoArabiBot`

4. **أوقف الـ Deployment:**
   - اضغط على المشروع
   - اذهب إلى `Settings`
   - ابحث عن `Deployment` أو `Service`
   - اضغط على `Stop` أو `Pause`

5. **أو احذف الـ Service مؤقتاً:**
   - Settings → Delete Service
   - (يمكنك إعادة إنشائه لاحقاً)

---

### الطريقة 2: باستخدام Railway CLI

إذا كان لديك Railway CLI مثبت:

```bash
# Login to Railway
railway login

# Link to your project
railway link

# Stop the service
railway down

# Or remove service
railway service delete
```

---

## ✅ التحقق من الإيقاف / Verify Stop

بعد الإيقاف، انتظر 30 ثانية ثم جرّب:

```bash
python3 check_webhook.py
```

إذا توقف البوت بنجاح، لن تظهر رسالة Conflict.

---

## 🚀 تشغيل البوت محلياً / Run Bot Locally

بعد إيقاف Railway:

```bash
# 1. أنشئ ملف .env من المثال
cp .env.example .env

# 2. افتح .env وأضف:
#    - BOT_TOKEN
#    - ADMIN_IDS
#    - MONGODB_URI
#    - معرفات القنوات (اختياري)

# 3. شغّل البوت
python3 bot.py
```

---

## 📋 قائمة المراجعة / Checklist

- [ ] إيقاف البوت من Railway
- [ ] انتظار 30 ثانية
- [ ] إنشاء 5 قنوات خاصة
- [ ] إضافة البوت كمسؤول في كل قناة
- [ ] الحصول على معرفات القنوات
- [ ] نسخ .env.example إلى .env
- [ ] إضافة جميع المتغيرات المطلوبة
- [ ] تشغيل البوت محلياً
- [ ] التحقق من الرسائل في القنوات

---

## 🔄 إعادة التشغيل على Railway لاحقاً

إذا أردت إعادة تشغيله على Railway:

1. ارفع التغييرات للـ main branch:
   ```bash
   git checkout main
   git merge claude/create-channels-018EzaB5Xkhm7F4UMp7GGt5K
   git push origin main
   ```

2. أضف متغيرات البيئة في Railway Dashboard:
   - BOT_TOKEN
   - ADMIN_IDS
   - MONGODB_URI
   - LOG_CHANNEL_ID
   - VIDEOS_CHANNEL_ID
   - NEW_USERS_CHANNEL_ID
   - STATS_CHANNEL_ID
   - ADMIN_CHANNEL_ID
   - UPDATES_CHANNEL_USERNAME

3. Railway سيعيد التشغيل تلقائياً

---

## 💡 نصيحة / Tip

**لا تشغّل البوت في مكانين معاً!**
Never run the bot in two places at once!

- إما محلياً (Local)
- أو على Railway
- **ليس الاثنين معاً**

---

تم الإنشاء: 2025-11-16
