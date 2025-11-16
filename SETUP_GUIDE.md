# 🚀 دليل التثبيت والتشغيل السريع
**Quick Setup & Installation Guide**

---

## 📋 المتطلبات الأساسية
**Prerequisites**

- Python 3.8 أو أحدث / Python 3.8 or higher
- MongoDB (محلي أو عبر الإنترنت) / MongoDB (local or cloud)
- حساب Telegram Bot من [@BotFather](https://t.me/BotFather)

---

## ⚡ التثبيت السريع (5 دقائق)
**Quick Installation (5 minutes)**

### 1️⃣ استنساخ المشروع
**Clone the Repository**

```bash
git clone https://github.com/w70t/Bot-iraq.git
cd Bot-iraq
```

### 2️⃣ إنشاء البيئة الافتراضية
**Create Virtual Environment**

```bash
# إنشاء البيئة الافتراضية
python3 -m venv venv

# تفعيل البيئة الافتراضية
source venv/bin/activate  # Linux/Mac
# أو
venv\Scripts\activate  # Windows
```

### 3️⃣ تثبيت المكتبات
**Install Dependencies**

```bash
pip install -r requirements.txt
```

### 4️⃣ إعداد ملف البيئة
**Configure Environment File**

```bash
# نسخ ملف القالب
cp .env.example .env

# فتح الملف للتعديل
nano .env  # أو استخدم محرر نصوص آخر
```

**املأ البيانات التالية:**

```env
# 1. توكن البوت (مطلوب)
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

# 2. معرفات الأدمنز (مطلوب)
ADMIN_IDS=123456789,987654321

# 3. رابط MongoDB (مطلوب)
MONGODB_URI=mongodb://localhost:27017/bot_database

# 4. قناة السجلات (اختياري)
LOG_CHANNEL_ID=-1001234567890
```

---

## 🔑 كيف تحصل على البيانات المطلوبة؟
**How to Get Required Information**

### 🤖 Bot Token

1. افتح [@BotFather](https://t.me/BotFather) على Telegram
2. أرسل `/newbot`
3. اتبع التعليمات
4. انسخ الـ Token الذي يظهر لك

### 👤 Admin ID

1. افتح [@userinfobot](https://t.me/userinfobot) على Telegram
2. أرسل `/start`
3. سيظهر لك معرفك (Your ID)

### 🗄️ MongoDB URI

**الخيار 1: MongoDB محلي**
```bash
# تثبيت MongoDB
sudo apt install mongodb  # Ubuntu/Debian
brew install mongodb-community  # macOS

# تشغيل MongoDB
sudo systemctl start mongodb  # Linux
brew services start mongodb-community  # macOS

# استخدم هذا الرابط
MONGODB_URI=mongodb://localhost:27017/bot_database
```

**الخيار 2: MongoDB Atlas (سحابي - مجاني)**
1. اذهب إلى [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. أنشئ حساب مجاني
3. أنشئ Cluster جديد
4. اضغط على "Connect"
5. اختر "Connect your application"
6. انسخ الرابط وضعه في `.env`

### 📢 Log Channel ID (اختياري)

1. أنشئ قناة Telegram جديدة
2. أضف البوت كمسؤول في القناة
3. افتح [@username_to_id_bot](https://t.me/username_to_id_bot)
4. أرسل رابط القناة
5. انسخ الـ ID (يبدأ بـ `-100`)

---

## ▶️ تشغيل البوت
**Running the Bot**

### تشغيل عادي
**Normal Run**

```bash
# تأكد من تفعيل البيئة الافتراضية
source venv/bin/activate

# شغّل البوت
python3 bot.py
```

### تشغيل في الخلفية (مستمر)
**Background Run (Persistent)**

```bash
# استخدم screen أو tmux
screen -S bot
python3 bot.py
# اضغط Ctrl+A ثم D للخروج وإبقاء البوت يعمل

# للعودة للجلسة
screen -r bot
```

**أو استخدم systemd:**

```bash
# أنشئ ملف الخدمة
sudo nano /etc/systemd/system/telegram-bot.service

# أضف المحتوى التالي:
[Unit]
Description=Telegram Download Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/Bot-iraq
Environment=PATH=/path/to/Bot-iraq/venv/bin
ExecStart=/path/to/Bot-iraq/venv/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target

# شغّل الخدمة
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot

# راقب الحالة
sudo systemctl status telegram-bot
```

---

## 🍪 رفع الكوكيز (للمنصات التي تحتاج تسجيل دخول)
**Upload Cookies (for platforms requiring login)**

### المنصات المدعومة:
- 📘 Facebook
- 📸 Instagram
- 🧵 Threads
- 🎵 TikTok
- 📌 Pinterest
- 🐦 Twitter/X
- 🤖 Reddit
- 🎬 Vimeo
- 📺 Dailymotion
- 🎮 Twitch

### كيفية تصدير الكوكيز:

#### باستخدام Cookie Editor (موصى به):

1. **ثبّت الإضافة:**
   - Chrome: [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
   - Firefox: [Cookie-Editor](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/)

2. **تصدير الكوكيز:**
   - افتح الموقع المطلوب (مثلاً instagram.com)
   - سجل الدخول لحسابك
   - اضغط على أيقونة Cookie-Editor
   - اضغط "Export" → "Netscape"
   - احفظ الملف باسم `instagram.txt`

3. **رفع الكوكيز للبوت:**
   - افتح البوت على Telegram
   - أرسل `/admin`
   - اختر "📚 المكتبات"
   - اختر المنصة (مثل 🧵 Threads)
   - اضغط "⬆️ رفع كوكيز جديدة"
   - أرسل ملف الكوكيز

---

## 🔧 استكشاف الأخطاء
**Troubleshooting**

### ❌ خطأ: `InvalidToken`
```
telegram.error.InvalidToken: You must pass the token...
```
**الحل:** تأكد من نسخ الـ BOT_TOKEN بشكل صحيح من @BotFather

### ❌ خطأ: `MONGODB_URI غير موجود`
```
!!! خطأ في الاتصال بقاعدة البيانات: متغير البيئة MONGODB_URI غير موجود
```
**الحل:** تأكد من وجود ملف `.env` وفيه `MONGODB_URI`

### ❌ خطأ: `No valid ADMIN_IDs found`
```
⚠️ No valid ADMIN_IDs found in .env
```
**الحل:** أضف `ADMIN_IDS` في ملف `.env`

### ❌ الكوكيز لا تعمل
**الحل:**
1. تأكد من تصدير الكوكيز بصيغة Netscape
2. تأكد من تسجيل الدخول في المتصفح
3. جرب تصدير كوكيز جديدة
4. تحقق من عدم انتهاء صلاحية الجلسة

---

## 📊 الأوامر المتاحة
**Available Commands**

### للمستخدمين:
- `/start` - بدء البوت
- `/help` - المساعدة
- `/account` - معلومات الحساب

### للأدمن فقط:
- `/admin` - لوحة التحكم
- `/healthcheck` - فحص صحة النظام
- `/cookieinfo` - معلومات الكوكيز
- `/errors` - عرض الأخطاء

---

## 📅 الجدول الزمني للمهام التلقائية
**Scheduled Tasks**

| المهمة | التوقيت | الوصف |
|--------|---------|-------|
| 🍪 فحص الكوكيز | 00:00 UTC يومياً | فحص صلاحية الكوكيز |
| 💾 نسخ احتياطي | 00:30 UTC أسبوعياً | نسخ احتياطي للكوكيز |
| 📊 تقرير الأخطاء | 23:00 UTC يومياً | تقرير الأخطاء للأدمن |

---

## 🆘 الدعم
**Support**

للمساعدة أو الإبلاغ عن مشاكل:
- 📧 GitHub Issues: [Create Issue](https://github.com/w70t/Bot-iraq/issues)
- 📸 Instagram: [@7kmmy](https://instagram.com/7kmmy)

---

## 📝 ملاحظات مهمة
**Important Notes**

1. ✅ لا تشارك ملف `.env` أبداً
2. ✅ احتفظ بنسخة احتياطية من الكوكيز
3. ✅ حدّث البوت بانتظام
4. ✅ راقب السجلات للأخطاء

---

**تم بنجاح! البوت الآن جاهز للعمل 🚀**
**Success! Your bot is ready to run 🚀**
