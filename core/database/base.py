import os
from pymongo import MongoClient
from datetime import datetime

# استخدام logger من config
try:
    from config.logger import get_logger
except ImportError:
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)

# الاتصال بقاعدة البيانات
MONGODB_URI = os.getenv("MONGODB_URI")

# ✅ دعم كلا الصيغتين: ADMIN_ID (أدمن واحد) و ADMIN_IDS (عدة أدمن)
ADMIN_ID_STR = os.getenv("ADMIN_ID", "")  # أدمن واحد
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")  # عدة أدمن

# Parse ADMIN_IDS safely - يدعم الصيغتين
try:
    ADMIN_IDS = []

    # إذا كان ADMIN_IDS موجود، استخدمه
    if ADMIN_IDS_STR:
        ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip().isdigit()]
    # إذا لم يكن موجود، استخدم ADMIN_ID
    elif ADMIN_ID_STR and ADMIN_ID_STR.isdigit():
        ADMIN_IDS = [int(ADMIN_ID_STR)]

    if not ADMIN_IDS:
        logger.warning("⚠️ No valid ADMIN_IDs found in .env. Admin functions will be disabled.")
    else:
        logger.info(f"✅ تم تحميل {len(ADMIN_IDS)} أدمن: {ADMIN_IDS}")

except (ValueError, AttributeError) as e:
    logger.error(f"❌ Failed to parse ADMIN_ID/ADMIN_IDS from .env: {e}")
    ADMIN_IDS = []

try:
    if not MONGODB_URI:
        raise ValueError("متغير البيئة MONGODB_URI غير موجود.")

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.server_info()

    db = client.telegram_bot
    users_collection = db.users
    settings_collection = db.settings

    logger.info("✅ تم الاتصال بقاعدة البيانات بنجاح.")
except Exception as e:
    logger.error(f"!!! خطأ في الاتصال بقاعدة البيانات: {e}")
    db = None
    users_collection = None
    settings_collection = None

    # إرسال تقرير خطأ جسيم
    try:
        from utils import send_critical_log
        send_critical_log(f"فشل الاتصال بقاعدة البيانات MongoDB: {str(e)}", module="database.py")
    except Exception as log_error:
        logger.error(f"فشل إرسال سجل الخطأ: {log_error}")


def init_db():
    """التحقق من الاتصال بقاعدة البيانات"""
    if db is None or users_collection is None:
        logger.error("!!! قاعدة البيانات غير متصلة.")
        return False
    return True


def ensure_db_connection():
    """التحقق من الاتصال بقاعدة البيانات مع إعادة المحاولة التلقائية"""
    global client, db, users_collection, settings_collection

    # إذا كانت المتغيرات غير مهيأة، محاولة إعادة الاتصال
    if db is None or users_collection is None or settings_collection is None:
        logger.warning("⚠️ Database connection lost, attempting reconnection...")
        try:
            # محاولة إعادة الاتصال
            if not MONGODB_URI:
                logger.error("❌ MONGODB_URI not configured")
                return False

            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            client.server_info()  # Test connection

            db = client.telegram_bot
            users_collection = db.users
            settings_collection = db.settings

            logger.info("✅ Database reconnection successful")
            return True
        except Exception as e:
            logger.error(f"❌ Database reconnection failed: {e}")
            try:
                from utils import send_critical_log
                send_critical_log(f"Database reconnection failed: {str(e)}", module="database.py")
            except:
                pass
            return False

    # التحقق من أن الاتصال ما زال حياً
    try:
        # Quick ping to verify connection is alive
        client.admin.command('ping')
        return True
    except Exception as e:
        logger.warning(f"⚠️ Database ping failed: {e}, attempting reconnection...")

        # محاولة إعادة الاتصال
        try:
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            client.server_info()  # Test connection

            db = client.telegram_bot
            users_collection = db.users
            settings_collection = db.settings

            logger.info("✅ Database reconnection successful after ping failure")
            return True
        except Exception as reconnect_error:
            logger.error(f"❌ Database reconnection failed: {reconnect_error}")
            try:
                from utils import send_critical_log
                send_critical_log(f"Database reconnection failed: {str(reconnect_error)}", module="database.py")
            except:
                pass
            return False
