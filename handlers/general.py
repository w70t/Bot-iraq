import random
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Emoji reactions for different types of content
REACTIONS = ["👀", "✨", "🎵", "🔥", "💫", "🤩", "🎬", "📡", "⚡", "🎯"]

async def handle_reactive_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    رد تفاعلي تلقائي عند إرسال روابط أو ملفات
    Shows random emoji reactions to links
    """
    try:
        text = update.message.text or ""

        # React to links
        if any(keyword in text.lower() for keyword in ["http", "www", "youtu", "facebook", "instagram", "tiktok"]):
            reaction = random.choice(REACTIONS)
            await update.message.set_reaction(reaction)
            logger.info(f"⚡ تفاعل تلقائي: {reaction} للمستخدم {update.effective_user.id}")

    except Exception as e:
        # Silent fail - reactions are not critical
        logger.debug(f"فشل التفاعل التلقائي: {e}")
