# Apple Music Downloader Telegram Bot

A fully functional Python Telegram bot that downloads music from Apple Music links using a YouTube Music fallback approach.

## Features
- **Metadata Extraction:** Automatically fetches title, artist, album, and high-quality artwork from Apple Music.
- **High-Quality Audio:** Downloads audio via `yt-dlp` (YouTube Music) and converts it to 256kbps MP3.
- **ID3 Tagging:** Embeds metadata and album art directly into the MP3 file.
- **Rate Limiting:** Prevents abuse with a configurable download limit (default: 10 downloads/hour).
- **Admin Stats:** Monitor bot usage with the `/stats` command.
- **Cleanup:** Automatically removes temporary files after sending.

## Prerequisites
- Python 3.10+
- FFmpeg installed and added to PATH
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd apple_music_bot
   ```

2. **Set up a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Create a `.env` file in the root directory:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   ADMIN_ID=your_telegram_user_id
   ```

## Usage
Run the bot:
```bash
python main.py
```

Send an Apple Music link to the bot, and it will process and send the MP3 file back to you.

## Project Structure
- `main.py`: Bot entry point and Telegram handlers.
- `metadata.py`: Apple Music scraping and metadata extraction.
- `downloader.py`: Audio downloading, conversion, and ID3 tagging.
- `user_manager.py`: User session and rate limit management.
- `downloads/`: Temporary directory for processing files.

## License
MIT
