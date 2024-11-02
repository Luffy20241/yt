from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
import os
import asyncio
import re
from .database.db_manager import Database
from .utils.downloader import get_video_formats, download_video
from .utils.compressor import compress_video
from .utils.helpers import create_format_buttons, clean_files, progress, get_video_duration, take_screenshot
from config import API_ID, API_HASH, BOT_TOKEN, DUMP_CHANNEL, DOWNLOADS_DIR, AUTH_USERS
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

ENCODE_DIR = os.path.join(DOWNLOADS_DIR, "encode")
os.makedirs(ENCODE_DIR, exist_ok=True)  # Ensure the encode directory exists

class Bot:
    def __init__(self):
        logging.info("Initializing bot...")
        self.app = Client(
            "video_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
        self.db = Database()
        self.tasks = []  # Track ongoing tasks
        self.video_urls = {}  # Define video URLs dictionary here
        self.setup_handlers()

    def setup_handlers(self):
        logging.info("Setting up handlers...")

        def restricted_command(func):
            async def wrapper(client, message: Message):
                if message.from_user is None:
                    await message.reply_text("This command can only be used in a personal chat.")
                    return

                user_id = message.from_user.id
                chat_id = message.chat.id

                logging.info(f"Checking authorization for user_id: {user_id}, chat_id: {chat_id}")

                is_authorized_user = await self.db.is_user_authorized(user_id)
                is_authorized_group = await self.db.is_group_authorized(chat_id)

                if is_authorized_user or is_authorized_group or user_id in AUTH_USERS:
                    await func(client, message)
                else:
                    await message.reply_text("You are not authorized to use this bot. Please contact the owner.")
            return wrapper

        @self.app.on_message(filters.command("start"))
        async def start_command(_, message: Message):
            logging.info("Received /start command")
            await message.reply_text(
                "Hello! I can help you download and compress videos.\n"
                "Commands:\n"
                "/yl <url> - Download YouTube video\n"
                "/set <ffmpeg_code> - Set custom FFmpeg code\n"
                "/add - Reply to video/document to compress\n"
                "/cancel - Cancel ongoing tasks\n"
                "/permit <user_id> - Authorize a specific user (owner only)\n"
                "/authorize - Authorize a group (owner only)"
            )

        @self.app.on_message(filters.command("cancel"))
        @restricted_command
        async def cancel_tasks(_, message: Message):
            logging.info("Received /cancel command")
            if not self.tasks:
                await message.reply_text("No ongoing tasks to cancel.")
                return
            
            for task in self.tasks:
                task.cancel()  # Cancel the task
            self.tasks.clear()  # Clear the task list
            await message.reply_text("All ongoing tasks have been canceled.")

        @self.app.on_message(filters.command("permit") & filters.user(AUTH_USERS))
        async def permit_user(_, message: Message):
            logging.info("Received /permit command")
            if len(message.command) < 2:
                await message.reply_text("Please provide a user ID to permit.")
                return
            try:
                user_id = int(message.command[1])
                await self.db.add_authorized_user(user_id)
                await message.reply_text(f"User {user_id} has been granted access.")
                logging.info(f"User {user_id} authorized.")
            except ValueError:
                await message.reply_text("Invalid user ID.")

        @self.app.on_message(filters.command("authorize") & filters.group & filters.user(AUTH_USERS))
        async def authorize_group(_, message: Message):
            logging.info("Received /authorize command")
            group_id = message.chat.id
            await self.db.add_authorized_group(group_id)
            await message.reply_text("This group is now authorized to use the bot.")
        
        @self.app.on_message(filters.group)
        async def group_message_handler(_, message: Message):
            group_id = message.chat.id
            if not await self.db.is_group_authorized(group_id):
                await message.reply_text("This group is not authorized to use the bot.")
                return
            # Continue with other functionality
        

        @self.app.on_message(filters.command("yl"))
        @restricted_command
        async def youtube_command(_, message: Message):
            logging.info("Received /yl command")
            if len(message.command) < 2:
                await message.reply_text("Please provide a YouTube URL")
                return

            status_msg = await message.reply_text("Fetching video information...")
            try:
                url = message.text.split(None, 1)[1]
                formats, title = await get_video_formats(url)
                keyboard = create_format_buttons(formats)

                await status_msg.edit_text(
                    f"Select format for: {title}",
                    reply_markup=keyboard
                )
                user_id = message.from_user.id
                self.video_urls[user_id] = url  # Store video URL in the dictionary
            except Exception as e:
                await status_msg.edit_text(f"Error: {str(e)}")
                logging.error(f"Error in youtube_command: {e}")

        @self.app.on_callback_query(filters.regex(r"^dl_"))
        async def download_callback(_, callback_query: CallbackQuery):
            format_id = callback_query.data.split("_")[1]
            user_id = callback_query.from_user.id
            url = self.video_urls.get(user_id)  # Use the instance variable here

            if not url:
                await callback_query.answer("Session expired. Please try again.", show_alert=True)
                return

            await callback_query.answer("Processing...")
            status_msg = await callback_query.message.reply_text("Downloading...")

            input_path = None
            output_path = None

            try:
                formats, title = await get_video_formats(url)
                sanitized_title = re.sub(r'[^\w\-_\.]', '_', title).strip()
                input_path = os.path.join(DOWNLOADS_DIR, f"{sanitized_title}.mp4")
                output_path = os.path.join(ENCODE_DIR, f"{sanitized_title}_compressed.mp4")

                download_task = asyncio.create_task(
                    download_video(url, format_id, input_path, status_msg)
                )
                self.tasks.append(download_task)
                success = await download_task

                if success and os.path.exists(input_path):
                    await self.app.send_video(
                        DUMP_CHANNEL,
                        input_path,
                        progress=progress,
                        progress_args=(status_msg, "Uploading to dump channel...")
                    )

                    ffmpeg_code = await self.db.get_ffmpeg_code(user_id)
                    await status_msg.edit_text("Compressing...")
                    
                    compress_task = asyncio.create_task(
                        compress_video(input_path, output_path, ffmpeg_code)
                    )
                    self.tasks.append(compress_task)
                    success = await compress_task

                    if success and os.path.exists(output_path):
                        duration = await get_video_duration(output_path)
                        thumb_image_path = await take_screenshot(output_path)

                        await self.app.send_video(
                            callback_query.message.chat.id,
                            output_path,
                            caption=f"{sanitized_title}\nDuration: {duration} seconds",
                            duration=duration,
                            thumb=thumb_image_path,
                            width=1280,
                            height=720,
                            reply_to_message_id=callback_query.message.id,
                            progress=progress,
                            progress_args=(status_msg, "Uploading compressed video...")
                        )
                        await status_msg.delete()
                        if os.path.exists(thumb_image_path):
                            os.remove(thumb_image_path)
                    else:
                        await status_msg.edit_text("Compression failed!")
                else:
                    await status_msg.edit_text("Download failed!")
            except Exception as e:
                await status_msg.edit_text(f"Error: {str(e)}")
                logging.error(f"Error in download_callback: {e}")
            finally:
                clean_files(input_path, output_path)
                if user_id in self.video_urls:
                    del self.video_urls[user_id]

        @self.app.on_message(filters.command("get"))
        @restricted_command
        async def get_ffmpeg(_, message: Message):
            logging.info("Received /get command")
            try:
                user_id = message.from_user.id
                ffmpeg_code = await self.db.get_ffmpeg_code(user_id)
                
                if ffmpeg_code:
                    await message.reply_text(
                        f"Your current FFmpeg code is:<br><code>{ffmpeg_code}</code>",
                    )
                else:
                    await message.reply_text(
                        "You haven't set any FFmpeg code yet.<br>"
                        "Use /set <ffmpeg_code> to set your compression preferences.",
                    )
            except Exception as e:
                await message.reply_text(f"Error retrieving FFmpeg code: {str(e)}")
                logging.error(f"Error in get_ffmpeg command: {e}")

        @self.app.on_message(filters.command("set"))
        @restricted_command
        async def set_ffmpeg(_, message: Message):
            logging.info("Received /set command")
            if len(message.command) < 2:
                await message.reply_text("Please provide FFmpeg code.")
                return

            user_id = message.from_user.id
            ffmpeg_code = message.text.split(None, 1)[1]

            await self.db.set_ffmpeg_code(user_id, ffmpeg_code)
            await message.reply_text("Your FFmpeg code has been set!")
        @self.app.on_message(filters.command("add") & filters.reply)
        async def compress_command(_, message: Message):
            replied = message.reply_to_message
            if not (replied.video or replied.document):
                await message.reply_text("Please reply to a video/document")
                return

            status_msg = await message.reply_text("Processing...")
            input_path = None
            output_path = None

            try:
                title = replied.video.file_name if replied.video else replied.document.file_name
                sanitized_title = re.sub(r'[^\w\-_\.]', '_', title).strip()
                input_path = os.path.join(DOWNLOADS_DIR, f"{sanitized_title}_input.mp4")
                
                # Create a task for downloading
                download_task = asyncio.create_task(
                    replied.download(input_path, progress=progress, progress_args=(status_msg, "Downloading..."))
                )
                self.tasks.append(download_task)
                await download_task

                # Forward the file to the dump channel
                await replied.forward(DUMP_CHANNEL)

                # Compress and save in ENCODE_DIR
                output_path = os.path.join(ENCODE_DIR, f"{sanitized_title}_compressed.mp4")
                ffmpeg_code = await self.db.get_ffmpeg_code(message.from_user.id)  # Ensure this is awaited
                
                await status_msg.edit_text("Compressing...")
                
                # Create a task for compression
                compress_task = asyncio.create_task(
                    compress_video(input_path, output_path, ffmpeg_code)
                )
                self.tasks.append(compress_task)
                success = await compress_task

                if success and os.path.exists(output_path):
                    duration = await get_video_duration(output_path)
                    thumb_image_path = await take_screenshot(output_path)
                    
                    await self.app.send_video(
                        message.chat.id,
                        output_path,
                        caption=sanitized_title,
                        duration=duration,
                        thumb=thumb_image_path,
                        width=1280,
                        height=720,
                        progress=progress,
                        progress_args=(status_msg, "Uploading compressed video...")
                    )
                    await status_msg.delete()
                    if os.path.exists(thumb_image_path):
                        os.remove(thumb_image_path)
                else:
                    await status_msg.edit_text("Compression failed! Please try again later.")
            except Exception as e:
                await status_msg.edit_text(f"Error: {str(e)}")
            finally:
                clean_files(input_path, output_path)

            @self.app.on_message(filters.forwarded & (filters.video | filters.document))
            async def compress_command(_, message: Message):
                replied = message.reply_to_message
                if not (replied.video or replied.document):
                    await message.reply_text("Please forward a video or document.")
                    return

                status_msg = await message.reply_text("Processing...")

                input_path = None
                output_path = None

                try:
                    title = replied.video.file_name if replied.video else replied.document.file_name
                    sanitized_title = re.sub(r'[^\w\-_\.]', '_', title).strip()
                    input_path = os.path.join(DOWNLOADS_DIR, f"{sanitized_title}_input.mp4")
                    
                    # Create a task for downloading
                    download_task = asyncio.create_task(
                        replied.download(input_path, progress=progress, progress_args=(status_msg, "Downloading..."))
                    )
                    self.tasks.append(download_task)
                    await download_task

                    # Forward the file to the dump channel
                    await replied.forward(DUMP_CHANNEL)

                    # Compress and save in ENCODE_DIR
                    output_path = os.path.join(ENCODE_DIR, f"{sanitized_title}_compressed.mp4")
                    ffmpeg_code = await self.db.get_ffmpeg_code(message.from_user.id)  # Make sure this is awaited
                    
                    await status_msg.edit_text("Compressing...")
                    
                    # Create a task for compression
                    compress_task = asyncio.create_task(
                        compress_video(input_path, output_path, ffmpeg_code)
                    )
                    self.tasks.append(compress_task)
                    success = await compress_task

                    if success and os.path.exists(output_path):
                        duration = await get_video_duration(output_path)
                        thumb_image_path = await take_screenshot(output_path)

                        await self.app.send_video(
                            message.chat.id,
                            output_path,
                            caption=sanitized_title,
                            duration=duration,
                            thumb=thumb_image_path,
                            width=1280,
                            height=720,
                            progress=progress,
                            progress_args=(status_msg, "Uploading compressed video...")
                        )
                        await status_msg.delete()
                        if os.path.exists(thumb_image_path):
                            os.remove(thumb_image_path)
                    else:
                        await status_msg.edit_text("Compression failed! Please try again later.")
                except Exception as e:
                    await status_msg.edit_text(f"Error: {str(e)}")
                finally:
                    clean_files(input_path, output_path)


    async def run(self):
        await self.app.start()  # This starts the bot and its tasks
        logging.info("Bot is running...")
        await asyncio.Event().wait()  # Keep the bot running indefinitely
# Ensure the bot is not run directly
if __name__ == "__main__":
    bot = Bot()
    asyncio.run(bot.run())      