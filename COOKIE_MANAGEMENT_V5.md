# 🍪 Auto Cookie Management System V5.0 Ultra Secure Edition

## 📋 Overview

A fully automated, encrypted cookie management system for handling Facebook, Instagram, and TikTok authentication cookies directly inside Telegram with zero manual setup, automatic validation, and encrypted storage.

## ✨ Key Features

### 1️⃣ **Smart Auto-Detection**
- Automatically selects the right encrypted cookie file based on incoming links
- `facebook.com` → `/cookies_encrypted/facebook.enc`
- `instagram.com` → `/cookies_encrypted/instagram.enc`
- `tiktok.com` → `/cookies_encrypted/tiktok.enc`
- Alerts admin if cookies are missing or expired

### 2️⃣ **Secure Admin Upload**
- Upload raw cookie files directly in Telegram chat
- Automatic AES-256 encryption (Fernet)
- Instant validation after upload
- Secure deletion of unencrypted files

### 3️⃣ **Automatic Validation**
- Tests cookies immediately after upload
- Uses platform-specific test URLs
- Confirms story download access
- Auto-deletes invalid cookies

### 4️⃣ **Weekly Auto Check & Cleanup**
- Background task runs every Sunday at 00:00 UTC
- Validates all encrypted cookies
- Warns if cookies are older than 30 days
- Auto-deletes expired cookies
- Logs all events to `/logs/cookie_events.log`

### 5️⃣ **Admin Panel Integration**
- Full cookie management panel in bot
- View cookie status
- Test all cookies
- Test story downloads
- View encryption info
- Delete all cookies

### 6️⃣ **Automatic Weekly Backup**
- Creates encrypted ZIP backup every Sunday at 00:30 UTC
- Uploads to log channel automatically
- Includes date and SHA256 checksum
- Admin-only access

### 7️⃣ **Story Support**
- ✅ Instagram Stories, Reels, Highlights, Posts
- ✅ Facebook Stories, Videos, Posts, Groups
- ✅ TikTok Private/Following-only videos

### 8️⃣ **Security Design**
- AES-256 Fernet encryption
- Rotating key system
- Key stored in `cookie_key.json`
- Temporary files auto-deleted
- Admin-only operations
- All actions logged

## 📁 File Structure

```
handlers/
 ├── admin.py (Cookie Management Panel)
 ├── download.py (Auto-detection integration)
 └── cookie_manager.py (Core cookie logic)

cookies_encrypted/
 ├── facebook.enc
 ├── instagram.enc
 ├── tiktok.enc
 ├── facebook.json (metadata)
 ├── instagram.json (metadata)
 └── tiktok.json (metadata)

cookies/
 └── (temporary decrypted files - auto-deleted)

backups/
 └── cookies_encrypted_2025-11-18.zip

logs/
 └── cookie_events.log

cookie_key.json
```

## 🚀 How to Use

### For Admins

#### 1. Upload Cookies
1. Export cookies from your browser using a cookie export extension
2. Save as `facebook.txt`, `instagram.txt`, or `tiktok.txt`
3. Send the file directly to the bot in Telegram
4. Bot will automatically:
   - Detect platform
   - Encrypt with AES-256
   - Validate cookies
   - Confirm upload

#### 2. Access Cookie Management Panel
1. Open bot → `/admin`
2. Click "🍪 إدارة Cookies"
3. Options:
   - 📋 View detailed status
   - 🧪 Test all cookies
   - 📸 Test stories now
   - 🔐 View encryption info
   - 🗑️ Delete all cookies

#### 3. Weekly Maintenance
- System automatically checks cookies every Sunday
- You'll receive alerts for:
  - Cookies older than 30 days
  - Expired/invalid cookies
  - Auto-deleted cookies

### For Users

Users don't need to do anything! The bot will automatically:
- Detect the platform from their URL
- Use the appropriate encrypted cookies
- Download content including stories
- Alert if cookies are missing

## 🔧 Technical Details

### Cookie Priority Chain

For social media platforms (Facebook/Instagram/TikTok):

1. **Encrypted Cookies** (V5.0) - `/cookies_encrypted/{platform}.enc`
2. **Browser Cookies** - Chrome/Firefox cookies
3. **Platform-specific TXT** - `/cookies/{platform}.txt`
4. **General TXT** - `cookies.txt`

### Encryption

- **Algorithm**: AES-256 (Fernet)
- **Key Storage**: `cookie_key.json`
- **Key Rotation**: Supported (manual)
- **Temp File Lifetime**: < 1 second

### Validation Test URLs

- **Instagram**: `https://www.instagram.com/stories/highlights/`
- **Facebook**: `https://www.facebook.com/stories.php`
- **TikTok**: `https://www.tiktok.com/@scout2015/video/6718335390845095173`

### Weekly Schedule

- **Cookie Check**: Sunday 00:00 UTC
- **Cookie Backup**: Sunday 00:30 UTC

## 📝 Configuration

### Environment Variables

Ensure these are set in `.env`:

```env
# Admin IDs (required for weekly alerts)
ADMIN_IDS=123456789,987654321

# Log Channel (required for backups)
LOG_CHANNEL_ID=-1001234567890
```

### Dependencies

Added to `requirements.txt`:
```
cryptography>=42.0.0
```

Install with:
```bash
pip install -r requirements.txt
```

## 🧪 Testing Checklist

- [ ] Upload cookies for Instagram via bot
- [ ] Upload cookies for Facebook via bot
- [ ] Upload cookies for TikTok via bot
- [ ] Verify encryption in `/cookies_encrypted/`
- [ ] Test cookie status in admin panel
- [ ] Run story test (manual button)
- [ ] Download Instagram story with cookies
- [ ] Download Facebook video with cookies
- [ ] Download TikTok private video with cookies
- [ ] Check cookie events log
- [ ] Wait for weekly auto-check (or manually trigger)
- [ ] Check auto-backup in log channel

## 🛡️ Security Notes

1. **Never share `cookie_key.json`** - This is your master encryption key
2. **Keep `.env` secure** - Contains admin IDs
3. **Log channel should be private** - Backups contain encrypted cookies
4. **Cookies have expiry** - Usually 30-90 days depending on platform
5. **Re-upload regularly** - System warns after 30 days

## 🔍 Troubleshooting

### Cookie upload fails
- Check file format (must be Netscape cookies.txt format)
- Ensure file name contains platform name (facebook/instagram/tiktok)
- Verify you're logged in on the browser before exporting

### Download still fails after uploading cookies
- Test cookies using "🧪 اختبار جميع الـ Cookies" in admin panel
- Check cookie age (may have expired)
- Try re-exporting and uploading fresh cookies
- Check logs: `logs/cookie_events.log`

### Stories not working
- Use "📸 اختبار Stories الآن" to test story access
- Ensure cookies are from a logged-in session
- Some stories may be restricted even with cookies

### Weekly check not running
- Check bot logs for scheduler errors
- Verify `job_queue` is enabled in bot configuration
- Check system time/timezone

## 📚 Code References

- **Cookie Manager**: `handlers/cookie_manager.py`
- **Admin Panel**: `handlers/admin.py:2246-2415`
- **Auto-detection**: `handlers/download.py:499-560`
- **Weekly Scheduler**: `utils.py:1039-1147`
- **Bot Registration**: `bot.py:442-448` (upload handler), `bot.py:572-578` (scheduler)

## 🎯 Benefits

1. **Zero Manual Setup** - Everything in Telegram
2. **Military-Grade Security** - AES-256 encryption
3. **Automatic Maintenance** - Weekly checks and backups
4. **Story Support** - Download private/restricted content
5. **Multi-Platform** - Facebook, Instagram, TikTok
6. **Production Ready** - Comprehensive logging and error handling
7. **Admin Friendly** - Full control panel in bot

## 📊 Version History

### V5.0 Ultra Secure Edition (2025-11-11)
- ✅ Initial release
- ✅ AES-256 encryption
- ✅ Auto-detection and validation
- ✅ Weekly checks and backups
- ✅ Admin panel integration
- ✅ Story support
- ✅ Comprehensive logging

## 🔮 Future Enhancements

- [ ] Auto-refresh cookies using browser automation
- [ ] Multiple cookie sets per platform
- [ ] Cookie health monitoring dashboard
- [ ] Automatic cookie rotation
- [ ] Cross-platform cookie sharing
- [ ] Cookie expiry prediction

---

**Version**: 5.0 Ultra Secure Edition
**Date**: 2025-11-11
**Status**: Production Ready 🚀
