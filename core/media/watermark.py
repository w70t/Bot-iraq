#!/usr/bin/env python3
"""
دوال إضافة اللوجو والعلامات المائية
Watermark and logo overlay utilities using FFmpeg
"""

import os
import subprocess

from config.logger import get_logger

logger = get_logger(__name__)


def get_logo_overlay_position(position):
    """
    الحصول على إحداثيات وضع اللوجو
    """
    positions = {
        'top_left': (10, 10),
        'top_right': ('W-w-10', 10),
        'bottom_left': (10, 'H-h-10'),
        'bottom_right': ('W-w-10', 'H-h-10'),
        'center': ('(W-w)/2', '(H-h)/2'),
        'center_right': ('W-w-10', '(H-h)/2'),
        'center_left': ('10', '(H-h)/2'),
        'top_center': ('(W-w)/2', '10'),
        'bottom_center': ('(W-w)/2', 'H-h-10'),
    }

    x, y = positions.get(position, positions['center_right'])
    return x, y


def prepare_logo_for_processing(logo_path, max_size=500):
    """
    تحضير اللوجو للمعالجة - تصغيره إذا كان كبيراً جداً

    Args:
        logo_path: مسار اللوجو الأصلي
        max_size: الحد الأقصى للحجم (افتراضي 500px)

    Returns:
        str: مسار اللوجو المُحضَّر (قد يكون مؤقتاً إذا تم تصغيره)
    """
    try:
        # الحصول على أبعاد اللوجو باستخدام ffprobe
        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            logo_path
        ]

        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            dimensions = result.stdout.strip().split(',')
            if len(dimensions) == 2:
                width = int(dimensions[0])
                height = int(dimensions[1])

                logger.info(f"🔍 [prepare_logo] أبعاد اللوجو: {width}x{height}")

                # إذا كان اللوجو كبيراً جداً (أكبر من max_size)، نصغره
                if width > max_size or height > max_size:
                    logger.warning(f"⚠️ [prepare_logo] اللوجو كبير جداً ({width}x{height}) - جاري التصغير...")

                    # إنشاء مسار مؤقت للوجو المصغر
                    temp_logo_path = logo_path.replace('.png', '_resized.png')

                    # تصغير اللوجو مع الحفاظ على نسبة العرض للارتفاع والشفافية
                    resize_cmd = [
                        'ffmpeg', '-y', '-i', logo_path,
                        '-vf', f'scale={max_size}:{max_size}:force_original_aspect_ratio=decrease,format=rgba',
                        '-pix_fmt', 'rgba',
                        temp_logo_path
                    ]

                    resize_result = subprocess.run(resize_cmd, capture_output=True, text=True, timeout=30)

                    if resize_result.returncode == 0 and os.path.exists(temp_logo_path):
                        new_size = os.path.getsize(temp_logo_path)
                        logger.info(f"✅ [prepare_logo] تم تصغير اللوجو بنجاح: {width}x{height} → ~{max_size}x{max_size}")
                        logger.info(f"  - اللوجو المصغر: {temp_logo_path} ({new_size/1024:.1f}KB)")
                        return temp_logo_path
                    else:
                        logger.warning(f"⚠️ [prepare_logo] فشل تصغير اللوجو - استخدام الأصلي")
                        return logo_path
                else:
                    logger.info(f"✅ [prepare_logo] حجم اللوجو مناسب - لا حاجة للتصغير")
                    return logo_path

        # في حالة فشل ffprobe، استخدم اللوجو الأصلي
        return logo_path

    except Exception as e:
        logger.warning(f"⚠️ [prepare_logo] خطأ في تحضير اللوجو: {e}")
        return logo_path


def apply_simple_watermark(input_path, output_path, logo_path, animation_type='corner_rotation', size=150, position='top_right', opacity=0.7):
    """
    دالة موحدة ومبسطة لإضافة اللوجو - محسّنة للأداء
    جميع الحركات تحترم الموضع المختار من المستخدم

    📍 **شرح المميزات:**
    • static: ثابت تماماً في الموضع المحدد (لا يتحرك)
    • المتحركات: تتحرك حول الموضع المحدد (وسط، تحت، إلخ)

    ⚡ **تحسينات الأداء:**
    • ultrafast preset لسرعة المعالجة
    • CRF 28 لتقليل حجم الملف
    • معالجة أولوية منخفضة لتقليل حمل CPU
    """
    try:
        # تتبع حالة الملفات قبل البدء
        logger.info(f"🔍 [TRACE] بدء apply_simple_watermark")
        logger.info(f"  - input_path: {input_path}")
        logger.info(f"  - input exists: {os.path.exists(input_path)}")
        if os.path.exists(input_path):
            logger.info(f"  - input size: {os.path.getsize(input_path) / 1024 / 1024:.2f}MB")
        logger.info(f"  - output_path: {output_path}")
        logger.info(f"  - logo_path: {logo_path}")
        logger.info(f"  - logo exists: {os.path.exists(logo_path)}")

        # تحضير اللوجو (تصغيره إذا كان كبيراً جداً)
        prepared_logo_path = prepare_logo_for_processing(logo_path, max_size=500)
        logger.info(f"  - prepared_logo_path: {prepared_logo_path}")

        # الحصول على إحداثيات الموضع المختار
        pos_x, pos_y = get_logo_overlay_position(position)

        # تحويل إلى string
        if isinstance(pos_x, str):
            overlay_x = pos_x
        else:
            overlay_x = str(pos_x)

        if isinstance(pos_y, str):
            overlay_y = pos_y
        else:
            overlay_y = str(pos_y)

        # الشفافية
        if opacity < 1.0:
            opacity_filter = f"[1:v]scale={size}:-1,format=rgba,colorchannelmixer=aa={opacity}[logo]"
        else:
            opacity_filter = f"[1:v]scale={size}:-1,format=rgba[logo]"

        # اختيار الحركة حسب النوع
        if animation_type == 'static':
            # 🔒 ثابت تماماً في الموضع المختار (لا يتحرك مطلقاً)
            filter_complex = f"{opacity_filter};[0:v][logo]overlay={overlay_x}:{overlay_y}"
            logger.info(f"🔒 تطبيق لوجو ثابت في الموضع: {position}")

        elif animation_type == 'corner_rotation':
            # 🔄 يتحرك بين 4 زوايا حول الموضع المختار
            # إذا اختار "وسط" → يدور حول الوسط في مربع صغير
            # إذا اختار "تحت" → يدور في الأسفل
            filter_complex = (
                f"{opacity_filter};"
                "[0:v][logo]overlay="
                f"x='{overlay_x}+if(lt(mod(n,240),60),-30,if(lt(mod(n,240),120),30,if(lt(mod(n,240),180),30,-30)))':"
                f"y='{overlay_y}+if(lt(mod(n,240),60),-30,if(lt(mod(n,240),120),-30,if(lt(mod(n,240),180),30,30)))'"
            )
            logger.info(f"🔄 تطبيق حركة الزوايا في الموضع: {position}")

        elif animation_type == 'bounce':
            # ⬆️ يرتد حول الموضع المختار (دائرة صغيرة)
            filter_complex = (
                f"{opacity_filter};"
                "[0:v][logo]overlay="
                f"x='{overlay_x}+30*sin(n/20)':"
                f"y='{overlay_y}+30*cos(n/20)'"
            )
            logger.info(f"⬆️ تطبيق حركة الارتداد في الموضع: {position}")

        elif animation_type == 'slide':
            # ➡️ ينزلق يميناً ويساراً حول الموضع المختار
            filter_complex = (
                f"{opacity_filter};"
                "[0:v][logo]overlay="
                f"x='{overlay_x}+50*sin(n/40)':"
                f"y='{overlay_y}'"
            )
            logger.info(f"➡️ تطبيق حركة الانزلاق في الموضع: {position}")

        elif animation_type == 'fade':
            # 💫 ثابت في الموضع المختار مع تأثير التلاشي
            filter_complex = f"{opacity_filter};[0:v][logo]overlay={overlay_x}:{overlay_y}"
            logger.info(f"💫 تطبيق حركة التلاشي في الموضع: {position}")

        elif animation_type == 'zoom':
            # 🔍 ثابت في الموضع المختار مع تأثير التكبير
            filter_complex = f"{opacity_filter};[0:v][logo]overlay={overlay_x}:{overlay_y}"
            logger.info(f"🔍 تطبيق حركة التكبير في الموضع: {position}")

        else:
            # افتراضي - ثابت في الموضع المحدد
            filter_complex = f"{opacity_filter};[0:v][logo]overlay={overlay_x}:{overlay_y}"
            logger.info(f"⚪ تطبيق حركة افتراضية في الموضع: {position}")

        # الأمر مع تحسينات الأداء والحجم
        # ❌ تم إزالة -movflags +faststart لأنه يسبب حذف الملف المدخل
        # المشكلة: عند فشل إعادة فتح الملف المخرج، FFmpeg يحذف الملف المدخل!

        # محاولة استخدام hardware acceleration إن أمكن
        hw_accel_cmd = []
        try:
            # التحقق الفعلي من NVENC (اختبار حقيقي وليس فقط الوجود في القائمة)
            test_cmd = [
                'ffmpeg', '-hide_banner', '-f', 'lavfi', '-i', 'color=black:s=64x64:d=0.1',
                '-c:v', 'h264_nvenc', '-f', 'null', '-'
            ]
            nvenc_test = subprocess.run(
                test_cmd,
                capture_output=True, text=True, timeout=5
            )

            if nvenc_test.returncode == 0:
                logger.info("🚀 [apply_simple_watermark] NVENC متاح ويعمل - استخدام hardware acceleration")
                hw_accel_cmd = ['-c:v', 'h264_nvenc', '-preset', 'p4']  # p4 = medium quality/speed
            else:
                logger.debug("ℹ️ [apply_simple_watermark] NVENC غير متاح أو لا يعمل - استخدام CPU")
                logger.debug(f"  - NVENC test stderr: {nvenc_test.stderr[:200]}")
        except Exception as e:
            logger.debug(f"ℹ️ [apply_simple_watermark] فشل فحص NVENC: {e}")
            pass  # Silently fall back to CPU encoding

        # بناء الأمر
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-i', prepared_logo_path,  # استخدام اللوجو المُحضَّر (المصغر إذا لزم الأمر)
            '-filter_complex', filter_complex,
            '-c:a', 'copy',  # نسخ الصوت بدون إعادة ترميز
        ]

        # إضافة إعدادات الفيديو (hardware أو software)
        if hw_accel_cmd:
            cmd.extend(hw_accel_cmd)
            cmd.extend(['-b:v', '3M', '-maxrate', '4M', '-bufsize', '6M'])  # تحديد bitrate للحجم
        else:
            # Software encoding مع توازن أفضل
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'veryfast',  # توازن بين السرعة والحجم (أفضل من ultrafast)
                '-crf', '24',  # جودة جيدة مع حجم معقول (23-28 نطاق جيد)
                '-tune', 'film',  # تحسين للمحتوى العام
                '-threads', '4',  # زيادة الخيوط قليلاً للسرعة
            ])

        cmd.extend([
            # '-movflags', '+faststart',  # ❌ يسبب: Unable to re-open output file
            '-shortest',
            output_path
        ])

        logger.info(f"🔄 تنفيذ FFmpeg ({animation_type} في الموضع {position})")

        # تشغيل FFmpeg مع أولوية منخفضة لتقليل استهلاك CPU
        try:
            import psutil
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.getcwd()
            )

            # تقليل أولوية العملية
            try:
                p = psutil.Process(process.pid)
                p.nice(3)  # أولوية منخفضة معتدلة (0-19، 19 الأدنى)
            except Exception:
                pass

            # الانتظار حتى الانتهاء
            stdout, stderr = process.communicate(timeout=300)
            result = type('obj', (object,), {
                'returncode': process.returncode,
                'stdout': stdout,
                'stderr': stderr
            })()

        except ImportError:
            # إذا لم يكن psutil متاحاً، استخدم subprocess العادي
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=os.getcwd()
            )

        if result.returncode != 0:
            logger.error(f"❌ FFmpeg فشل ({animation_type})")
            logger.error(f"  Command: {' '.join(cmd)}")
            logger.error(f"  Return code: {result.returncode}")
            logger.error(f"  stderr (full): {result.stderr}")
            logger.error(f"  input_path exists: {os.path.exists(input_path)}")
            logger.error(f"  output_path exists: {os.path.exists(output_path)}")
            return input_path

        if not os.path.exists(output_path):
            logger.error("❌ ملف الناتج غير موجود")
            return input_path

        file_size = os.path.getsize(output_path)
        if file_size < 1000:
            logger.error("❌ ملف الناتج فارغ")
            return input_path

        logger.info(f"✨ نجح اللوجو ({animation_type} في {position})! {file_size/1024/1024:.2f}MB")
        return output_path

    except subprocess.TimeoutExpired:
        logger.error("❌ FFmpeg انتهت مهلته")
        return input_path
    except Exception as e:
        logger.error(f"❌ خطأ في اللوجو ({animation_type}): {e}")
        return input_path


def apply_animated_watermark(input_path, output_path, logo_path, size=None):
    """
    دالة رئيسية محدثة لإضافة اللوجو المتحرك - إصلاح FFmpeg
    """
    logger.info(f"🎨 بدء معالجة اللوجو...")
    logger.info(f"  - input_path: {input_path}")
    logger.info(f"  - output_path: {output_path}")
    logger.info(f"  - logo_path: {logo_path}")
    logger.info(f"  - size: {size}")

    if not os.path.exists(logo_path):
        logger.error(f"❌ مسار اللوجو غير صحيح: {logo_path}")
        return input_path

    if not os.path.exists(input_path):
        logger.error(f"❌ مسار الفيديو المدخل غير صحيح: {input_path}")
        return input_path

    try:
        logger.info(f"✨ بدء إضافة اللوجو المتحرك: {input_path}")

        # جلب جميع الإعدادات من قاعدة البيانات
        try:
            from database import get_all_logo_settings
            settings = get_all_logo_settings()

            animation_type = settings.get('animation', 'corner_rotation')
            position = settings.get('position', 'top_right')
            size_px = settings.get('size_pixels', 150) if size is None else size
            opacity = settings.get('opacity_decimal', 0.7)

            logger.info(f"⚙️ إعدادات اللوجو: {animation_type}, {position}, {size_px}px, {int(opacity*100)}%")

        except Exception as db_error:
            logger.warning(f"⚠️ فشل قراءة إعدادات قاعدة البيانات: {db_error}")
            # استخدام إعدادات افتراضية
            animation_type = 'corner_rotation'
            position = 'top_right'
            size_px = 150 if size is None else size
            opacity = 0.7
            logger.info(f"⚙️ استخدام إعدادات افتراضية: {animation_type}, {position}, {size_px}px, {int(opacity*100)}%")

        # استخدام الدالة المبسطة الجديدة مع الإصلاح
        result_path = apply_simple_watermark(input_path, output_path, logo_path, animation_type, size_px, position, opacity)

        if result_path != input_path:
            logger.info(f"✨ تم تطبيق اللوجو بنجاح!")

            # التحقق من حجم الملف الناتج
            if os.path.exists(result_path):
                file_size_mb = os.path.getsize(result_path) / 1024 / 1024
                logger.info(f"📊 [apply_animated_watermark] حجم الفيديو بعد اللوجو: {file_size_mb:.2f}MB")

                # إذا تجاوز 48MB، نضغطه تلقائياً
                if file_size_mb > 48:
                    logger.warning(f"⚠️ [apply_animated_watermark] الملف كبير جداً ({file_size_mb:.2f}MB) - بدء الضغط...")

                    # إنشاء مسار مؤقت للملف المضغوط
                    compressed_path = result_path.replace('.mp4', '_compressed.mp4')

                    # ضغط الفيديو
                    compressed_result = compress_video_smart(result_path, compressed_path, target_size_mb=48, max_attempts=3)

                    if compressed_result != result_path and os.path.exists(compressed_result):
                        # نجح الضغط - حذف الملف الكبير واستخدام المضغوط
                        compressed_size_mb = os.path.getsize(compressed_result) / 1024 / 1024
                        logger.info(f"✅ [apply_animated_watermark] تم الضغط بنجاح: {file_size_mb:.2f}MB → {compressed_size_mb:.2f}MB")

                        try:
                            os.remove(result_path)
                            logger.info(f"🗑️ [apply_animated_watermark] تم حذف الملف الكبير: {result_path}")
                        except Exception as e:
                            logger.warning(f"⚠️ [apply_animated_watermark] فشل حذف الملف الكبير: {e}")

                        # نقل الملف المضغوط إلى المسار الأصلي
                        try:
                            os.rename(compressed_result, result_path)
                            logger.info(f"✅ [apply_animated_watermark] تم نقل الملف المضغوط إلى: {result_path}")
                        except Exception as e:
                            logger.error(f"❌ [apply_animated_watermark] فشل نقل الملف: {e}")
                            result_path = compressed_result
                    else:
                        logger.warning(f"⚠️ [apply_animated_watermark] فشل الضغط - استخدام الملف الأصلي")

            return result_path
        else:
            logger.warning(f"⚠️ فشل اللوجو المتحرك، محاولة اللوجو الثابت...")
            return apply_watermark(input_path, output_path, logo_path, position, size)

    except Exception as e:
        logger.error(f"❌ خطأ عام في اللوجو المتحرك: {str(e)}")
        logger.error(f"تفاصيل الخطأ: {str(e)}")
        return apply_watermark(input_path, output_path, logo_path, position, size)


def compress_video_smart(input_path, output_path, target_size_mb=48, max_attempts=3):
    """
    ضغط ذكي للفيديو للوصول إلى حجم مستهدف

    Args:
        input_path: مسار الفيديو المدخل
        output_path: مسار الفيديو المخرج
        target_size_mb: الحجم المستهدف بالميجابايت (افتراضي 48MB)
        max_attempts: عدد محاولات الضغط (افتراضي 3)

    Returns:
        str: مسار الملف المضغوط في حالة النجاح، أو input_path في حالة الفشل
    """
    try:
        import traceback

        logger.info(f"🗜️ [compress_video_smart] بدء ضغط ذكي للفيديو")
        logger.info(f"  - input_path: {input_path}")
        logger.info(f"  - target_size: {target_size_mb}MB")

        if not os.path.exists(input_path):
            logger.error(f"❌ [compress_video_smart] الملف غير موجود: {input_path}")
            return input_path

        input_size_mb = os.path.getsize(input_path) / 1024 / 1024
        logger.info(f"📊 [compress_video_smart] حجم الملف الأصلي: {input_size_mb:.2f}MB")

        if input_size_mb <= target_size_mb:
            logger.info(f"✅ [compress_video_smart] الملف أصغر من الحد المطلوب ({target_size_mb}MB)")
            return input_path

        # الحصول على مدة الفيديو
        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_path
        ]

        try:
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
            duration_seconds = float(result.stdout.strip())
            logger.info(f"⏱️ [compress_video_smart] مدة الفيديو: {duration_seconds:.1f}s")
        except Exception as e:
            logger.warning(f"⚠️ [compress_video_smart] فشل قراءة مدة الفيديو: {e}")
            duration_seconds = 180  # افتراض 3 دقائق

        # حساب bitrate المستهدف (90% من الهدف لترك هامش أمان)
        target_bitrate_kbps = int((target_size_mb * 0.90 * 8192) / duration_seconds)
        logger.info(f"🎯 [compress_video_smart] bitrate المستهدف: {target_bitrate_kbps}kbps")

        # محاولة الضغط بإعدادات مختلفة
        for attempt in range(1, max_attempts + 1):
            logger.info(f"🔄 [compress_video_smart] محاولة {attempt}/{max_attempts}")

            # تعديل البتريت حسب المحاولة
            current_bitrate = int(target_bitrate_kbps * (0.9 ** (attempt - 1)))
            logger.info(f"  - bitrate للمحاولة {attempt}: {current_bitrate}kbps")

            # اختيار preset حسب المحاولة (أسرع أولاً، ثم أبطأ للضغط أكثر)
            presets = ['veryfast', 'faster', 'fast']
            preset = presets[min(attempt - 1, len(presets) - 1)]

            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-c:v', 'libx264',
                '-preset', preset,
                '-b:v', f'{current_bitrate}k',
                '-maxrate', f'{int(current_bitrate * 1.2)}k',
                '-bufsize', f'{int(current_bitrate * 2)}k',
                '-c:a', 'aac',
                '-b:a', '128k',  # جودة صوت معقولة
                '-ac', '2',  # ستيريو
                '-shortest',
                output_path
            ]

            logger.info(f"  - preset: {preset}")
            logger.info(f"🔄 [compress_video_smart] تشغيل FFmpeg...")

            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            elapsed_time = time.time() - start_time

            logger.info(f"⏱️ [compress_video_smart] وقت المعالجة: {elapsed_time:.1f}s")

            if result.returncode != 0:
                logger.error(f"❌ [compress_video_smart] فشل FFmpeg في المحاولة {attempt}")
                logger.error(f"  - stderr: {result.stderr[-500:]}")  # آخر 500 حرف
                continue

            if not os.path.exists(output_path):
                logger.error(f"❌ [compress_video_smart] ملف الناتج غير موجود")
                continue

            output_size_mb = os.path.getsize(output_path) / 1024 / 1024
            logger.info(f"📊 [compress_video_smart] حجم الناتج: {output_size_mb:.2f}MB")

            if output_size_mb <= target_size_mb:
                reduction_pct = ((input_size_mb - output_size_mb) / input_size_mb) * 100
                logger.info(f"✅ [compress_video_smart] نجح الضغط! تقليل {reduction_pct:.1f}%")
                logger.info(f"  - من {input_size_mb:.2f}MB إلى {output_size_mb:.2f}MB")
                return output_path
            else:
                logger.warning(f"⚠️ [compress_video_smart] المحاولة {attempt}: الحجم لا يزال كبيراً ({output_size_mb:.2f}MB)")

        # إذا فشلت جميع المحاولات
        logger.error(f"❌ [compress_video_smart] فشل الوصول للحجم المستهدف بعد {max_attempts} محاولات")

        # إرجاع آخر نتيجة حتى لو كانت أكبر من الهدف
        if os.path.exists(output_path):
            output_size_mb = os.path.getsize(output_path) / 1024 / 1024
            if output_size_mb < input_size_mb:
                logger.info(f"ℹ️ [compress_video_smart] استخدام آخر محاولة ({output_size_mb:.2f}MB)")
                return output_path

        return input_path

    except Exception as e:
        import traceback
        logger.error(f"❌ [compress_video_smart] خطأ حرج: {type(e).__name__}: {str(e)}")
        logger.error(f"📍 [compress_video_smart] Stack trace:\n{traceback.format_exc()}")
        return input_path


def apply_watermark(input_path, output_path, logo_path, position='center', size=150):
    """
    يطبق لوجو ثابت على الفيديو (احتياطي محسّن)
    """
    # تتبع دقيق لحالة الملفات
    logger.info(f"🔍 [TRACE] بدء apply_watermark (fallback)")
    logger.info(f"  - input_path: {input_path}")
    logger.info(f"  - input exists: {os.path.exists(input_path)}")
    logger.info(f"  - logo_path: {logo_path}")
    logger.info(f"  - logo exists: {os.path.exists(logo_path)}")
    logger.info(f"  - current working directory: {os.getcwd()}")

    # قائمة الملفات في مجلد videos
    try:
        videos_dir = os.path.dirname(input_path) or 'videos'
        if os.path.exists(videos_dir):
            files_in_dir = os.listdir(videos_dir)
            logger.info(f"  - files in {videos_dir}: {files_in_dir[:10]}")  # أول 10 ملفات
    except Exception as e:
        logger.error(f"  - error listing directory: {e}")

    if not os.path.exists(logo_path):
        logger.error(f"❌ مسار اللوجو غير صحيح: {logo_path}")
        return input_path

    if not os.path.exists(input_path):
        logger.error(f"❌ مسار الفيديو المدخل غير صحيح: {input_path}")
        return input_path

    try:
        logger.info(f"🎨 إضافة لوجو ثابت: {input_path}")

        # تحضير اللوجو (تصغيره إذا كان كبيراً جداً)
        prepared_logo_path = prepare_logo_for_processing(logo_path, max_size=500)

        # التأكد من أن size قيمة صحيحة
        if size is None or not isinstance(size, (int, float)):
            size = 150
            logger.warning(f"⚠️ تم تعيين حجم افتراضي: {size}")

        size = int(size)

        # جميع المواضع المتاحة
        positions = {
            'top_left': '10:10',
            'top_right': f'W-w-10:10',
            'bottom_left': f'10:H-h-10',
            'bottom_right': f'W-w-10:H-h-10',
            'center': f'(W-w)/2:(H-h)/2',
            'center_right': f'W-w-10:(H-h)/2',
            'center_left': f'10:(H-h)/2',
            'top_center': f'(W-w)/2:10',
            'bottom_center': f'(W-w)/2:H-h-10'
        }

        pos = positions.get(position, positions['center'])

        # الحصول على مدة الفيديو لحساب timeout مناسب
        try:
            probe_cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                input_path
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            duration_seconds = float(probe_result.stdout.strip())
            # timeout = مدة الفيديو × 3 + 120 ثانية (أقل من 10 دقائق كحد أدنى)
            processing_timeout = max(600, int(duration_seconds * 3 + 120))
            logger.info(f"⏱️ [apply_watermark] مدة الفيديو: {duration_seconds:.1f}s - timeout: {processing_timeout}s")
        except Exception as e:
            logger.warning(f"⚠️ [apply_watermark] فشل قراءة مدة الفيديو: {e}")
            processing_timeout = 600  # افتراضي 10 دقائق

        # بناء الأمر مع إعدادات محسّنة
        cmd = [
            'ffmpeg',
            '-y',
            '-i', input_path,
            '-i', prepared_logo_path,  # استخدام اللوجو المُحضَّر
            '-filter_complex',
            f'[1:v]scale={size}:-1[logo];[0:v][logo]overlay={pos}',
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'veryfast',  # أسرع من medium - تحسين السرعة
            '-crf', '24',  # جودة جيدة
            '-threads', '4',  # تسريع
            # '-movflags', '+faststart',  # ❌ يسبب: Unable to re-open output file
            '-shortest',
            output_path
        ]

        logger.info(f"🔄 [apply_watermark] بدء المعالجة (timeout: {processing_timeout}s)")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=processing_timeout)

        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size > 1000:
                logger.info(f"✅ نجح اللوجو الثابت ({file_size/1024/1024:.2f}MB)")
                return output_path

        logger.error(f"❌ فشل اللوجو الثابت")
        if result.stderr:
            logger.error(f"تفاصيل الخطأ: {result.stderr[:500]}")
        return input_path

    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return input_path
