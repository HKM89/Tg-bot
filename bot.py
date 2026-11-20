"""Telegram bot: stamp photos with time, timezone and location.

Usage in Telegram:
  1. Send a photo (as photo or as file).
  2. In the caption, or in the next message, send:
        Jul 22, 2025 11:14:23 AM
        40.844934, -73.922545
     or with an address instead of coordinates:
        Jul 22, 2025 11:14:23 AM
        Cross Bronx Expy, Bronx, NY 10452
"""
from __future__ import annotations

import asyncio
import io
import logging
import os

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from geo import InputError, build_stamp
from stamp import stamp_image

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
log = logging.getLogger("stampbot")

HELP = (
    "📸 Send me a photo, then send the time and location:\n\n"
    "With coordinates (address is found automatically):\n"
    "<code>Jul 22, 2025 11:14:23 AM\n40.844934, -73.922545</code>\n\n"
    "With an address (coordinates will NOT be printed):\n"
    "<code>Jul 22, 2025 11:14:23 AM\nCross Bronx Expy, Bronx, NY 10452</code>\n\n"
    "• Time is taken as local time at that place; the time zone (EDT, PST…) is detected "
    "from the location.\n"
    "• Write <code>now</code> as the time to use the current time.\n"
    "• You can put everything in the photo caption too.\n"
    "• Send the photo as a <i>file</i> to keep full quality."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg.photo:
        file_id = msg.photo[-1].file_id
    else:
        file_id = msg.document.file_id
    context.user_data["photo_id"] = file_id

    if msg.caption:
        await process(update, context, msg.caption)
    else:
        await msg.reply_html(
            "Got the photo ✅ Now send the time and the location (coordinates or address).\n"
            "Example:\n<code>Jul 22, 2025 11:14:23 AM\n40.844934, -73.922545</code>"
        )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "photo_id" not in context.user_data:
        await update.message.reply_text("Please send a photo first 📸")
        return
    await process(update, context, update.message.text)


async def process(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    msg = update.message
    await msg.chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        stamp = await asyncio.to_thread(build_stamp, text)
    except InputError as e:
        await msg.reply_text(f"⚠️ {e}\n\nSend /help for the format.")
        return
    except Exception:
        log.exception("geocoding failed")
        await msg.reply_text("⚠️ Location service error, please try again in a moment.")
        return

    tg_file = await context.bot.get_file(context.user_data["photo_id"])
    data = bytes(await tg_file.download_as_bytearray())
    result = await asyncio.to_thread(stamp_image, data, stamp.lines)

    caption = f"🕒 Time zone: {stamp.tz_name}"
    await msg.reply_photo(io.BytesIO(result), caption=caption)
    await msg.reply_document(io.BytesIO(result), filename="stamped.jpg",
                             caption="Full quality file")
    context.user_data.pop("photo_id", None)


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set the TELEGRAM_BOT_TOKEN environment variable (get it from @BotFather).")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
