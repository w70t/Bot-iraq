"""
ملف اللغات الشامل - جميع نصوص البوت بالعربية والإنجليزية
Comprehensive Language File - All bot texts in Arabic and English
"""

TEXTS = {
    "ar": {
        # رسائل الترحيب والبداية
        "welcome_first": "🎉 **أهلاً بك في بوت التحميل!**\n\n🌍 **اختر لغتك:**",
        "welcome_after_lang": "✨ **أهلاً {name}!**\n\n📥 يمكنك الآن تحميل الفيديوهات والصوتيات من جميع المنصات!\n\n📢 **تابع قناتنا الرسمية للتحديثات:**",
        "official_channel": "📢 قناة التحديثات الرسمية",
        "channel_link": "https://t.me/iraq_7kmmy",

        # قائمة الأزرار الرئيسية
        "download_video": "📥 تحميل فيديو",
        "download_audio": "🎧 تحميل صوت",
        "my_account": "👤 حسابي",
        "help": "❓ المساعدة",
        "vip_subscribe": "⭐ الاشتراك VIP",
        "support_creator": "🎁 دعم صاحب البوت",
        "change_language": "🌐 تغيير اللغة",

        # لوحة الاشتراك - الواجهة الرئيسية
        "subscription_panel_title": "💎 **لوحة التحكم بالاشتراك**",
        "subscription_panel_intro": "⚙️ **الإعدادات الحالية:**",
        "subscription_status": "📊 الحالة:",
        "subscription_enabled": "✅ مفعّل",
        "subscription_disabled": "❌ معطّل",
        "subscription_price": "💰 السعر الحالي:",
        "subscription_notifications": "🔔 إشعار المستخدمين:",
        "notifications_enabled": "✅ مفعّل",
        "notifications_disabled": "❌ معطّل",
        "choose_action": "\n\n📌 **اختر الإجراء المطلوب:**",

        # أزرار لوحة الاشتراك
        "btn_enable_subscription": "✅ تفعيل الاشتراك",
        "btn_disable_subscription": "❌ إيقاف الاشتراك",
        "btn_change_price": "💰 تغيير السعر",
        "btn_toggle_notifications": "🔔 تفعيل / تعطيل الإشعارات",
        "btn_back_to_main": "↩️ العودة للقائمة الرئيسية",

        # تأكيدات الإجراءات
        "confirm_enable_sub": "⚙️ **هل تريد بالتأكيد تفعيل نظام الاشتراك؟**\n\n✅ سيظهر زر الاشتراك VIP لجميع المستخدمين.",
        "confirm_disable_sub": "⚙️ **هل تريد بالتأكيد إيقاف نظام الاشتراك؟**\n\n❌ سيتم إخفاء زر الاشتراك من القائمة الرئيسية.",
        "confirm_toggle_notifications": "⚙️ **هل تريد تغيير حالة الإشعارات؟**",
        "btn_yes": "✅ نعم",
        "btn_no": "❌ لا",

        # نظام تغيير السعر
        "price_selection_title": "💰 **اختر السعر المناسب:**",
        "price_1": "1$ شهرياً",
        "price_3": "3$ شهرياً (موصى به)",
        "price_5": "5$ شهرياً",
        "price_custom": "💵 سعر مخصص",
        "enter_custom_price": "💵 **أدخل السعر المخصص:**\n\n📝 مثال: 7\n⚠️ أدخل رقم فقط (بالدولار)",
        "invalid_price": "❌ **السعر غير صحيح!**\n\n✅ أدخل رقم موجب (مثال: 3)",
        "price_updated": "✅ **تم تحديث السعر بنجاح!**\n\n💰 السعر الجديد: ${price} شهرياً",

        # رسائل النجاح والفشل
        "subscription_enabled_success": "✅ **تم تفعيل نظام الاشتراك بنجاح!**\n\n📢 سيظهر زر الاشتراك الآن لجميع المستخدمين.",
        "subscription_disabled_success": "❌ **تم إيقاف نظام الاشتراك!**\n\n🔒 تم إخفاء زر الاشتراك من القائمة الرئيسية.",
        "notifications_toggled": "🔔 **تم تغيير حالة الإشعارات!**",
        "action_cancelled": "❌ **تم إلغاء الإجراء**",
        "error_occurred": "❌ **حدث خطأ!** يرجى المحاولة مرة أخرى.",

        # رسائل VIP للمستخدمين
        "vip_plan_title": "👑 **باقة VIP المميزة!**",
        "vip_features": "✨ **المميزات:**",
        "vip_feature_unlimited": "♾️ تحميلات غير محدودة",
        "vip_feature_length": "⏱️ فيديوهات بأي طول",
        "vip_feature_nologo": "🎨 بدون لوجو",
        "vip_feature_quality": "📺 جودات عالية 4K/HD",
        "vip_feature_priority": "⚡ أولوية في المعالجة",
        "vip_feature_audio": "🎵 تحميل صوتي MP3",
        "vip_price_label": "💰 **السعر:**",
        "vip_contact": "📞 **للاشتراك، تواصل معنا:**\n📸 Instagram: @7kmmy\n🔗 https://instagram.com/7kmmy",
    },

    "en": {
        # Welcome and Start Messages
        "welcome_first": "🎉 **Welcome to Download Bot!**\n\n🌍 **Choose your language:**",
        "welcome_after_lang": "✨ **Welcome {name}!**\n\n📥 You can now download videos and audios from all platforms!\n\n📢 **Follow our official channel for updates:**",
        "official_channel": "📢 Official Updates Channel",
        "channel_link": "https://t.me/iraq_7kmmy",

        # Main Menu Buttons
        "download_video": "📥 Download Video",
        "download_audio": "🎧 Download Audio",
        "my_account": "👤 My Account",
        "help": "❓ Help",
        "vip_subscribe": "⭐ Subscribe VIP",
        "support_creator": "🎁 Support the Creator",
        "change_language": "🌐 Change Language",

        # Subscription Panel - Main Interface
        "subscription_panel_title": "💎 **Subscription Control Panel**",
        "subscription_panel_intro": "⚙️ **Current Settings:**",
        "subscription_status": "📊 Status:",
        "subscription_enabled": "✅ Enabled",
        "subscription_disabled": "❌ Disabled",
        "subscription_price": "💰 Current Price:",
        "subscription_notifications": "🔔 User Notifications:",
        "notifications_enabled": "✅ Enabled",
        "notifications_disabled": "❌ Disabled",
        "choose_action": "\n\n📌 **Choose an action:**",

        # Subscription Panel Buttons
        "btn_enable_subscription": "✅ Enable Subscription",
        "btn_disable_subscription": "❌ Disable Subscription",
        "btn_change_price": "💰 Change Price",
        "btn_toggle_notifications": "🔔 Toggle Notifications",
        "btn_back_to_main": "↩️ Back to Main Menu",

        # Action Confirmations
        "confirm_enable_sub": "⚙️ **Are you sure you want to enable the subscription system?**\n\n✅ VIP subscription button will be shown to all users.",
        "confirm_disable_sub": "⚙️ **Are you sure you want to disable the subscription system?**\n\n❌ VIP button will be hidden from the main menu.",
        "confirm_toggle_notifications": "⚙️ **Do you want to change notification status?**",
        "btn_yes": "✅ Yes",
        "btn_no": "❌ No",

        # Price Change System
        "price_selection_title": "💰 **Choose a suitable price:**",
        "price_1": "$1 monthly",
        "price_3": "$3 monthly (recommended)",
        "price_5": "$5 monthly",
        "price_custom": "💵 Custom price",
        "enter_custom_price": "💵 **Enter custom price:**\n\n📝 Example: 7\n⚠️ Enter numbers only (in USD)",
        "invalid_price": "❌ **Invalid price!**\n\n✅ Enter a positive number (example: 3)",
        "price_updated": "✅ **Price updated successfully!**\n\n💰 New price: ${price} monthly",

        # Success and Failure Messages
        "subscription_enabled_success": "✅ **Subscription system enabled successfully!**\n\n📢 VIP button is now visible to all users.",
        "subscription_disabled_success": "❌ **Subscription system disabled!**\n\n🔒 VIP button hidden from main menu.",
        "notifications_toggled": "🔔 **Notification status changed!**",
        "action_cancelled": "❌ **Action cancelled**",
        "error_occurred": "❌ **An error occurred!** Please try again.",

        # VIP Messages for Users
        "vip_plan_title": "👑 **VIP Premium Plan!**",
        "vip_features": "✨ **Features:**",
        "vip_feature_unlimited": "♾️ Unlimited downloads",
        "vip_feature_length": "⏱️ Any video length",
        "vip_feature_nologo": "🎨 No watermark",
        "vip_feature_quality": "📺 High quality 4K/HD",
        "vip_feature_priority": "⚡ Priority processing",
        "vip_feature_audio": "🎵 MP3 audio download",
        "vip_price_label": "💰 **Price:**",
        "vip_contact": "📞 **To subscribe, contact us:**\n📸 Instagram: @7kmmy\n🔗 https://instagram.com/7kmmy",
    }
}

def get_text(lang: str, key: str, **kwargs) -> str:
    """
    الحصول على نص محدد حسب اللغة
    Get specific text based on language

    Args:
        lang: Language code ('ar' or 'en')
        key: Text key
        **kwargs: Format parameters

    Returns:
        Formatted text string
    """
    try:
        text = TEXTS.get(lang, TEXTS['ar']).get(key, key)
        if kwargs:
            text = text.format(**kwargs)
        return text
    except Exception as e:
        return key
