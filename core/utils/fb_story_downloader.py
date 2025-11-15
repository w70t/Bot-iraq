"""
Facebook Story Downloader - Fallback System
يستخدم مواقع خارجية كـ fallback عندما يفشل yt-dlp

المواقع المدعومة:
- FBDownloader
- SaveFrom
- SnapSave
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
import json
from typing import Optional, Dict, Any
from urllib.parse import quote

logger = logging.getLogger(__name__)


class FBStoryDownloader:
    """محمل Facebook Stories باستخدام مواقع خارجية"""

    # قائمة المواقع المدعومة
    SERVICES = {
        'fbdownloader': {
            'name': 'FBDownloader',
            'api_url': 'https://fbdownloader.app/api/video',
            'method': 'post',
            'enabled': True
        },
        'savefrom': {
            'name': 'SaveFrom',
            'api_url': 'https://api.savefrom.net/info',
            'method': 'get',
            'enabled': True
        },
        'snapinsta': {
            'name': 'SnapInsta',
            'api_url': 'https://snapinsta.app/api/ajaxSearch',
            'method': 'post',
            'enabled': True
        }
    }

    @staticmethod
    def download_facebook_story(url: str) -> Dict[str, Any]:
        """
        تحميل Facebook Story من موقع خارجي

        Args:
            url: رابط Facebook Story

        Returns:
            dict مع video_url و info
        """

        logger.info(f"🌐 [FB_STORY_DOWNLOADER] Attempting to download: {url[:80]}...")

        # المحاولة 1: FBDownloader API
        result = FBStoryDownloader._try_fbdownloader(url)
        if result:
            logger.info("✅ [FB_STORY_DOWNLOADER] Success via FBDownloader")
            return result

        # المحاولة 2: SaveFrom
        result = FBStoryDownloader._try_savefrom(url)
        if result:
            logger.info("✅ [FB_STORY_DOWNLOADER] Success via SaveFrom")
            return result

        # المحاولة 3: Web Scraping مباشر
        result = FBStoryDownloader._try_direct_scraping(url)
        if result:
            logger.info("✅ [FB_STORY_DOWNLOADER] Success via Direct Scraping")
            return result

        logger.error("❌ [FB_STORY_DOWNLOADER] All methods failed")
        return None

    @staticmethod
    def _try_fbdownloader(url: str) -> Optional[Dict[str, Any]]:
        """محاولة عبر FBDownloader"""
        try:
            logger.info("🔄 [FBDownloader] Trying FBDownloader API...")

            # FBDownloader API endpoint
            api_url = "https://www.fbdownloader.app/api/video"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }

            payload = {
                'url': url
            }

            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()

                # استخراج رابط الفيديو
                if 'download' in data or 'url' in data or 'video' in data:
                    video_url = (
                        data.get('download') or
                        data.get('url') or
                        data.get('video', {}).get('url')
                    )

                    if video_url:
                        return {
                            'video_url': video_url,
                            'title': data.get('title', 'Facebook Story'),
                            'thumbnail': data.get('thumbnail'),
                            'source': 'FBDownloader'
                        }

            logger.warning(f"⚠️ [FBDownloader] Failed: {response.status_code}")

        except Exception as e:
            logger.error(f"❌ [FBDownloader] Error: {e}")

        return None

    @staticmethod
    def _try_savefrom(url: str) -> Optional[Dict[str, Any]]:
        """محاولة عبر SaveFrom.net"""
        try:
            logger.info("🔄 [SaveFrom] Trying SaveFrom API...")

            # SaveFrom API
            api_url = f"https://api.savefrom.net/info?url={quote(url)}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(api_url, headers=headers, timeout=15)

            if response.status_code == 200:
                # تحليل الاستجابة
                data = response.text

                # البحث عن روابط الفيديو
                video_urls = re.findall(r'"url":"(https?://[^"]+)"', data)

                if video_urls:
                    return {
                        'video_url': video_urls[0],
                        'title': 'Facebook Story',
                        'source': 'SaveFrom'
                    }

            logger.warning(f"⚠️ [SaveFrom] Failed: {response.status_code}")

        except Exception as e:
            logger.error(f"❌ [SaveFrom] Error: {e}")

        return None

    @staticmethod
    def _try_direct_scraping(url: str) -> Optional[Dict[str, Any]]:
        """محاولة استخراج الفيديو مباشرة من HTML"""
        try:
            logger.info("🔄 [Direct Scraping] Trying direct HTML extraction...")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }

            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                html = response.text

                # البحث عن روابط الفيديو في HTML
                # Facebook يضع روابط الفيديو في meta tags أو JSON

                # محاولة 1: og:video
                og_video = re.search(r'<meta property="og:video" content="([^"]+)"', html)
                if og_video:
                    video_url = og_video.group(1)
                    return {
                        'video_url': video_url,
                        'title': 'Facebook Story',
                        'source': 'Direct Scraping (og:video)'
                    }

                # محاولة 2: JSON data
                json_match = re.search(r'<script[^>]*>.*?("video_url":\s*"([^"]+)")', html)
                if json_match:
                    video_url = json_match.group(2)
                    return {
                        'video_url': video_url,
                        'title': 'Facebook Story',
                        'source': 'Direct Scraping (JSON)'
                    }

            logger.warning(f"⚠️ [Direct Scraping] No video found in HTML")

        except Exception as e:
            logger.error(f"❌ [Direct Scraping] Error: {e}")

        return None

    @staticmethod
    def download_file(video_url: str, output_path: str) -> bool:
        """
        تحميل الفيديو من الرابط المباشر

        Args:
            video_url: رابط الفيديو المباشر
            output_path: مسار حفظ الملف

        Returns:
            True إذا نجح التحميل
        """
        try:
            logger.info(f"📥 [Download] Downloading from: {video_url[:80]}...")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(
                video_url,
                headers=headers,
                stream=True,
                timeout=30
            )

            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                logger.info(f"✅ [Download] Saved to: {output_path}")
                return True

            logger.error(f"❌ [Download] Failed: HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"❌ [Download] Error: {e}")

        return False


# دوال مساعدة سريعة
def download_facebook_story(url: str) -> Optional[Dict[str, Any]]:
    """
    دالة سريعة لتحميل Facebook Story

    Usage:
        result = download_facebook_story(url)
        if result:
            video_url = result['video_url']
            # تحميل الفيديو...
    """
    return FBStoryDownloader.download_facebook_story(url)


def is_facebook_story(url: str) -> bool:
    """تحقق إذا كان الرابط Facebook Story"""
    return '/stories/' in url.lower() and 'facebook.com' in url.lower()
