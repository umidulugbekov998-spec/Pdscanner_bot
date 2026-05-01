"""
main.py — Bot entry point.

Initialises the database, registers all handlers, and starts polling.
Run with:  python main.py
"""

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

import database as db
from handlers import router
from config import BOT_TOKEN, OPENAI_API_KEY
import utils  # patch OPENAI_API_KEY into the utils module

# ── Patch the OpenAI key from config into utils if not already in env ─────────
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    utils.openai_client = utils.AsyncOpenAI(api_key=OPENAI_API_KEY)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt= "%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main():
    # 1. Initialise SQLite database (creates tables if they don't exist)
    await db.init_db()
    logger.info("🗄️  Database ready.")

    # 2. Create the Bot instance
    #    DefaultBotProperties sets HTML / Markdown as the default parse_mode
    bot = Bot(
        token   = BOT_TOKEN,
        default = DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    # 3. Create the Dispatcher with in-memory FSM storage
    #    For production you can swap MemoryStorage() with RedisStorage()
    dp = Dispatcher(storage=MemoryStorage())

    # 4. Register all handlers from handlers.py
    dp.include_router(router)

    # 5. Drop pending updates (so old messages don't get replayed on restart)
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("🚀 Bot is starting — long-polling…")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("👋 Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
