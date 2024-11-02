import os
import logging
import yt_dlp
import asyncio
from pyrogram.types import Message
from config import DEFAULT_FFMPEG, DOWNLOADS_DIR, COOKIES_PATH
from bot.utils.compressor import compress_video
from bot.database.db_manager import Database

# Initialize logging
LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize the database
db = Database()

# Default yt-dlp options with cookies path
ydl_opts = {
    'quiet': False,
    'no_warnings': True,
    'age_limit': 100,
    'geo_bypass': True,
    'geo_bypass_country': 'US',
    'cookies': os.path.expanduser(COOKIES_PATH),  # Ensures cookies path is resolved
    'logger': LOGGER,
    'progress_hooks': [],
    'allow_multiple_video_streams': True,
    'allow_multiple_audio_streams': True,
    'merge_output_format': 'mp4'
}

# Throttle decorator to limit function calls
def throttle(rate_limit_seconds):
    """Decorator to throttle function calls."""
    def decorator(func):
        last_called = [None]  # Use a list to hold the timestamp

        async def wrapped(*args, **kwargs):
            now = asyncio.get_event_loop().time()
            if last_called[0] is None or (now - last_called[0] >= rate_limit_seconds):
                last_called[0] = now
                return await func(*args, **kwargs)
        return wrapped
    return decorator

def _on_progress(status_msg, loop):
    """Returns a function that acts as a progress hook for yt-dlp."""
    def hook(d):
        if d['status'] == 'finished':
            LOGGER.info("Download completed")
            if status_msg:
                asyncio.run_coroutine_threadsafe(status_msg.edit_text("Download completed successfully!"), loop)
        elif d['status'] == 'downloading':
            download_speed = d.get('speed', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            total_bytes = d.get('total_bytes', d.get('total_bytes_estimate', 0))
            if total_bytes:
                progress = downloaded_bytes / total_bytes * 100
                LOGGER.info(f"Download progress: {progress:.2f}%")
                if status_msg:
                    asyncio.run_coroutine_threadsafe(
                        update_progress(status_msg, progress),
                        loop
                    )

    return hook

async def get_video_formats(url):
    """Extracts video formats from a URL using cookies."""
    try:
        global ydl_opts
        # Ensure cookies are used in get_video_formats
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [
                {
                    'format_id': f.get('format_id'),
                    'ext': f.get('ext'),
                    'resolution': f.get('height'),
                    'fps': f.get('fps', 'N/A'),
                }
                for f in info.get('formats', [])
                if f.get('vcodec') != 'none' and (f.get('height', 0) >= 360) and (f.get('filesize') is not None and f.get('filesize') > 0)
            ]

            title = info.get('title', 'No title available')
            LOGGER.info("Formats extracted successfully")

            # Log available formats for the bot's response
            formatted_formats = [f"{fmt['resolution']}p ({fmt['ext']}, {fmt['fps']} FPS)" for fmt in formats]
            LOGGER.info(f"Available formats: {', '.join(formatted_formats)}")

            return formats, title
    except Exception as e:
        LOGGER.error(f"Error fetching video formats: {e}")
        return [], "Error"

@throttle(5)  # Throttle updates to every 5 seconds
async def update_progress(status_msg: Message, progress: float):
    """Update progress message in a throttled manner."""
    try:
        if status_msg:
            await status_msg.edit_text(f"Downloading... {progress:.2f}% completed")
    except Exception as e:
        if "MESSAGE_ID_INVALID" in str(e):
            LOGGER.error("Failed to update progress: The message ID is invalid. It may have been deleted or expired.")
        else:
            LOGGER.error(f"Failed to update progress: {e}")

async def download_video(url, format_id, output_path, status_msg):
    """Downloads video based on a specified format_id using cookies."""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        loop = asyncio.get_event_loop()

        download_opts = {
            'format': f"{format_id}+bestaudio/best",
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': True,
            'cookies': os.path.expanduser(COOKIES_PATH),  # Ensures cookies path is resolved
            'logger': LOGGER,
            'progress_hooks': [_on_progress(status_msg, loop)],
            'merge_output_format': 'mp4'
        }

        with yt_dlp.YoutubeDL(download_opts) as ydl:
            ydl.download([url])
            LOGGER.info("Download completed successfully")

            if os.path.exists(output_path):
                LOGGER.info(f"Output file exists: {output_path}")
                return True
            else:
                LOGGER.error("Output path does not exist after download.")
                return False
    except yt_dlp.DownloadError as e:
        LOGGER.error(f"Download error: {e}")
        return False
    except Exception as e:
        LOGGER.error(f"Unexpected error: {e}")
        return False
