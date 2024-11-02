# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Pyrogram credentials
API_ID = int(os.getenv('API_ID','18530329'))
API_HASH = os.getenv('API_HASH','edefebe693e029e6aca6c7c1df2745ec')
BOT_TOKEN = os.getenv('BOT_TOKEN','7936026368:AAGUVaduGFrc6XwUy9BOrCX0gcNdTytO_xE')

# Channel IDs
DUMP_CHANNEL = int(os.getenv('DUMP_CHANNEL','-1001930986503'))

# Default FFmpeg code
DEFAULT_FFMPEG = '-c:v copy -c:a copy -c:s copy -map 0'

# Database
DB_NAME = 'bot_data.db'

# Downloads directory
DOWNLOADS_DIR = 'downloads'
COOKIES_PATH = '~/cookies.txt'
FFMPEG_LOCATION = '/usr/bin/vegapunk'  # Replace with your actual FFmpeg path
# config.py
AUTH_USERS = [1908235162]  # Replace with your authorized user IDs
