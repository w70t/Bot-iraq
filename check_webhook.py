#!/usr/bin/env python3
"""
سكريبت للتحقق من حالة الـ webhook وحذفه
Check webhook status and delete it
"""
import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

async def check_and_fix_webhook():
    load_dotenv()
    token = os.getenv('BOT_TOKEN')

    if not token:
        print("❌ BOT_TOKEN not found in .env file")
        return

    bot = Bot(token=token)

    try:
        # Check webhook info
        webhook_info = await bot.get_webhook_info()

        print("=" * 60)
        print("🔍 معلومات الـ Webhook / Webhook Info:")
        print("=" * 60)
        print(f"URL: {webhook_info.url}")
        print(f"Has Custom Certificate: {webhook_info.has_custom_certificate}")
        print(f"Pending Update Count: {webhook_info.pending_update_count}")
        print(f"Last Error Date: {webhook_info.last_error_date}")
        print(f"Last Error Message: {webhook_info.last_error_message}")
        print(f"Max Connections: {webhook_info.max_connections}")
        print("=" * 60)

        if webhook_info.url:
            print("\n⚠️ Webhook is set! This might cause conflicts.")
            print(f"📍 Webhook URL: {webhook_info.url}")

            # Delete webhook
            print("\n🔧 Deleting webhook...")
            result = await bot.delete_webhook(drop_pending_updates=True)

            if result:
                print("✅ Webhook deleted successfully!")
                print("✅ يمكنك الآن تشغيل البوت مرة أخرى")
            else:
                print("❌ Failed to delete webhook")
        else:
            print("\n✅ No webhook is set - using polling mode")
            print("🔍 Checking for other issues...")

            # Get bot info
            me = await bot.get_me()
            print(f"\n🤖 Bot Info:")
            print(f"   Name: {me.first_name}")
            print(f"   Username: @{me.username}")
            print(f"   ID: {me.id}")

            print("\n💡 المشكلة قد تكون:")
            print("   1. البوت يعمل على Railway أو خادم آخر")
            print("   2. هناك عملية أخرى تستخدم نفس التوكن")
            print("   3. انتظر 1-2 دقيقة ثم حاول مرة أخرى")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_and_fix_webhook())
