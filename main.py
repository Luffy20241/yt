import logging
import os
import asyncio
from bot.client import Bot
from config import DOWNLOADS_DIR

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Change to DEBUG for detailed logging
)

async def main():
    # Create downloads directory if it doesn't exist
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    logging.info("Downloads directory checked/created.")

    # Start bot
    bot = Bot()
    
    # Initialize the database
    await bot.db.initialize()
    logging.info("Database initialized.")

    await bot.run()  # Ensure this calls the correct run method of the bot

if __name__ == '__main__':
    try:
        asyncio.run(main())  # Start the main async function
    except KeyboardInterrupt:
        logging.info("Bot shutdown initiated.")
    except Exception as e:
        logging.error(f"An error occurred while starting the bot: {e}")
