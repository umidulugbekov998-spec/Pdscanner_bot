# main.py — Barcha handlerlar ulangan to'liq versiya

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

import database as db
from handlers import router as main_router
from features_handlers import router as features_router
from config import BOT_TOKEN, OPENAI_API_KEY
import utils

if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    from openai import AsyncOpenAI
    utils.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main():
    await db.init_db()
    logger.info("🗄️  Database tayyor.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(features_router)
    dp.include_router(main_router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🚀 Bot ishga tushmoqda…")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("👋 Bot to'xtatildi.")


if __name__ == "__main__":
    asyncio.run(main())
