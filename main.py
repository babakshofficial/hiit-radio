import os
import logging
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

from metadata import AppleMusicMetadata, SpotifyMetadata
from downloader import MusicDownloader
from user_manager import UserManager

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

downloader = MusicDownloader()
user_manager = UserManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"سلام {user.first_name}! من ربات دانلودر موزیک هستم.\n\n"
        "لینک اپل موزیک یا اسپاتیفای (آهنگ) بفرست، یا نام آهنگ و خواننده را تایپ کن.\n\n"
        "دستورات:\n"
        "/help - راهنما\n"
        "/stats - آمار ربات (فقط ادمین)"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "روش‌های دانلود:\n\n"
        "1️⃣ لینک اپل موزیک (آهنگ)\n"
        "2️⃣ لینک اسپاتیفای (آهنگ)\n"
        "3️⃣ نام آهنگ + خواننده (مثلاً: Bohemian Rhapsody Queen)\n\n"
        "محدودیت: ۱۰ دانلود در ساعت."
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        return
    
    total_users, total_downloads = user_manager.get_stats()
    await update.message.reply_text(
        f"📊 آمار ربات:\n\n"
        f"تعداد کاربران: {total_users}\n"
        f"کل دانلودها: {total_downloads}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    allowed, wait_time = user_manager.check_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(f"محدودیت دانلود. لطفاً {wait_time // 60} دقیقه صبر کنید.")
        return

    status_message = await update.message.reply_text("🔍 در حال بررسی...")

    # 🔹 SPOTIFY LINK HANDLING
    if "spotify.com" in text or "open.spotify.com" in text:
        await status_message.edit_text("🔍 در حال استخراج اطلاعات از اسپاتیفای...")
        metadata = SpotifyMetadata(text)
        if not await metadata.fetch():
            await status_message.edit_text(
                "❌ خطای اسپاتیفای:\n"
                "• فقط لینک آهنگ (نه آلبوم/پلی‌لیست) معتبر است\n"
                "• اگر خطای 403 می‌بینید: اپلیکیشن اسپاتیفای در داشبورد فعال نیست.\n"
                "  راه‌حل: به داشبورد اسپاتیفای بروید و Redirect URI اضافه کنید."
            )
            return
    
    # 🔹 APPLE MUSIC LINK HANDLING
    elif "music.apple.com" in text:
        await status_message.edit_text("🔍 در حال استخراج اطلاعات از اپل موزیک...")
        metadata = AppleMusicMetadata(text)
        if not await metadata.fetch():
            await status_message.edit_text("❌ خطا در استخراج اطلاعات. لطفاً لینک را بررسی کنید.")
            return
    
    # 🔹 TEXT QUERY HANDLING (iTunes Search)
    else:
        query = text.strip()
        if len(query) < 3:
            await update.message.reply_text("❌ لطفاً حداقل ۳ کاراکتر وارد کنید.")
            return

        await status_message.edit_text("🔍 جستجو در اپل موزیک...")
        metadata = await AppleMusicMetadata.search_by_query(query)
        
        if not metadata:
            title = query
            artist = ""
            if re.search(r'\s+by\s+', query, re.IGNORECASE):
                parts = re.split(r'\s+by\s+', query, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) == 2:
                    title = parts[0].strip()
                    artist = parts[1].strip()
            elif " - " in query:
                parts = query.split(" - ", 1)
                if len(parts) == 2:
                    artist = parts[0].strip()
                    title = parts[1].strip()

            metadata = AppleMusicMetadata(None)
            metadata.title = title
            metadata.artist = artist
            metadata.id = str(hash(query))
            metadata.type = 'search'

        await status_message.edit_text(f"🎵 یافت شد: {metadata.title} {metadata.artist}\n📥 در حال دانلود...")

    # 🔹 DOWNLOAD AND SEND
    file_path = await downloader.download_song(metadata)
    
    if file_path and os.path.exists(file_path):
        await status_message.edit_text("📤 در حال ارسال به تلگرام...")
        
        search_query = f"{metadata.artist} {metadata.title}".strip()
        keyboard = [
            [InlineKeyboardButton("🔍 جستجوی مشابه", switch_inline_query_current_chat=search_query)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(file_path, 'rb') as audio:
                    await update.message.reply_audio(
                        audio=audio,
                        title=metadata.title,
                        performer=metadata.artist,
                        reply_markup=reply_markup,
                        read_timeout=60,
                        write_timeout=60,
                        connect_timeout=60,
                        pool_timeout=60
                    )
                user_manager.record_download(user_id)
                await status_message.delete()
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                    await asyncio.sleep(2)
                else:
                    logger.error(f"Send failed: {e}")
                    await status_message.edit_text("❌ خطای ارسال. لطفاً دوباره امتحان کنید.")
        
        await downloader.cleanup(file_path)
    else:
        # 🔑 FALLBACK: Use Apple/Spotify 30s preview if available
        if metadata.preview_url:
            await status_message.edit_text(
                f"⚠️ نسخه کامل یافت نشد.\n"
                f"در حال ارسال نمونه ۳۰ ثانیه‌ای رسمی از {metadata.title}...\n\n"
                f"💡 نکته: برای دانلود کامل، لینک مستقیم اپل موزیک/اسپاتیفای ارسال کنید."
            )
            try:
                preview_path = os.path.join(downloader.download_dir, f"{metadata.id}_preview.mp3")
                with open(preview_path, 'wb') as f:
                    f.write(requests.get(metadata.preview_url, timeout=10).content)
                
                with open(preview_path, 'rb') as audio:
                    await update.message.reply_audio(
                        audio=audio,
                        title=f"{metadata.title} (Preview)",
                        performer=metadata.artist
                    )
                os.remove(preview_path)
                await status_message.delete()
                return
            except:
                pass
        
        await status_message.edit_text(
            "❌ متاسفانه آهنگی پیدا نشد.\n\n"
            "لطفاً:\n"
            "• لینک آهنگ معتبر اپل موزیک/اسپاتیفای ارسال کنید\n"
            "• یا نام آهنگ و خواننده را دقیق‌تر وارد کنید"
        )

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in .env")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started with Spotify + Apple Music support")
    application.run_polling()

if __name__ == '__main__':
    main()