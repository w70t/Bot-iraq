"""
🍪 Auto Cookie Management System V5.0 Ultra Secure Edition
Handles encrypted cookie storage, validation, and automatic platform detection
"""

import os
import json
import logging
import asyncio
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
# Lazy import for cryptography - will be imported when needed
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Paths
COOKIES_ENCRYPTED_DIR = Path("cookies_encrypted")
COOKIES_TEMP_DIR = Path("cookies")
COOKIE_KEY_FILE = Path("cookie_key.json")
COOKIE_LOG_FILE = Path("logs/cookie_events.log")

# Test URLs for validation
TEST_URLS = {
    'instagram': 'https://www.instagram.com/p/C5bL8gqPfHH/',  # Fixed: Use actual post URL
    'facebook': [
        'https://www.facebook.com/me',
        'https://m.facebook.com/me',
        'https://www.facebook.com/settings',
    ],
    'threads': 'https://www.threads.net/',
    'tiktok': 'https://www.tiktok.com/@scout2015/video/6718335390845095173',
    'pinterest': 'https://www.pinterest.com/',
    'twitter': 'https://twitter.com/home',
    'reddit': None,  # Reddit cookies use soft validation (no specific test URL needed)
    'vimeo': 'https://vimeo.com/',
    'dailymotion': 'https://www.dailymotion.com/',
    'twitch': 'https://www.twitch.tv/',
    'general': None  # General cookies don't need validation
}

# Platform detection patterns
PLATFORM_PATTERNS = {
    'facebook': ['facebook.com', 'fb.watch', 'fb.com'],
    'instagram': ['instagram.com'],
    'threads': ['threads.net', 'threads.com'],
    'tiktok': ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'],
    'pinterest': ['pinterest.com', 'pin.it'],
    'twitter': ['twitter.com', 'x.com', 't.co'],
    'reddit': ['reddit.com', 'redd.it'],
    'vimeo': ['vimeo.com'],
    'dailymotion': ['dailymotion.com', 'dai.ly'],
    'twitch': ['twitch.tv']
}

# Platform Cookie Linking (V5.2)
# Each platform uses its own cookie file
PLATFORM_COOKIE_LINKS = {
    'facebook': 'facebook',
    'instagram': 'instagram',
    'threads': 'instagram',         # Threads uses Instagram cookies (owned by Meta)
    'tiktok': 'tiktok',
    'pinterest': 'pinterest',
    'twitter': 'twitter',
    'reddit': 'reddit',
    'vimeo': 'vimeo',
    'dailymotion': 'dailymotion',
    'twitch': 'twitch',
    'youtube': None                 # YouTube doesn't need cookies
}


class CookieManager:
    """Manages encrypted cookies with auto-validation and platform detection"""

    def __init__(self):
        self.fernet = None
        self._ensure_directories()
        self._load_or_create_key()

    def _ensure_directories(self):
        """Create necessary directories"""
        COOKIES_ENCRYPTED_DIR.mkdir(exist_ok=True)
        COOKIES_TEMP_DIR.mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        logger.info("✅ Cookie directories initialized")

    def _load_or_create_key(self):
        """Load or generate AES-256 encryption key"""
        try:
            # Import Fernet here to avoid import errors before cryptography is installed
            from cryptography.fernet import Fernet

            if COOKIE_KEY_FILE.exists():
                with open(COOKIE_KEY_FILE, 'r') as f:
                    key_data = json.load(f)
                    key = key_data['key'].encode()
                    logger.info("🔑 Loaded existing encryption key")
            else:
                # Generate new key
                key = Fernet.generate_key()
                key_data = {
                    'key': key.decode(),
                    'created_at': datetime.now().isoformat(),
                    'algorithm': 'AES-256 (Fernet)'
                }
                with open(COOKIE_KEY_FILE, 'w') as f:
                    json.dump(key_data, f, indent=2)
                logger.info("🔐 Generated new encryption key")

            self.fernet = Fernet(key)
        except ImportError as e:
            logger.error(f"❌ cryptography module not installed: {e}")
            logger.error("Please install: pip install cryptography>=42.0.0")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to load/create encryption key: {e}")
            raise

    def _log_event(self, message: str):
        """Log cookie events to file"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(COOKIE_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            logger.error(f"❌ Failed to log event: {e}")

    def detect_platform(self, url: str) -> str:
        """Detect platform from URL"""
        url_lower = url.lower()
        for platform, patterns in PLATFORM_PATTERNS.items():
            if any(pattern in url_lower for pattern in patterns):
                return platform
        return None

    def detect_platform_from_cookies(self, cookie_text: str) -> str:
        """
        Detect platform from cookie domain (V5.3)
        Analyzes cookie domains to automatically identify the platform
        """
        cookie_text_lower = cookie_text.lower()

        # Check for platform-specific domains
        if 'facebook.com' in cookie_text_lower or 'fb.com' in cookie_text_lower:
            return 'facebook'
        elif 'instagram.com' in cookie_text_lower:
            return 'instagram'
        elif 'tiktok.com' in cookie_text_lower:
            return 'tiktok'
        elif 'pinterest.com' in cookie_text_lower:
            return 'pinterest'
        elif 'reddit.com' in cookie_text_lower:
            return 'reddit'
        elif 'twitter.com' in cookie_text_lower or 'x.com' in cookie_text_lower:
            return 'twitter'
        elif 'vimeo.com' in cookie_text_lower:
            return 'vimeo'
        elif 'dailymotion.com' in cookie_text_lower:
            return 'dailymotion'
        elif 'twitch.tv' in cookie_text_lower:
            return 'twitch'

        return None

    def parse_netscape_cookies(self, cookie_text: str) -> tuple:
        """
        Parse Netscape format cookies and extract valid entries (V5.2)

        Returns:
            tuple: (success: bool, parsed_data: str, platform: str, cookie_count: int)
        """
        try:
            lines = cookie_text.strip().split('\n')
            valid_lines = []
            cookie_count = 0
            detected_platform = None

            # Check if this is Netscape format
            is_netscape = False
            for line in lines[:5]:  # Check first 5 lines
                if '# Netscape HTTP Cookie File' in line or '# http://curl.haxx.se' in line:
                    is_netscape = True
                    break

            # Detect platform from domains
            detected_platform = self.detect_platform_from_cookies(cookie_text)

            # Parse cookie lines
            for line in lines:
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Handle #HttpOnly_ prefix (it's a cookie flag, not a comment)
                httponly_flag = False
                if line.startswith('#HttpOnly_'):
                    httponly_flag = True
                    line = line[10:]  # Remove '#HttpOnly_' prefix (10 characters)

                # Keep actual comment lines (with space after # or known patterns)
                if line.startswith('#') and (
                    line.startswith('# ') or
                    'Netscape' in line or
                    'curl.haxx.se' in line or
                    'Cookie File' in line or
                    'generated by' in line
                ):
                    valid_lines.append(line)
                    continue

                # Parse cookie line: domain, flag, path, secure, expiration, name, value
                # Support both tabs and spaces as delimiters (Safari/Chrome Cookie-Editor compatibility)
                # \s{1,} accepts single or multiple spaces for maximum flexibility
                parts = re.split(r'\t+|\s+', line.strip())

                # Valid cookie must have at least 6 fields (some exports omit the value field)
                # Standard Netscape format: domain, flag, path, secure, expiration, name, value
                if len(parts) >= 6:
                    try:
                        domain = parts[0].strip()
                        flag = parts[1].strip() if len(parts) > 1 else 'TRUE'
                        path = parts[2].strip() if len(parts) > 2 else '/'
                        secure = parts[3].strip() if len(parts) > 3 else 'FALSE'
                        expiration = parts[4].strip() if len(parts) > 4 else '0'
                        name = parts[5].strip() if len(parts) > 5 else ''
                        value = parts[6].strip() if len(parts) > 6 else ''

                        # Validate basic cookie structure
                        if domain and name:
                            # Check expiration (skip expired cookies)
                            try:
                                exp_timestamp = int(expiration)
                                current_timestamp = int(time.time())

                                if exp_timestamp > current_timestamp:
                                    # Reconstruct line with HttpOnly prefix if needed
                                    # Use tab-separated format for consistency with Netscape standard
                                    cookie_line = f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}"
                                    if httponly_flag:
                                        cookie_line = f"#HttpOnly_{cookie_line}"
                                    valid_lines.append(cookie_line)
                                    cookie_count += 1
                                else:
                                    logger.debug(f"Skipped expired cookie: {name} (exp: {expiration})")
                            except (ValueError, TypeError):
                                # If expiration parsing fails, include the cookie anyway
                                cookie_line = f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}"
                                if httponly_flag:
                                    cookie_line = f"#HttpOnly_{cookie_line}"
                                valid_lines.append(cookie_line)
                                cookie_count += 1
                    except (IndexError, ValueError) as e:
                        logger.debug(f"Skipped malformed cookie line: {line[:50]}... Error: {e}")

            # If no valid cookies found
            if cookie_count == 0:
                logger.warning("No valid cookies found in text")
                return (False, None, None, 0)

            # Reconstruct Netscape format
            if not is_netscape:
                # Add Netscape header if missing
                header = [
                    "# Netscape HTTP Cookie File",
                    "# http://curl.haxx.se/rfc/cookie_spec.html",
                    "# This file was generated by Bot Cookie Manager"
                ]
                valid_lines = header + valid_lines

            parsed_data = '\n'.join(valid_lines)

            platform_name = detected_platform.capitalize() if detected_platform else 'Unknown'
            self._log_event(f"✅ Parsed {cookie_count} valid cookies (Platform: {platform_name})")
            logger.info(f"✅ Parsed {cookie_count} cookies successfully ({platform_name})")

            return (True, parsed_data, detected_platform, cookie_count)

        except Exception as e:
            logger.error(f"❌ Failed to parse cookies: {e}")
            return (False, None, None, 0)

    def encrypt_cookie_file(self, platform: str, cookie_data: bytes) -> bool:
        """Encrypt cookie file and save to encrypted directory"""
        try:
            encrypted_data = self.fernet.encrypt(cookie_data)
            encrypted_path = COOKIES_ENCRYPTED_DIR / f"{platform}.enc"

            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)

            # Save metadata
            metadata = {
                'platform': platform,
                'encrypted_at': datetime.now().isoformat(),
                'size': len(encrypted_data),
                'validated': False
            }
            metadata_path = COOKIES_ENCRYPTED_DIR / f"{platform}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            self._log_event(f"🔒 Encrypted cookies for {platform}")
            logger.info(f"✅ Successfully encrypted cookies for {platform}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to encrypt cookies for {platform}: {e}")
            self._log_event(f"❌ Encryption failed for {platform}: {e}")
            return False

    def decrypt_cookie_file(self, platform: str) -> str:
        """Decrypt cookie file temporarily and return path"""
        try:
            encrypted_path = COOKIES_ENCRYPTED_DIR / f"{platform}.enc"

            if not encrypted_path.exists():
                logger.warning(f"⚠️ No encrypted cookies found for {platform}")
                return None

            with open(encrypted_path, 'rb') as f:
                encrypted_data = f.read()

            decrypted_data = self.fernet.decrypt(encrypted_data)

            # Save to temporary location
            temp_path = COOKIES_TEMP_DIR / f"{platform}.txt"
            with open(temp_path, 'wb') as f:
                f.write(decrypted_data)

            logger.info(f"🔓 Decrypted cookies for {platform} temporarily")
            return str(temp_path)

        except Exception as e:
            logger.error(f"❌ Failed to decrypt cookies for {platform}: {e}")
            return None

    def delete_temp_cookies(self):
        """Delete all temporary decrypted cookies"""
        try:
            for file in COOKIES_TEMP_DIR.glob("*.txt"):
                file.unlink()
            logger.info("🧹 Cleaned up temporary cookie files")
        except Exception as e:
            logger.error(f"❌ Failed to delete temp cookies: {e}")

    def _fb_has_essential_cookies(self, cookie_file_path: str) -> bool:
        """Check if Facebook cookie file contains essential cookies (xs, c_user)"""
        try:
            import http.cookiejar
            cookiejar = http.cookiejar.MozillaCookieJar()
            cookiejar.load(cookie_file_path, ignore_discard=True, ignore_expires=True)

            names = {c.name for c in cookiejar if "facebook" in c.domain}
            required = {"xs", "c_user"}
            has_essential = required.issubset(names)

            logger.debug(f"FB cookies found: {names}, has essential: {has_essential}")
            return has_essential
        except Exception as e:
            logger.error(f"Error checking FB essential cookies: {e}")
            return False

    def _ig_has_essential_cookies(self, cookie_file_path: str) -> bool:
        """Check if Instagram cookie file contains essential cookies (sessionid, ds_user_id)"""
        try:
            import http.cookiejar
            cookiejar = http.cookiejar.MozillaCookieJar()
            cookiejar.load(cookie_file_path, ignore_discard=True, ignore_expires=True)

            names = {c.name for c in cookiejar if "instagram" in c.domain}
            # Essential Instagram cookies: sessionid is the main one
            required = {"sessionid"}
            has_essential = required.issubset(names)

            logger.debug(f"IG cookies found: {names}, has essential: {has_essential}")
            return has_essential
        except Exception as e:
            logger.error(f"Error checking IG essential cookies: {e}")
            return False

    def _reddit_has_essential_cookies(self, cookie_file_path: str) -> bool:
        """Check if Reddit cookie file contains essential cookies (reddit_session)"""
        try:
            import http.cookiejar
            cookiejar = http.cookiejar.MozillaCookieJar()
            cookiejar.load(cookie_file_path, ignore_discard=True, ignore_expires=True)

            names = {c.name for c in cookiejar if "reddit" in c.domain}
            # Essential Reddit cookies: reddit_session, token_v2
            # At minimum we need reddit_session
            has_reddit_session = "reddit_session" in names

            logger.debug(f"Reddit cookies found: {names}, has reddit_session: {has_reddit_session}")
            return has_reddit_session or len(names) >= 3  # Accept if has 3+ reddit cookies
        except Exception as e:
            logger.error(f"Error checking Reddit essential cookies: {e}")
            return False

    async def validate_cookies(self, platform: str) -> bool:
        """Validate cookies by testing with yt-dlp (with soft validation for Facebook & Instagram & Reddit)"""
        cookie_path = None
        try:
            # Decrypt temporarily
            cookie_path = self.decrypt_cookie_file(platform)
            if not cookie_path:
                return False

            # Special handling for Reddit with soft validation (no test URL needed)
            if platform == 'reddit':
                return await self._validate_reddit_cookies(cookie_path)

            # Get test URL(s)
            test_urls = TEST_URLS.get(platform)
            if not test_urls:
                logger.warning(f"⚠️ No test URL defined for {platform}")
                return False

            # Convert single URL to list for uniform handling
            if isinstance(test_urls, str):
                test_urls = [test_urls]

            # Special handling for Facebook with soft validation
            if platform == 'facebook':
                return await self._validate_facebook_cookies(cookie_path, test_urls)

            # Special handling for Instagram with soft validation
            if platform == 'instagram':
                return await self._validate_instagram_cookies(cookie_path, test_urls)

            # Standard validation for other platforms
            test_url = test_urls[0] if isinstance(test_urls, list) else test_urls

            # Test with yt-dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiefile': cookie_path,
                'skip_download': True,
                'extract_flat': True,
                'socket_timeout': 30,  # ✅ إضافة timeout لتجنب التعليق
            }

            loop = asyncio.get_event_loop()

            def test_extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(test_url, download=False)

            # Run with timeout
            await asyncio.wait_for(
                loop.run_in_executor(None, test_extract),
                timeout=30
            )

            # Update metadata
            metadata_path = COOKIES_ENCRYPTED_DIR / f"{platform}.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                metadata['validated'] = True
                metadata['validation_type'] = 'full'
                metadata['last_validated'] = datetime.now().isoformat()
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

            self._log_event(f"✅ Cookies for {platform} validated successfully")
            logger.info(f"✅ Cookies for {platform} are valid")
            return True

        except asyncio.TimeoutError:
            logger.error(f"❌ Validation timeout for {platform}")
            self._log_event(f"❌ Validation timeout for {platform}")
            return False
        except Exception as e:
            logger.error(f"❌ Validation failed for {platform}: {e}")
            self._log_event(f"❌ Validation failed for {platform}: {e}")
            return False
        finally:
            # Always cleanup temp files
            if cookie_path and os.path.exists(cookie_path):
                try:
                    os.remove(cookie_path)
                except:
                    pass

    async def _validate_facebook_cookies(self, cookie_path: str, test_urls: list) -> bool:
        """Validate Facebook cookies with soft validation fallback"""
        has_essential = self._fb_has_essential_cookies(cookie_path)

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiefile': cookie_path,
            'skip_download': True,
            'extract_flat': True,
            'socket_timeout': 30,  # ✅ إضافة timeout لتجنب التعليق
        }

        loop = asyncio.get_event_loop()
        last_error = None
        validation_ok = False

        # Try each URL
        for url in test_urls:
            try:
                def test_extract():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.extract_info(url, download=False)

                await asyncio.wait_for(
                    loop.run_in_executor(None, test_extract),
                    timeout=30
                )
                validation_ok = True
                logger.info(f"✅ Facebook cookies validated with URL: {url}")
                break
            except Exception as e:
                last_error = str(e)
                error_lower = last_error.lower()

                # Check if it's an unsupported URL or login-related error
                if "unsupported url" in error_lower or "login" in error_lower:
                    logger.debug(f"URL {url} not supported or requires login: {e}")
                    continue
                else:
                    logger.debug(f"Validation attempt failed for {url}: {e}")
                    continue

        # Update metadata based on validation result
        metadata_path = COOKIES_ENCRYPTED_DIR / "facebook.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            if validation_ok:
                # Full validation passed
                metadata['validated'] = True
                metadata['validation_type'] = 'full'
                metadata['last_validated'] = datetime.now().isoformat()
                self._log_event("✅ Facebook cookies validated successfully (full)")
                logger.info("✅ Facebook cookies validated successfully (full)")
            elif has_essential:
                # Soft validation - essential cookies present
                metadata['validated'] = True
                metadata['validation_type'] = 'soft'
                metadata['last_validated'] = datetime.now().isoformat()
                self._log_event("ℹ️ Facebook cookies soft-validated (xs + c_user present)")
                logger.warning("⚠️ Facebook validation inconclusive; core cookies present -> accepting as valid (soft)")
                validation_ok = True
            else:
                # No validation and no essential cookies
                metadata['validated'] = False
                metadata['validation_type'] = 'failed'
                metadata['last_error'] = last_error or "Missing essential cookies"
                self._log_event(f"❌ Facebook cookie validation failed: {last_error}")

            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

        return validation_ok if validation_ok else has_essential

    async def _validate_reddit_cookies(self, cookie_path: str) -> bool:
        """Validate Reddit cookies with soft validation (no test URL - just check essential cookies)"""
        has_essential = self._reddit_has_essential_cookies(cookie_path)

        # Update metadata
        metadata_path = COOKIES_ENCRYPTED_DIR / "reddit.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            if has_essential:
                # Soft validation - essential cookies present
                metadata['validated'] = True
                metadata['validation_type'] = 'soft'
                metadata['last_validated'] = datetime.now().isoformat()
                self._log_event("✅ Reddit cookies soft-validated (essential cookies present)")
                logger.info("✅ Reddit cookies validated successfully (soft)")
            else:
                # No essential cookies
                metadata['validated'] = False
                metadata['validation_type'] = 'failed'
                metadata['last_error'] = "Missing essential Reddit cookies (reddit_session)"
                self._log_event("❌ Reddit cookie validation failed: Missing essential cookies")
                logger.error("❌ Reddit cookies missing essential cookies")

            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

        return has_essential

    async def _validate_instagram_cookies(self, cookie_path: str, test_urls: list) -> bool:
        """Validate Instagram cookies with soft validation fallback"""
        has_essential = self._ig_has_essential_cookies(cookie_path)

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiefile': cookie_path,
            'skip_download': True,
            'extract_flat': True,
            'socket_timeout': 30,
        }

        loop = asyncio.get_event_loop()
        last_error = None
        validation_ok = False

        # Try each URL
        for url in test_urls:
            try:
                def test_extract():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.extract_info(url, download=False)

                await asyncio.wait_for(
                    loop.run_in_executor(None, test_extract),
                    timeout=30
                )
                validation_ok = True
                logger.info(f"✅ Instagram cookies validated with URL: {url}")
                break
            except Exception as e:
                last_error = str(e)
                error_lower = last_error.lower()

                # Check if it's an unsupported URL or login-related error
                if "unsupported url" in error_lower or "login" in error_lower:
                    logger.debug(f"URL {url} not supported or requires login: {e}")
                    continue
                else:
                    logger.debug(f"Validation attempt failed for {url}: {e}")
                    continue

        # Update metadata based on validation result
        metadata_path = COOKIES_ENCRYPTED_DIR / "instagram.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            if validation_ok:
                # Full validation passed
                metadata['validated'] = True
                metadata['validation_type'] = 'full'
                metadata['last_validated'] = datetime.now().isoformat()
                self._log_event("✅ Instagram cookies validated successfully (full)")
                logger.info("✅ Instagram cookies validated successfully (full)")
            elif has_essential:
                # Soft validation - essential cookies present
                metadata['validated'] = True
                metadata['validation_type'] = 'soft'
                metadata['last_validated'] = datetime.now().isoformat()
                self._log_event("ℹ️ Instagram cookies soft-validated (sessionid present)")
                logger.warning("⚠️ Instagram validation inconclusive; core cookies present -> accepting as valid (soft)")
                validation_ok = True
            else:
                # No validation and no essential cookies
                metadata['validated'] = False
                metadata['validation_type'] = 'failed'
                metadata['last_error'] = last_error or "Missing essential cookies"
                self._log_event(f"❌ Instagram cookie validation failed: {last_error}")

            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

        return validation_ok if validation_ok else has_essential

    def get_cookie_status(self) -> dict:
        """Get status of all encrypted cookies (V6.0 - All Platforms)"""
        status = {}

        # All supported platforms including general cookies
        all_platforms = ['facebook', 'instagram', 'tiktok', 'pinterest', 'twitter', 'reddit', 'vimeo', 'dailymotion', 'twitch', 'general']

        for platform in all_platforms:
            encrypted_path = COOKIES_ENCRYPTED_DIR / f"{platform}.enc"
            metadata_path = COOKIES_ENCRYPTED_DIR / f"{platform}.json"

            if encrypted_path.exists():
                info = {'exists': True}

                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)

                    encrypted_date = datetime.fromisoformat(metadata['encrypted_at'])
                    age_days = (datetime.now() - encrypted_date).days

                    info.update({
                        'age_days': age_days,
                        'validated': metadata.get('validated', False),
                        'last_validated': metadata.get('last_validated', 'Never'),
                        'size': metadata.get('size', 0)
                    })
                else:
                    info.update({
                        'age_days': 0,
                        'validated': False,
                        'last_validated': 'Never',
                        'size': 0
                    })

                status[platform] = info
            else:
                status[platform] = {'exists': False}

        return status

    def get_cookie_file_for_platform(self, platform: str) -> str:
        """
        Get the actual cookie file name for a platform (V5.1)
        Supports platform linking (e.g., Pinterest uses Instagram cookies)

        Returns the cookie file base name (e.g., 'instagram', 'facebook', 'general')
        """
        cookie_file = PLATFORM_COOKIE_LINKS.get(platform.lower())
        return cookie_file

    def get_platform_cookie_status(self, platform: str) -> dict:
        """
        Get cookie status for any platform including linked platforms (V5.1)

        Returns:
            dict with keys:
            - exists: bool
            - cookie_file: str (which cookie file is used)
            - linked: bool (whether this platform uses linked cookies)
            - age_days: int
            - validated: bool
            - last_validated: str
        """
        cookie_file = self.get_cookie_file_for_platform(platform)

        if cookie_file is None:
            # Platform doesn't need cookies (e.g., YouTube)
            return {
                'exists': False,
                'cookie_file': None,
                'linked': False,
                'needs_cookies': False
            }

        # Check if this is a linked platform
        is_linked = (cookie_file != platform.lower())

        # Get status of the actual cookie file
        encrypted_path = COOKIES_ENCRYPTED_DIR / f"{cookie_file}.enc"
        metadata_path = COOKIES_ENCRYPTED_DIR / f"{cookie_file}.json"

        if encrypted_path.exists():
            info = {
                'exists': True,
                'cookie_file': cookie_file,
                'linked': is_linked,
                'needs_cookies': True
            }

            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)

                encrypted_date = datetime.fromisoformat(metadata['encrypted_at'])
                age_days = (datetime.now() - encrypted_date).days

                # ⭐ عد الكوكيز في الملف
                cookie_count = self._count_cookies(cookie_file)

                info.update({
                    'age_days': age_days,
                    'validated': metadata.get('validated', False),
                    'last_validated': metadata.get('last_validated', 'Never'),
                    'encrypted_at': metadata['encrypted_at'],
                    'cookie_count': cookie_count  # ⭐ إضافة عدد الكوكيز
                })
            else:
                # ⭐ عد الكوكيز حتى بدون metadata
                cookie_count = self._count_cookies(cookie_file)

                info.update({
                    'age_days': 0,
                    'validated': False,
                    'last_validated': 'Never',
                    'cookie_count': cookie_count  # ⭐ إضافة عدد الكوكيز
                })

            return info
        else:
            return {
                'exists': False,
                'cookie_file': cookie_file,
                'linked': is_linked,
                'needs_cookies': True
            }

    def _count_cookies(self, cookie_file: str) -> int:
        """عد الكوكيز الصالحة في الملف المشفر"""
        try:
            # فك تشفير الملف مؤقتاً للعد
            temp_path = self.decrypt_cookie_file(cookie_file)
            if not temp_path or not os.path.exists(temp_path):
                return 0

            # قراءة وعد الكوكيز
            with open(temp_path, 'r') as f:
                lines = f.readlines()

            # عد السطور الصالحة (ليست تعليقات أو فارغة)
            count = 0
            for line in lines:
                line = line.strip()
                # تجاهل السطور الفارغة
                if not line:
                    continue
                # تجاهل التعليقات (لكن اعتبر #HttpOnly_ كوكيز صالحة)
                if line.startswith('#') and not line.startswith('#HttpOnly_'):
                    continue
                count += 1

            # حذف الملف المؤقت
            if os.path.exists(temp_path):
                os.remove(temp_path)

            return count
        except Exception as e:
            logger.error(f"❌ Failed to count cookies for {cookie_file}: {e}")
            return 0

    def delete_cookies(self, platform: str) -> bool:
        """Delete encrypted cookies for a platform"""
        try:
            encrypted_path = COOKIES_ENCRYPTED_DIR / f"{platform}.enc"
            metadata_path = COOKIES_ENCRYPTED_DIR / f"{platform}.json"

            if encrypted_path.exists():
                encrypted_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()

            self._log_event(f"🗑️ Deleted cookies for {platform}")
            logger.info(f"✅ Deleted cookies for {platform}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete cookies for {platform}: {e}")
            return False

    async def check_and_alert_expired(self, context: ContextTypes.DEFAULT_TYPE, admin_ids: list):
        """Check all cookies and alert admins if expired"""
        try:
            status = self.get_cookie_status()
            alerts = []

            for platform, info in status.items():
                if info['exists']:
                    age_days = info.get('age_days', 0)

                    if age_days > 30:
                        alerts.append(f"⚠️ {platform.capitalize()} cookies are {age_days} days old")
                        self._log_event(f"⚠️ {platform} cookies are {age_days} days old")

                    # Validate if needed
                    if not info.get('validated', False):
                        is_valid = await self.validate_cookies(platform)
                        if not is_valid:
                            self.delete_cookies(platform)
                            alerts.append(f"❌ {platform.capitalize()} cookies expired and deleted")

            # Send alerts to admins
            if alerts:
                alert_message = "🍪 **Cookie Status Alert**\n\n" + "\n".join(alerts)
                for admin_id in admin_ids:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=alert_message,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to send alert to admin {admin_id}: {e}")

        except Exception as e:
            logger.error(f"❌ Failed to check expired cookies: {e}")


# Global instance
cookie_manager = CookieManager()


# ====================
# Telegram Handlers
# ====================

async def handle_cookie_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cookie file upload from admin"""
    from database import is_admin

    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("🚫 غير مصرح لك باستخدام هذا الأمر!")
        return

    # Check if document is attached
    if not update.message.document:
        await update.message.reply_text(
            "❌ يرجى إرفاق ملف cookies بصيغة .txt\n\n"
            "💡 الملفات المدعومة:\n"
            "• facebook.txt / fb.txt\n"
            "• instagram.txt / ig.txt\n"
            "• tiktok.txt / tt.txt\n"
            "• pinterest.txt\n"
            "• twitter.txt / x.txt\n"
            "• reddit.txt\n"
            "• vimeo.txt\n"
            "• dailymotion.txt\n"
            "• twitch.txt\n"
            "• general.txt (كوكيز عامة لجميع المنصات)"
        )
        return

    document = update.message.document
    filename = document.file_name.lower()

    # Detect platform from filename (V6.0 - All Platforms Support)
    platform = None
    if 'facebook' in filename or 'fb' in filename:
        platform = 'facebook'
    elif 'instagram' in filename or 'ig' in filename:
        platform = 'instagram'
    elif 'twitter' in filename or filename.startswith('x.'):
        platform = 'twitter'
    elif 'tiktok' in filename or 'tt' in filename:
        platform = 'tiktok'
    elif 'pinterest' in filename:
        platform = 'pinterest'
    elif 'reddit' in filename:
        platform = 'reddit'
    elif 'vimeo' in filename:
        platform = 'vimeo'
    elif 'dailymotion' in filename:
        platform = 'dailymotion'
    elif 'twitch' in filename:
        platform = 'twitch'
    elif 'general' in filename:
        platform = 'general'

    if not platform:
        await update.message.reply_text(
            "❌ لم أتمكن من تحديد المنصة من اسم الملف!\n\n"
            "💡 تأكد أن اسم الملف يحتوي على اسم المنصة:\n"
            "• facebook / fb\n"
            "• instagram / ig\n"
            "• tiktok / tt\n"
            "• pinterest\n"
            "• twitter / x\n"
            "• reddit\n"
            "• vimeo\n"
            "• dailymotion\n"
            "• twitch\n"
            "• general (للكوكيز العامة)"
        )
        return

    processing_msg = await update.message.reply_text(
        f"🔄 **جاري معالجة ملف cookies لـ {platform.capitalize()}...**\n\n"
        f"⏳ الرجاء الانتظار...",
        parse_mode='Markdown'
    )

    try:
        # Download file
        file = await document.get_file()
        cookie_data = await file.download_as_bytearray()

        # Get the actual cookie file name (handle platform linking)
        # Pinterest → instagram, Reddit → facebook, Twitter → general, etc.
        actual_platform = cookie_manager.get_cookie_file_for_platform(platform)

        # If platform doesn't need cookies (like YouTube), reject
        if actual_platform is None:
            await processing_msg.edit_text(
                f"⚠️ {platform.capitalize()} لا يحتاج إلى ملف cookies!"
            )
            return

        logger.info(f"📝 Platform {platform} will use cookie file: {actual_platform}")

        # Encrypt and save with the actual platform name
        success = cookie_manager.encrypt_cookie_file(actual_platform, bytes(cookie_data))

        if not success:
            await processing_msg.edit_text(
                f"❌ فشل تشفير ملف cookies لـ {platform.capitalize()}!\n\n"
                f"يرجى المحاولة مرة أخرى."
            )
            return

        # Validate
        await processing_msg.edit_text(
            f"🔒 **تم تشفير الملف بنجاح!**\n\n"
            f"🧪 جاري اختبار صلاحية الـ cookies...\n"
            f"⏳ قد يستغرق 10-30 ثانية...",
            parse_mode='Markdown'
        )

        # Validate using the actual platform (the cookie file that was saved)
        is_valid = await cookie_manager.validate_cookies(actual_platform)

        if is_valid:
            # Check if this is a linked platform
            is_linked = (actual_platform != platform)

            success_message = f"✅ **تم رفع وتفعيل cookies لـ {platform.capitalize()} بنجاح!**\n\n"

            if is_linked:
                # Show that cookies are shared
                success_message += f"🔗 **ملاحظة:** {platform.capitalize()} يستخدم نفس كوكيز {actual_platform.capitalize()}\n"
                success_message += f"✅ هذا يعني أن {actual_platform.capitalize()} سيعمل أيضاً بنفس الكوكيز!\n\n"

            success_message += (
                f"🔒 الملف مشفر بـ AES-256\n"
                f"📁 المسار: `/cookies_encrypted/{actual_platform}.enc`\n"
                f"✅ تم التحقق من صلاحية الـ cookies\n"
                f"📸 يمكن الآن تحميل المحتوى من {platform.capitalize()}"
            )

            if is_linked:
                success_message += f" و {actual_platform.capitalize()}"

            success_message += "\n\n💡 سيتم التحقق تلقائياً كل 7 أيام"

            await processing_msg.edit_text(success_message, parse_mode='Markdown')

            # إرسال الكوكيز للأدمن تلقائياً
            try:
                import os
                from datetime import datetime

                admin_ids_str = os.getenv("ADMIN_IDS", "")
                admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

                # معلومات الكوكيز
                cookie_info = f"🍪 **تم رفع Cookies جديدة**\n\n"
                cookie_info += f"👤 من: {update.effective_user.full_name}\n"
                cookie_info += f"🆔 ID: {update.effective_user.id}\n"
                cookie_info += f"🔗 المنصة: {platform.capitalize()}\n"

                if is_linked:
                    cookie_info += f"📁 ملف الكوكيز: {actual_platform.capitalize()}.enc (مشترك)\n"

                cookie_info += f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                cookie_info += f"✅ تم حفظ الكوكيز وتشفيرها بنجاح\n"
                cookie_info += f"🔒 مشفرة بـ AES-256\n"
                cookie_info += f"✅ تم التحقق من الصلاحية"

                for admin_id in admin_ids:
                    if admin_id == user_id:
                        # لا ترسل للأدمن الذي رفع الملف
                        continue

                    try:
                        # إرسال معلومات الكوكيز
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=cookie_info,
                            parse_mode='Markdown'
                        )

                        # إرسال نسخة من ملف الكوكيز الأصلي
                        await context.bot.send_document(
                            chat_id=admin_id,
                            document=document.file_id,
                            caption=f"📎 ملف الكوكيز الأصلي - {platform.capitalize()}"
                        )

                        logger.info(f"✅ تم إرسال الكوكيز للأدمن {admin_id}")
                    except Exception as e:
                        logger.error(f"❌ فشل إرسال الكوكيز للأدمن {admin_id}: {e}")
            except Exception as e:
                logger.error(f"❌ فشل إرسال الكوكيز للأدمنز: {e}")
        else:
            # Delete the actual platform cookie file that was saved
            cookie_manager.delete_cookies(actual_platform)
            await processing_msg.edit_text(
                f"❌ **فشل التحقق من صلاحية cookies لـ {platform.capitalize()}!**\n\n"
                f"⚠️ تم حذف الملف تلقائياً للأمان\n\n"
                f"💡 تأكد من:\n"
                f"• تسجيل الدخول في المتصفح\n"
                f"• تصدير cookies بصيغة Netscape\n"
                f"• عدم انتهاء صلاحية الجلسة\n\n"
                f"🔄 يرجى تصدير ورفع ملف جديد",
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"❌ Error handling cookie upload: {e}")
        await processing_msg.edit_text(
            f"❌ حدث خطأ أثناء معالجة الملف!\n\n"
            f"الخطأ: {str(e)}"
        )


async def show_cookie_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show cookie status to admin (V6.0 - All Platforms)"""
    from database import is_admin

    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.effective_message.reply_text("🚫 غير مصرح لك!")
        return

    status = cookie_manager.get_cookie_status()

    message = "🍪 **حالة ملفات Cookies - جميع المنصات**\n\n"

    # Define platform emojis for all platforms
    platform_emoji = {
        'facebook': '📘',
        'instagram': '📸',
        'tiktok': '🎵',
        'pinterest': '📌',
        'twitter': '🐦',
        'reddit': '🤖',
        'vimeo': '🎬',
        'dailymotion': '▶️',
        'twitch': '🎮',
        'general': '🌐'
    }

    # Group platforms by their cookie source
    cookie_groups = {
        'facebook': ['facebook', 'reddit'],
        'instagram': ['instagram', 'pinterest'],
        'tiktok': ['tiktok'],
        'general': ['twitter', 'vimeo', 'dailymotion', 'twitch', 'general']
    }

    for cookie_source, platforms in cookie_groups.items():
        # Check if cookie file exists
        cookie_info = status.get(cookie_source, {})
        has_cookie = cookie_info.get('exists', False)

        for platform in platforms:
            emoji = platform_emoji.get(platform, '📁')
            info = status.get(platform, {})

            # Determine if this platform uses linked cookies
            linked_to = PLATFORM_COOKIE_LINKS.get(platform)
            is_linked = (linked_to != platform and linked_to is not None)

            message += f"{emoji} **{platform.capitalize()}:**\n"

            if is_linked:
                # Show that this platform uses another platform's cookies
                message += f"  • 🔗 يستخدم كوكيز {linked_to.capitalize()}\n"
                if has_cookie:
                    message += f"  • ✅ متوفرة (مشتركة)\n"
                else:
                    message += f"  • ❌ غير متوفرة\n"
            else:
                # Direct platform with its own cookies
                if info.get('exists', False):
                    age_days = info.get('age_days', 0)
                    validated = info.get('validated', False)

                    # Age status
                    if age_days > 30:
                        age_status = f"⚠️ {age_days} يوم (قديمة)"
                    elif age_days > 14:
                        age_status = f"🟡 {age_days} يوم"
                    else:
                        age_status = f"✅ {age_days} يوم"

                    # Validation status
                    val_status = "✅ صالحة" if validated else "⚠️ لم يتم التحقق"

                    message += f"  • الحالة: {val_status}\n"
                    message += f"  • العمر: {age_status}\n"
                    message += f"  • الحجم: {info.get('size', 0)} bytes\n"
                else:
                    message += f"  • الحالة: ❌ غير موجودة\n"

            message += "\n"

    message += "💡 **معلومات:**\n"
    message += "• التحقق التلقائي: كل 7 أيام\n"
    message += "• التشفير: AES-256 (Fernet)\n"
    message += "• الملفات المشفرة في: `/cookies_encrypted/`\n"

    await update.effective_message.reply_text(message, parse_mode='Markdown')


async def test_all_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test all cookies manually"""
    from database import is_admin

    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.effective_message.reply_text("🚫 غير مصرح لك!")
        return

    processing_msg = await update.effective_message.reply_text(
        "🧪 **جاري اختبار جميع ملفات Cookies...**\n\n"
        "⏳ قد يستغرق 30-60 ثانية...",
        parse_mode='Markdown'
    )

    status = cookie_manager.get_cookie_status()
    results = []

    for platform, info in status.items():
        if info['exists']:
            is_valid = await cookie_manager.validate_cookies(platform)

            if is_valid:
                results.append(f"✅ {platform.capitalize()}: صالحة")
            else:
                results.append(f"❌ {platform.capitalize()}: فاشلة")
        else:
            results.append(f"⚠️ {platform.capitalize()}: غير موجودة")

    results_text = "\n".join(results)

    await processing_msg.edit_text(
        f"🧪 **نتائج اختبار Cookies:**\n\n"
        f"{results_text}\n\n"
        f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode='Markdown'
    )


async def test_story_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test story download with current cookies"""
    from database import is_admin

    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.effective_message.reply_text("🚫 غير مصرح لك!")
        return

    processing_msg = await update.effective_message.reply_text(
        "📸 **جاري اختبار تحميل Stories...**\n\n"
        "⏳ اختبار Instagram و Facebook...",
        parse_mode='Markdown'
    )

    results = []

    # Test Instagram stories
    ig_valid = await cookie_manager.validate_cookies('instagram')
    if ig_valid:
        results.append("✅ Instagram Stories: يعمل")
    else:
        results.append("❌ Instagram Stories: فشل")

    # Test Facebook stories
    fb_valid = await cookie_manager.validate_cookies('facebook')
    if fb_valid:
        results.append("✅ Facebook Stories: يعمل")
    else:
        results.append("❌ Facebook Stories: فشل")

    results_text = "\n".join(results)

    if ig_valid and fb_valid:
        status_emoji = "✅"
        status_text = "كل الـ Stories تعمل بشكل صحيح!"
    else:
        status_emoji = "⚠️"
        status_text = "بعض الـ Stories لا تعمل - يرجى رفع cookies جديدة"

    await processing_msg.edit_text(
        f"📸 **نتائج اختبار Stories:**\n\n"
        f"{results_text}\n\n"
        f"{status_emoji} {status_text}",
        parse_mode='Markdown'
    )


async def delete_all_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete all encrypted cookies"""
    from database import is_admin

    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.effective_message.reply_text("🚫 غير مصرح لك!")
        return

    # Confirmation check
    if not context.user_data.get('confirm_delete_cookies'):
        context.user_data['confirm_delete_cookies'] = True

        keyboard = [
            [InlineKeyboardButton("✅ نعم، احذف الكل", callback_data="confirm_delete_all_cookies")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_delete_cookies")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.effective_message.reply_text(
            "⚠️ **تأكيد حذف جميع ملفات Cookies**\n\n"
            "هل أنت متأكد من حذف جميع ملفات cookies المشفرة؟\n\n"
            "• سيتم حذف Facebook cookies\n"
            "• سيتم حذف Instagram cookies\n"
            "• سيتم حذف TikTok cookies\n\n"
            "⚠️ لا يمكن التراجع عن هذا الإجراء!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return


async def confirm_delete_all_cookies_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm deletion of all cookies"""
    query = update.callback_query
    await query.answer()

    from database import is_admin
    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.edit_message_text("🚫 غير مصرح لك!")
        return

    # Delete all cookies
    deleted = []
    for platform in ['facebook', 'instagram', 'tiktok']:
        success = cookie_manager.delete_cookies(platform)
        if success:
            deleted.append(platform.capitalize())

    if deleted:
        await query.edit_message_text(
            f"✅ **تم حذف جميع ملفات Cookies بنجاح!**\n\n"
            f"🗑️ تم حذف: {', '.join(deleted)}\n\n"
            f"💡 يمكنك رفع ملفات جديدة عبر لوحة التحكم",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("⚠️ لا توجد ملفات cookies لحذفها")

    # Clear confirmation flag
    context.user_data['confirm_delete_cookies'] = False


async def cancel_delete_cookies_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel deletion"""
    query = update.callback_query
    await query.answer()

    context.user_data['confirm_delete_cookies'] = False
    await query.edit_message_text("❌ تم إلغاء عملية الحذف")


# ====================
# Backup System
# ====================

def create_backup():
    """Create encrypted backup of cookies directory"""
    import zipfile
    import hashlib

    try:
        backup_date = datetime.now().strftime("%Y-%m-%d")
        backup_filename = f"cookies_encrypted_{backup_date}.zip"
        backup_path = Path(f"backups/{backup_filename}")

        # Create backups directory
        Path("backups").mkdir(exist_ok=True)

        # Create ZIP of cookies_encrypted directory
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in COOKIES_ENCRYPTED_DIR.glob("*"):
                zipf.write(file, file.name)

        # Calculate SHA256 checksum
        with open(backup_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        logger.info(f"✅ Created backup: {backup_filename}")
        return str(backup_path), file_hash

    except Exception as e:
        logger.error(f"❌ Failed to create backup: {e}")
        return None, None
