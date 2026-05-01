"""
handlers.py — All aiogram 3.x message / callback handlers.

Structure
---------
  • User registration middleware
  • /start, /help, /premium commands
  • Scan mode selection (A4, Passport, ID Card, Photo)
  • Filter selection (Magic Color, B&W)
  • Image processing pipeline
  • AI assistant (ask questions about scanned docs)
  • Premium purchase flow (upload receipt → admin approval)
  • Admin panel (set card number, broadcast, approve/decline payments)
"""

import io
import logging
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, BufferedInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import utils
from config import ADMIN_ID, WATERMARK_TEXT, BOT_USERNAME

logger = logging.getLogger(__name__)
router = Router()


# ─────────────────────────────────────────────────────────────────────────────
#  FSM STATE GROUPS
# ─────────────────────────────────────────────────────────────────────────────

class ScanSession(StatesGroup):
    """Tracks the user's active scan: which mode/filter, buffered images."""
    choosing_mode    = State()
    choosing_filter  = State()
    collecting_images = State()
    waiting_ai_question = State()


class AdminStates(StatesGroup):
    """Admin FSM: awaiting broadcast text or new card number."""
    waiting_broadcast_msg = State()
    waiting_card_number   = State()


class PaymentStates(StatesGroup):
    """User FSM: waiting for the user to upload their payment receipt."""
    waiting_receipt = State()


# ─────────────────────────────────────────────────────────────────────────────
#  KEYBOARDS — helper functions
# ─────────────────────────────────────────────────────────────────────────────

def main_menu_kb(is_premium: bool = False) -> InlineKeyboardMarkup:
    """Main menu shown after /start."""
    plan_label = "⭐ Premium Active" if is_premium else "💎 Get Premium"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 Scan Document", callback_data="scan_start"),
            InlineKeyboardButton(text="🤖 AI Assistant",  callback_data="ai_start"),
        ],
        [
            InlineKeyboardButton(text=plan_label,          callback_data="premium_info"),
            InlineKeyboardButton(text="📞 Contact Admin",  callback_data="contact_admin"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Help",           callback_data="help"),
        ],
    ])


def mode_selection_kb() -> InlineKeyboardMarkup:
    """Scan mode picker."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 A4 Document", callback_data="mode_a4"),
            InlineKeyboardButton(text="🛂 Passport",   callback_data="mode_passport"),
        ],
        [
            InlineKeyboardButton(text="🪪 ID Card",    callback_data="mode_id_card"),
            InlineKeyboardButton(text="🖼 Photo",       callback_data="mode_photo"),
        ],
        [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")],
    ])


def filter_selection_kb() -> InlineKeyboardMarkup:
    """Filter picker shown after mode is chosen."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✨ Magic Color", callback_data="filter_magic_color"),
            InlineKeyboardButton(text="⚫ B&W",          callback_data="filter_bw"),
        ],
        [
            InlineKeyboardButton(text="🎨 No Filter",   callback_data="filter_none"),
        ],
        [InlineKeyboardButton(text="🔙 Back", callback_data="scan_start")],
    ])


def ready_to_process_kb() -> InlineKeyboardMarkup:
    """Shown while user is sending images; lets them trigger PDF generation."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Generate PDF",    callback_data="generate_pdf")],
        [InlineKeyboardButton(text="🗑 Clear & Restart", callback_data="clear_session")],
    ])


def admin_panel_kb() -> InlineKeyboardMarkup:
    """Admin control panel."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Set Card Number", callback_data="admin_set_card")],
        [InlineKeyboardButton(text="📢 Broadcast",       callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Statistics",      callback_data="admin_stats")],
    ])


def payment_approval_kb(request_id: int) -> InlineKeyboardMarkup:
    """Approve / Decline buttons forwarded to admin with the receipt."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve",  callback_data=f"pay_approve:{request_id}"),
            InlineKeyboardButton(text="❌ Decline",  callback_data=f"pay_decline:{request_id}"),
        ]
    ])


# ─────────────────────────────────────────────────────────────────────────────
#  REGISTRATION HELPER
# ─────────────────────────────────────────────────────────────────────────────

async def register_user(message: Message):
    """Ensure the user exists in the database before any handler runs."""
    user = message.from_user
    await db.add_or_update_user(
        user_id   = user.id,
        username  = user.username,
        full_name = user.full_name,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  /START
# ─────────────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await register_user(message)
    await state.clear()

    user      = message.from_user
    premium   = await db.is_premium(user.id)
    plan_text = "⭐ **Premium**" if premium else "🆓 **Free**"

    text = (
        f"👋 Welcome, **{user.first_name}**!\n\n"
        f"🤖 I'm your **AI Document Scanner** — powered by advanced CV and GPT-4o.\n\n"
        f"📌 Your current plan: {plan_text}\n\n"
        f"What would you like to do today?"
    )
    await message.answer(text, parse_mode="Markdown",
                         reply_markup=main_menu_kb(premium))


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN MENU callback
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user    = call.from_user
    premium = await db.is_premium(user.id)
    await call.message.edit_text(
        f"🏠 **Main Menu** — choose an action:",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(premium)
    )
    await call.answer()


@router.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery):
    text = (
        "ℹ️ **How to use the bot**\n\n"
        "1️⃣ Tap **Scan Document** and choose a mode.\n"
        "2️⃣ Select a filter (Magic Color or B&W).\n"
        "3️⃣ Send one or more photos.\n"
        "4️⃣ Tap **Generate PDF** to download your file.\n\n"
        "🤖 Use **AI Assistant** to ask questions about any scanned image.\n\n"
        "💎 **Premium** users get:\n"
        "  • No watermarks\n"
        "  • Faster processing\n"
        "  • Higher output quality\n\n"
        "📞 Tap **Contact Admin** for support."
    )
    await call.message.edit_text(text, parse_mode="Markdown",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                     [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
                                 ]))
    await call.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  CONTACT ADMIN
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "contact_admin")
async def cb_contact_admin(call: CallbackQuery):
    await call.message.edit_text(
        f"📞 **Contact Admin**\n\n"
        f"For support, billing questions, or feedback:\n"
        f"👤 [@{BOT_USERNAME}_admin](tg://user?id={ADMIN_ID})\n\n"
        f"Or send a direct message — the admin will respond as soon as possible.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
        ])
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  PREMIUM INFO & PURCHASE FLOW
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "premium_info")
async def cb_premium_info(call: CallbackQuery, state: FSMContext):
    user    = call.from_user
    premium = await db.is_premium(user.id)

    if premium:
        await call.message.edit_text(
            "⭐ You already have **Premium** access!\n\n"
            "Enjoy watermark-free PDFs and high-quality scans.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
            ])
        )
    else:
        card = await db.get_setting("card_number", "Not set — contact admin.")
        await call.message.edit_text(
            "💎 **Upgrade to Premium**\n\n"
            "✅ No watermarks on PDFs\n"
            "✅ High-speed processing\n"
            "✅ Maximum image quality\n"
            "✅ Unlimited scans\n\n"
            f"💳 **Payment Card:** `{card}`\n\n"
            "After payment, tap the button below and upload a screenshot of your receipt. "
            "The admin will verify and activate your premium within minutes.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Upload Receipt", callback_data="upload_receipt")],
                [InlineKeyboardButton(text="🔙 Back",           callback_data="main_menu")],
            ])
        )
    await call.answer()


@router.callback_query(F.data == "upload_receipt")
async def cb_upload_receipt(call: CallbackQuery, state: FSMContext):
    await state.set_state(PaymentStates.waiting_receipt)
    await call.message.edit_text(
        "📸 Please send a **screenshot** of your payment receipt.\n\n"
        "The admin will review and activate your Premium plan shortly.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="main_menu")]
        ])
    )
    await call.answer()


@router.message(PaymentStates.waiting_receipt, F.photo)
async def handle_payment_receipt(message: Message, state: FSMContext, bot: Bot):
    """User uploaded a payment receipt photo → forward to admin for review."""
    await state.clear()
    user = message.from_user

    # Create a pending payment request in the DB
    request_id = await db.create_payment_request(user.id)

    # Forward the screenshot to the admin with Approve / Decline buttons
    caption = (
        f"💳 **New Premium Payment Request**\n\n"
        f"👤 User: [{user.full_name}](tg://user?id={user.id})\n"
        f"🆔 User ID: `{user.id}`\n"
        f"🔖 Username: @{user.username or 'N/A'}\n"
        f"📋 Request ID: `{request_id}`"
    )
    sent = await bot.send_photo(
        chat_id     = ADMIN_ID,
        photo       = message.photo[-1].file_id,
        caption     = caption,
        parse_mode  = "Markdown",
        reply_markup = payment_approval_kb(request_id)
    )

    # Store the admin-side message_id so we could reference/edit it later
    await db.set_payment_admin_message(request_id, sent.message_id)

    await message.answer(
        "✅ Your receipt has been forwarded to the admin for review.\n"
        "You will receive a notification once your Premium is activated. ⏳",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
        ])
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ADMIN — Approve / Decline payments
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay_approve:"))
async def cb_pay_approve(call: CallbackQuery, bot: Bot):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Unauthorized.", show_alert=True)
        return

    request_id = int(call.data.split(":")[1])
    req        = await db.get_payment_request(request_id)
    if not req:
        await call.answer("❌ Request not found.", show_alert=True)
        return

    # Upgrade the user
    await db.set_premium(req["user_id"], True)
    await db.update_payment_status(request_id, "approved")

    # Notify the user
    await bot.send_message(
        req["user_id"],
        "🎉 **Congratulations!** Your payment has been verified.\n\n"
        "⭐ You are now a **Premium** member! Enjoy watermark-free PDFs and priority processing.",
        parse_mode="Markdown"
    )

    # Update the admin message
    await call.message.edit_caption(
        call.message.caption + "\n\n✅ **APPROVED**",
        parse_mode="Markdown"
    )
    await call.answer("✅ User upgraded to Premium!", show_alert=True)


@router.callback_query(F.data.startswith("pay_decline:"))
async def cb_pay_decline(call: CallbackQuery, bot: Bot):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Unauthorized.", show_alert=True)
        return

    request_id = int(call.data.split(":")[1])
    req        = await db.get_payment_request(request_id)
    if not req:
        await call.answer("❌ Request not found.", show_alert=True)
        return

    await db.update_payment_status(request_id, "declined")

    # Notify the user
    await bot.send_message(
        req["user_id"],
        "❌ Your payment receipt could not be verified.\n\n"
        "Please double-check the receipt and re-submit, or contact the admin for help.",
        parse_mode="Markdown"
    )

    # Update the admin message
    await call.message.edit_caption(
        call.message.caption + "\n\n❌ **DECLINED**",
        parse_mode="Markdown"
    )
    await call.answer("❌ Request declined.", show_alert=True)


# ─────────────────────────────────────────────────────────────────────────────
#  SCAN FLOW — Mode selection
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "scan_start")
async def cb_scan_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(ScanSession.choosing_mode)
    await call.message.edit_text(
        "📂 **Select Scan Mode**\n\n"
        "Choose the type of document you want to scan:",
        parse_mode="Markdown",
        reply_markup=mode_selection_kb()
    )
    await call.answer()


@router.callback_query(F.data.startswith("mode_"))
async def cb_mode_selected(call: CallbackQuery, state: FSMContext):
    mode = call.data.replace("mode_", "")
    mode_labels = {
        "a4":       "📄 A4 Document",
        "passport": "🛂 Passport",
        "id_card":  "🪪 ID Card",
        "photo":    "🖼 Photo",
    }
    await state.update_data(mode=mode, images=[])
    await state.set_state(ScanSession.choosing_filter)

    await call.message.edit_text(
        f"✅ Mode: **{mode_labels.get(mode, mode)}**\n\n"
        f"🎨 Now choose a filter to apply to your scans:",
        parse_mode="Markdown",
        reply_markup=filter_selection_kb()
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  SCAN FLOW — Filter selection
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("filter_"))
async def cb_filter_selected(call: CallbackQuery, state: FSMContext):
    filter_type = call.data.replace("filter_", "")
    filter_labels = {
        "magic_color": "✨ Magic Color",
        "bw":          "⚫ B&W",
        "none":        "🎨 No Filter",
    }
    await state.update_data(filter_type=filter_type)
    await state.set_state(ScanSession.collecting_images)

    await call.message.edit_text(
        f"✅ Filter: **{filter_labels.get(filter_type, filter_type)}**\n\n"
        f"📸 Now send your photos one by one.\n"
        f"When you're done, tap **Generate PDF**.",
        parse_mode="Markdown",
        reply_markup=ready_to_process_kb()
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  SCAN FLOW — Collect incoming photos
# ─────────────────────────────────────────────────────────────────────────────

@router.message(ScanSession.collecting_images, F.photo)
async def handle_scan_photo(message: Message, state: FSMContext, bot: Bot):
    """Buffer each incoming photo during the scan session."""
    data      = await state.get_data()
    images    = data.get("images", [])
    file_id   = message.photo[-1].file_id  # highest resolution

    images.append(file_id)
    await state.update_data(images=images)

    count = len(images)
    await message.answer(
        f"📸 Page **{count}** received.\n"
        f"Send more pages or tap **Generate PDF** when ready.",
        parse_mode="Markdown",
        reply_markup=ready_to_process_kb()
    )


# ─────────────────────────────────────────────────────────────────────────────
#  SCAN FLOW — Generate PDF
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "generate_pdf")
async def cb_generate_pdf(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Process all buffered images and return a single PDF."""
    data        = await state.get_data()
    file_ids    = data.get("images", [])
    mode        = data.get("mode", "a4")
    filter_type = data.get("filter_type", "magic_color")

    if not file_ids:
        await call.answer("⚠️ No images added yet! Send at least one photo.", show_alert=True)
        return

    user    = call.from_user
    premium = await db.is_premium(user.id)
    add_wm  = not premium

    await call.message.edit_text(
        f"⚙️ Processing **{len(file_ids)}** page(s)…\n"
        f"{'🆓 Watermark will be added (Free plan).' if add_wm else '⭐ Premium: no watermark.'}",
        parse_mode="Markdown"
    )

    processed_images = []
    for fid in file_ids:
        # Download the file from Telegram servers
        file_info  = await bot.get_file(fid)
        buf        = io.BytesIO()
        await bot.download_file(file_info.file_path, buf)
        raw_bytes  = buf.getvalue()

        # Run the full scan pipeline
        processed  = utils.process_image(
            img_bytes   = raw_bytes,
            mode        = mode,
            filter_type = filter_type,
            apply_crop  = True,
            watermark   = add_wm,
        )
        processed_images.append(processed)

    # Merge all pages into one PDF
    pdf_bytes = utils.images_to_pdf(processed_images)
    pages     = len(processed_images)

    # Send the PDF
    await bot.send_document(
        chat_id     = user.id,
        document    = BufferedInputFile(pdf_bytes, filename="scan.pdf"),
        caption     = (
            f"📄 Your scanned PDF is ready!\n"
            f"📑 Pages: {pages}\n"
            f"{'🆓 Watermark added. Upgrade to Premium for watermark-free PDFs!' if add_wm else '⭐ Premium: no watermark!'}"
        ),
    )

    # Clear the session and show main menu
    await state.clear()
    await bot.send_message(
        user.id,
        "✅ Done! What would you like to do next?",
        reply_markup=main_menu_kb(premium)
    )


@router.callback_query(F.data == "clear_session")
async def cb_clear_session(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🗑 Session cleared.\n\nStart a new scan from the main menu.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
        ])
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  AI ASSISTANT
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ai_start")
async def cb_ai_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(ScanSession.waiting_ai_question)
    await call.message.edit_text(
        "🤖 **AI Document Assistant**\n\n"
        "Send me a **photo** of your document together with your question, "
        "or just send the photo first and I'll ask you what you want to know.\n\n"
        "Examples:\n"
        "• _'What is this document about?'_\n"
        "• _'Translate the text to English'_\n"
        "• _'What is the total amount on this invoice?'_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="main_menu")]
        ])
    )
    await call.answer()


@router.message(ScanSession.waiting_ai_question, F.photo)
async def handle_ai_photo(message: Message, state: FSMContext, bot: Bot):
    """User sends a photo + optional caption question."""
    question = message.caption or "Please describe and summarise this document."

    processing_msg = await message.answer("🤖 Analysing your document… ⏳")

    # Download image
    file_info = await bot.get_file(message.photo[-1].file_id)
    buf       = io.BytesIO()
    await bot.download_file(file_info.file_path, buf)

    # Call GPT-4o vision
    answer = await utils.ask_ai_about_image(buf.getvalue(), question)

    await processing_msg.delete()
    await message.answer(
        f"🤖 **AI Response:**\n\n{answer}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Ask Another",  callback_data="ai_start")],
            [InlineKeyboardButton(text="🏠 Main Menu",    callback_data="main_menu")],
        ])
    )
    await state.clear()


# ─────────────────────────────────────────────────────────────────────────────
#  ADMIN PANEL
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Unauthorized.")
        return
    await message.answer(
        "🛠 **Admin Panel**\n\nSelect an action:",
        parse_mode="Markdown",
        reply_markup=admin_panel_kb()
    )


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Unauthorized.", show_alert=True)
        return
    total   = await db.get_user_count()
    premium = await db.get_premium_count()
    free    = total - premium
    await call.message.edit_text(
        f"📊 **Bot Statistics**\n\n"
        f"👥 Total users:   **{total}**\n"
        f"⭐ Premium users: **{premium}**\n"
        f"🆓 Free users:    **{free}**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
        ])
    )
    await call.answer()


@router.callback_query(F.data == "admin_back")
async def cb_admin_back(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer()
        return
    await call.message.edit_text(
        "🛠 **Admin Panel**\n\nSelect an action:",
        parse_mode="Markdown",
        reply_markup=admin_panel_kb()
    )
    await call.answer()


# ── Set Card Number ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_set_card")
async def cb_admin_set_card(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Unauthorized.", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_card_number)
    current = await db.get_setting("card_number", "Not set")
    await call.message.edit_text(
        f"💳 **Update Payment Card Number**\n\n"
        f"Current value: `{current}`\n\n"
        f"Reply with the new card number:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back")]
        ])
    )
    await call.answer()


@router.message(AdminStates.waiting_card_number)
async def handle_card_number(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    new_card = message.text.strip()
    await db.set_setting("card_number", new_card)
    await state.clear()
    await message.answer(
        f"✅ Card number updated to:\n`{new_card}`",
        parse_mode="Markdown",
        reply_markup=admin_panel_kb()
    )


# ── Broadcast ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Unauthorized.", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_broadcast_msg)
    await call.message.edit_text(
        "📢 **Broadcast Message**\n\n"
        "Type the message you want to send to ALL users.\n"
        "Supports Markdown formatting.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back")]
        ])
    )
    await call.answer()


@router.message(AdminStates.waiting_broadcast_msg)
async def handle_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return

    broadcast_text = message.text
    await state.clear()

    user_ids    = await db.get_all_user_ids()
    sent        = 0
    failed      = 0
    status_msg  = await message.answer(f"📤 Sending to {len(user_ids)} users… please wait.")

    for uid in user_ids:
        try:
            await bot.send_message(uid, broadcast_text, parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Respect Telegram rate limits (20 msg/s)

    await status_msg.edit_text(
        f"✅ **Broadcast complete!**\n\n"
        f"📨 Sent:   {sent}\n"
        f"❌ Failed: {failed}",
        parse_mode="Markdown",
        reply_markup=admin_panel_kb()
    )


# ─────────────────────────────────────────────────────────────────────────────
#  FALLBACK — handle unexpected messages
# ─────────────────────────────────────────────────────────────────────────────

@router.message()
async def fallback(message: Message, state: FSMContext):
    await register_user(message)
    current_state = await state.get_state()

    if current_state == ScanSession.collecting_images.state:
        # User sent something other than a photo while in scan mode
        await message.answer(
            "📸 Please send a **photo** to add it to your scan, "
            "or tap **Generate PDF** to finish.",
            parse_mode="Markdown",
            reply_markup=ready_to_process_kb()
        )
    else:
        premium = await db.is_premium(message.from_user.id)
        await message.answer(
            "👋 Use the menu below to get started!",
            reply_markup=main_menu_kb(premium)
        )
