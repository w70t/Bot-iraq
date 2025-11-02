# 🚀 دليل تشغيل البوت على Xubuntu - خطوة بخطوة

## 📋 الخطوات الكاملة من الصفر

---

## 1️⃣ فك ضغط الملف

### افتح File Manager (مدير الملفات)
```
اضغط: Ctrl + Alt + T لفتح Terminal
أو
Applications → File Manager
```

### انتقل لمكان الملف المحمل
```bash
cd ~/Downloads
# أو إذا كان في مكان آخر
cd ~/Desktop
```

### فك الضغط
```bash
# فك ضغط الملف
unzip bot_final_with_pinterest_fix.zip -d telegram-bot

# ادخل للمجلد
cd telegram-bot

# اعرض محتويات المجلد
ls -la
```

**يجب أن ترى:**
```
bot.py
database.py
handlers/
requirements.txt
config.json
...
```

---

## 2️⃣ تثبيت Python و pip

### تحديث النظام أولاً
```bash
sudo apt update
sudo apt upgrade -y
```

### تثبيت Python 3 و pip
```bash
# تثبيت Python
sudo apt install python3 python3-pip python3-venv -y

# تحقق من النسخة
python3 --version
# يجب أن تظهر: Python 3.x.x

pip3 --version
# يجب أن تظهر: pip xx.x.x
```

---

## 3️⃣ إنشاء بيئة افتراضية (Virtual Environment)

### إنشاء البيئة
```bash
# تأكد أنك في مجلد telegram-bot
cd ~/Downloads/telegram-bot

# إنشاء بيئة افتراضية
python3 -m venv venv

# تفعيل البيئة الافتراضية
source venv/bin/activate
```

**يجب أن يظهر `(venv)` قبل اسم المستخدم:**
```
(venv) abdalwahab@abdalwahab:~/Downloads/telegram-bot$
```

---

## 4️⃣ تثبيت المكتبات المطلوبة

### تثبيت من requirements.txt
```bash
# تأكد أن البيئة الافتراضية مفعّلة
pip install -r requirements.txt
```

### إذا ظهرت مشاكل، ثبّت المكتبات يدوياً:
```bash
pip install python-telegram-bot==21.0
pip install yt-dlp --upgrade
pip install pymongo
pip install python-dotenv
pip install pillow
pip install requests
```

### تثبيت ffmpeg (مهم للفيديو!)
```bash
sudo apt install ffmpeg -y

# تحقق من التثبيت
ffmpeg -version
```

---

## 5️⃣ إعداد ملف المتغيرات (.env)

### إنشاء ملف .env
```bash
# استخدم محرر نصوص nano
nano .env
```

### أضف هذه المعلومات:
```bash
# معلومات البوت
BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# قاعدة البيانات MongoDB
MONGODB_URI=YOUR_MONGODB_CONNECTION_STRING

# معرّف المدير (Telegram User ID)
ADMIN_ID=YOUR_TELEGRAM_USER_ID

# قناة السجلات (اختياري)
LOG_CHANNEL_ID=-100XXXXXXXXX

# قناة الفيديوهات (اختياري)
LOG_CHANNEL_ID_VIDEOS=-100XXXXXXXXX

# للاستضافة (اختياري)
RAILWAY_PUBLIC_DOMAIN=
PORT=8443
```

### حفظ الملف:
```
اضغط: Ctrl + X
اضغط: Y (للحفظ)
اضغط: Enter
```

---

## 6️⃣ إعداد MongoDB (قاعدة البيانات)

### الطريقة 1: MongoDB Cloud (موصى به - مجاني)

1. **اذهب إلى:** https://www.mongodb.com/cloud/atlas/register
2. **سجّل حساب جديد** (مجاني)
3. **أنشئ Cluster جديد** (اختر Free Tier)
4. **انتظر 3-5 دقائق** حتى يجهز
5. **اضغط Connect** → **Connect your application**
6. **انسخ Connection String**
7. **استبدل `<password>` بكلمة السر**
8. **الصق الرابط في `.env`**

**مثال:**
```
mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

### الطريقة 2: MongoDB محلي (للتجربة فقط)
```bash
# تثبيت MongoDB محلي
sudo apt install mongodb -y

# تشغيل الخدمة
sudo systemctl start mongodb
sudo systemctl enable mongodb

# استخدم في .env
MONGODB_URI=mongodb://localhost:27017/telegram_bot
```

---

## 7️⃣ الحصول على BOT_TOKEN

### إنشاء بوت جديد على Telegram:

1. **افتح Telegram** على الهاتف/حاسوب
2. **ابحث عن:** `@BotFather`
3. **أرسل:** `/newbot`
4. **أدخل اسم البوت:** `My Download Bot`
5. **أدخل username:** `mydownloadbot_123_bot` (يجب أن ينتهي بـ `_bot`)
6. **انسخ Token** الذي يظهر
7. **الصقه في `.env`**

**مثال Token:**
```
123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

---

## 8️⃣ الحصول على ADMIN_ID (معرّفك)

### الطريقة السهلة:

1. **افتح Telegram**
2. **ابحث عن:** `@userinfobot`
3. **أرسل:** `/start`
4. **انسخ Your ID**
5. **الصقه في `.env`**

**مثال:**
```
ADMIN_ID=384100534
```

---

## 9️⃣ تشغيل البوت 🚀

### التشغيل العادي:
```bash
# تأكد أن البيئة الافتراضية مفعّلة
source venv/bin/activate

# شغّل البوت
python3 bot.py
```

**يجب أن ترى:**
```
==================================================
🤖 بدء تشغيل البوت...
==================================================
✅ تم الاتصال بقاعدة البيانات بنجاح.
✅ تم تهيئة إعدادات المكتبات بنجاح
✅ تم تسجيل جميع المعالجات بنجاح.
==================================================
🔄 وضع Polling (محلي)
==================================================
```

### ✅ البوت يعمل الآن!

---

## 🔟 اختبار البوت

### 1. افتح Telegram
### 2. ابحث عن بوتك
### 3. أرسل: `/start`
### 4. جرب:
- اختر لغة
- أرسل رابط فيديو من YouTube
- جرب `/admin` لفتح لوحة التحكم

---

## 🛠️ تشغيل البوت في الخلفية (Background)

### استخدام screen (موصى به):

```bash
# تثبيت screen
sudo apt install screen -y

# إنشاء session جديد
screen -S telegram-bot

# شغّل البوت
source venv/bin/activate
python3 bot.py

# اخرج من screen (البوت يستمر في العمل)
اضغط: Ctrl + A ثم D

# للعودة للبوت
screen -r telegram-bot

# لإيقاف البوت
screen -r telegram-bot
اضغط: Ctrl + C
```

### أو استخدام nohup:
```bash
nohup python3 bot.py > bot.log 2>&1 &

# لإيقاف البوت
ps aux | grep bot.py
kill <PID>
```

---

## 📊 مراقبة البوت

### عرض السجلات (Logs):
```bash
# إذا كنت تستخدم screen
screen -r telegram-bot

# إذا كنت تستخدم nohup
tail -f bot.log

# أو
tail -f nohup.out
```

---

## ⚠️ حل المشاكل الشائعة

### ❌ خطأ: `ModuleNotFoundError: No module named 'telegram'`
```bash
# تأكد من تفعيل البيئة الافتراضية
source venv/bin/activate

# أعد تثبيت المكتبات
pip install -r requirements.txt
```

### ❌ خطأ: `MONGODB_URI غير موجود`
```bash
# تأكد من وجود ملف .env
ls -la | grep .env

# تحقق من محتوياته
cat .env
```

### ❌ خطأ: `Unauthorized`
```bash
# تأكد من صحة BOT_TOKEN في .env
nano .env
# تحقق من Token
```

### ❌ البوت لا يرد على الرسائل
```bash
# تحقق من السجلات
tail -f bot.log

# تأكد من أن البوت يعمل
ps aux | grep bot.py
```

---

## 🔄 تحديث البوت

### عند تحديث الملفات:
```bash
# إيقاف البوت
Ctrl + C

# تحديث yt-dlp
pip install --upgrade yt-dlp

# إعادة التشغيل
python3 bot.py
```

---

## 📝 ملخص الأوامر المهمة

### تشغيل البوت:
```bash
cd ~/Downloads/telegram-bot
source venv/bin/activate
python3 bot.py
```

### إيقاف البوت:
```
Ctrl + C
```

### تحديث المكتبات:
```bash
source venv/bin/activate
pip install --upgrade yt-dlp
pip install -r requirements.txt --upgrade
```

### عرض السجلات:
```bash
tail -f bot.log
```

---

## ✅ قائمة التحقق النهائية

- [ ] Python 3 مثبت
- [ ] pip مثبت
- [ ] ffmpeg مثبت
- [ ] البيئة الافتراضية مُنشأة
- [ ] المكتبات مثبتة
- [ ] ملف .env موجود
- [ ] BOT_TOKEN صحيح
- [ ] MONGODB_URI صحيح
- [ ] ADMIN_ID صحيح
- [ ] البوت يعمل بدون أخطاء
- [ ] `/start` يعمل على Telegram
- [ ] تحميل الفيديوهات يعمل

---

## 🎉 تهانينا!

البوت الآن يعمل على Xubuntu! 🚀

**إذا واجهت أي مشكلة، أرسل لي:**
1. الخطأ الظاهر في Terminal
2. محتوى السجلات (`tail -f bot.log`)
3. الخطوة التي فشلت عندها
