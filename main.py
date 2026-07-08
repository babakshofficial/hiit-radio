import os
import logging
import asyncio
import re
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

from metadata import TrackMetadata
from downloader import MusicDownloader
from user_manager import UserManager

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

downloader = MusicDownloader()
user_manager = UserManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! من ربات دانلودر موزیک هستم.\n\n"
        "لینک اپل موزیک، اسپاتیفای، یوتیوب یا ساوندکلاود بفرست، یا نام آهنگ را تایپ کن.\n\n"
        "/help - راهنما\n/stats - آمار"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "لینک مستقیم یا نام آهنگ را ارسال کن.\nمحدودیت: ۱۰ دانلود در ساعت."
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    total_users, total_downloads = user_manager.get_stats()
    await update.message.reply_text(f"کاربران: {total_users}\nدانلودها: {total_downloads}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    allowed, wait_time = user_manager.check_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(f"محدودیت دانلود. {wait_time // 60} دقیقه صبر کنید.")
        return

    status_message = await update.message.reply_text("🔍 در حال بررسی...")
    
    metadata = await TrackMetadata.create(text)
    
    if not metadata.title:
        await status_message.edit_text("❌ اطلاعات آهنگ یافت نشد.")
        return

    await status_message.edit_text(f"🎵 {metadata.title} - {metadata.artist or 'Unknown'}\n📥 در حال دانلود...")
    
    file_path = await downloader.download_song(metadata)
    
    if file_path and os.path.exists(file_path):
        await status_message.edit_text("📤 در حال ارسال...")
        try:
            with open(file_path, 'rb') as audio:
                await update.message.reply_audio(
                    audio=audio,
                    title=metadata.title,
                    performer=metadata.artist,
                    read_timeout=60, write_timeout=60
                )
            user_manager.record_download(user_id)
            await status_message.delete()
        except Exception as e:
            logger.error(f"Send failed: {e}")
            await status_message.edit_text("❌ خطای ارسال.")
        await downloader.cleanup(file_path)
    else:
        # Fallback to 30s preview if available
        if metadata.preview_url:
            await status_message.edit_text("⚠️ دانلود کامل ممکن نیست. ارسال نمونه ۳۰ ثانیه‌ای...")
            try:
                preview_path = os.path.join(downloader.download_dir, f"{metadata.id}_preview.mp3")
                with open(preview_path, 'wb') as f:
                    f.write(requests.get(metadata.preview_url, timeout=10).content)
                with open(preview_path, 'rb') as audio:
                    await update.message.reply_audio(audio=audio, title=f"{metadata.title} (Preview)", performer=metadata.artist)
                os.remove(preview_path)
                await status_message.delete()
                return
            except Exception as e:
                logger.error(f"Preview failed: {e}")
                
        await status_message.edit_text("❌ آهنگ پیدا نشد.")

def main():
    if not BOT_TOKEN: return
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()