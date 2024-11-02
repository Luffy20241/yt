import aiosqlite
import logging
from config import DB_NAME, DEFAULT_FFMPEG

# Initialize logger
LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

class Database:
    def __init__(self):
        self.db_name = DB_NAME

    async def initialize(self):
        """Initialize the database by creating necessary tables."""
        await self.create_tables()

    async def create_tables(self):
        """Create tables if they don't exist."""
        async with aiosqlite.connect(self.db_name) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS authorized_users (
                    user_id INTEGER PRIMARY KEY
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS authorized_groups (
                    group_id INTEGER PRIMARY KEY
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS ffmpeg_settings (
                    user_id INTEGER PRIMARY KEY,
                    ffmpeg_code TEXT
                )
            ''')
            await conn.commit()
        LOGGER.info("Database tables created or verified.")

    async def add_authorized_user(self, user_id):
        """Add a user to the authorized_users table."""
        async with aiosqlite.connect(self.db_name) as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO authorized_users (user_id) VALUES (?)",
                (user_id,)
            )
            await conn.commit()
        LOGGER.info(f"User {user_id} authorized.")

    async def remove_authorized_user(self, user_id):
        """Remove a user from the authorized_users table."""
        async with aiosqlite.connect(self.db_name) as conn:
            await conn.execute(
                "DELETE FROM authorized_users WHERE user_id = ?",
                (user_id,)
            )
            await conn.commit()
        LOGGER.info(f"User {user_id} authorization removed.")

    async def is_user_authorized(self, user_id):
        """Check if a user is authorized."""
        async with aiosqlite.connect(self.db_name) as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM authorized_users WHERE user_id = ?",
                (user_id,)
            )
            result = await cursor.fetchone()
            return result is not None

    async def add_authorized_group(self, group_id):
        """Add a group to the authorized_groups table."""
        async with aiosqlite.connect(self.db_name) as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO authorized_groups (group_id) VALUES (?)",
                (group_id,)
            )
            await conn.commit()
        LOGGER.info(f"Group {group_id} authorized.")

    async def remove_authorized_group(self, group_id):
        """Remove a group from the authorized_groups table."""
        async with aiosqlite.connect(self.db_name) as conn:
            await conn.execute(
                "DELETE FROM authorized_groups WHERE group_id = ?",
                (group_id,)
            )
            await conn.commit()
        LOGGER.info(f"Group {group_id} authorization removed.")

    async def is_group_authorized(self, group_id):
        """Check if a group is authorized."""
        async with aiosqlite.connect(self.db_name) as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM authorized_groups WHERE group_id = ?",
                (group_id,)
            )
            result = await cursor.fetchone()
            return result is not None

    async def set_ffmpeg_code(self, user_id, ffmpeg_code):
        """Set or update the ffmpeg code for a specific user."""
        async with aiosqlite.connect(self.db_name) as conn:
            await conn.execute(
                '''
                INSERT INTO ffmpeg_settings (user_id, ffmpeg_code)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET ffmpeg_code = excluded.ffmpeg_code
                ''',
                (user_id, ffmpeg_code)
            )
            await conn.commit()
        LOGGER.info(f"FFmpeg code for user {user_id} set to: {ffmpeg_code}")

    async def get_ffmpeg_code(self, user_id):
        """Retrieve the ffmpeg code for a user, or use the default if none is set."""
        async with aiosqlite.connect(self.db_name) as conn:
            cursor = await conn.execute(
                "SELECT ffmpeg_code FROM ffmpeg_settings WHERE user_id = ?",
                (user_id,)
            )
            result = await cursor.fetchone()
            ffmpeg_code = result[0] if result else DEFAULT_FFMPEG
        LOGGER.info(f"Retrieved FFmpeg code for user {user_id}: {ffmpeg_code}")
        return ffmpeg_code
