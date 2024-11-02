import os
import logging
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import subprocess
import time
from config import DOWNLOADS_DIR

# Initialize logger with custom format
LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

def create_format_buttons(formats):
    """Creates an inline keyboard with video format options in two-column layout."""
    buttons = []
    row = []
    for format in formats:
        format_id = format['format_id']
        resolution = format['resolution']
        ext = format['ext']
        fps = format.get('fps', 'N/A')  # Default to 'N/A' if fps is not available
        
        # Create a button with resolution, format, and fps
        button_label = f"{resolution} ({ext}, {fps} FPS)"
        row.append(InlineKeyboardButton(button_label, callback_data=f"dl_{format_id}"))

        # Add the row to buttons every two buttons
        if len(row) == 2:
            buttons.append(row)
            row = []  # Reset row for the next set of buttons

    # Add any remaining buttons
    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)

def format_size(size_bytes):
    """Convert a file size in bytes into a human-readable string."""
    if size_bytes is None or size_bytes < 0:
        return "N/A"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def clean_files(*files):
    """Remove specified files if they exist."""
    for file in files:
        try:
            if os.path.exists(file):
                if os.path.isfile(file):
                    os.remove(file)
                    LOGGER.info(f"Deleted file: {file}")
                else:
                    LOGGER.warning(f"Skipped deletion. {file} is a directory.")
            else:
                LOGGER.info(f"File not found and skipped: {file}")
        except Exception as e:
            LOGGER.error(f"Failed to delete file {file}: {e}")

async def progress(current, total, message, text="Downloading", last_update=None):
    """Update progress message with current download percentage."""
    try:
        if last_update is None:
            last_update = time.time()  # Set last_update to current time if it's None
        
        percent = current * 100 / total
        current_time = time.time()
        
        # Update progress message every 5 seconds
        if current_time - last_update >= 5:
            await message.edit_text(
                text=f"{text}\n{percent:.1f}% completed"
            )
            return current_time  # Return the current time as the new last_update
        return last_update  # Return the original last_update if no update occurred

    except Exception as e:
        LOGGER.error(f"Failed to update progress: {e}")

async def get_video_duration(video_path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return round(float(result.stdout)) if result.returncode == 0 else None

async def take_screenshot(path):
    """Capture a screenshot from the video and save it as thumb.jpg in DOWNLOADS_DIR."""
    thumb_path = os.path.join(DOWNLOADS_DIR, "thumb.jpg")
    try:
        subprocess.call(["ffmpeg", "-i", path, "-ss", "00:00:01.000", "-vframes", "1", thumb_path])
        LOGGER.info(f"Screenshot taken and saved to {thumb_path}")
    except Exception as e:
        LOGGER.error(f"Failed to take screenshot: {e}")
    return thumb_path
