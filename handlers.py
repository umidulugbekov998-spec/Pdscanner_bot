# handlers.py — To'liq kengaytirilgan bot handlerlari

import io
import os
import random
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
from config import ADMIN_ID, BOT_USERNAME, KANAL_USERNAME, KANAL_LINK

logger = logging.getLogger(__name__)
router = Router()


# ═══════════════════════════════════════════════════════════════
#  FSM HOLATLARI
# ═══════════════════════════════════════════════════════════════

class Scan(StatesGroup):
    rejim   = State()
    filtr   = State()
    rasm    = State()
    ai      = State()

class Tulov(StatesGroup):
    chek = State()

class Admin(StatesGroup):
    karta      = State()
    broadcast  = State()
    premium_id = State()
    block_id   = State()
    unblock_id = State()
    kanal      = State()

class Yordam(StatesGroup):
    xabar = State()

class Shrift(StatesGroup):
    matn = State()

class Oyinlar(StatesGroup):
    viktorina = State()
    son_taxmin = State()


# ═══════════════════════════════════════════════════════════════
#  KLAVIATURALAR
# ═══════════════════════════════════════════════════════════════

def asosiy_menu(premium=False):
    tarif = "⭐ Premium faol ✓" if premium else "💎 Premium olish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 Skanerlash",        callback_data="scan_start"),
            InlineKeyboardButton(text="🤖 AI Yordamchi",      callback_data="ai_start"),
        ],
        [
            InlineKeyboardButton(text="🔤 Matn & Shriftlar",  callback_data="shrift_menu"),
            InlineKeyboardButton(text="🎮 O'yinlar",          callback_data="oyinlar_menu"),
        ],
        [
            InlineKeyboardButton(text=tarif,                   callback_data="premium_info"),
            InlineKeyboardButton(text="📞 Yordam",             callback_data="yordam_menu"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Haqida",            callback_data="haqida"),
        ],
    ])


def scan_rejim_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 A4 Hujjat",   callback_data="mode_a4"),
            InlineKeyboardButton(text="🛂 Pasport",     callback_data="mode_passport"),
        ],
        [
            InlineKeyboardButton(text="🪪 ID Karta",    callback_data="mode_id_card"),
            InlineKeyboardButton(text="🖼 Rasm",         callback_data="mode_photo"),
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")],
    ])


def scan_filtr_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✨ Sehrli Rang",  callback_data="filter_magic_color"),
            InlineKeyboardButton(text="⚫ Qora-Oq",      callback_data="filter_bw"),
        ],
        [
            InlineKeyboardButton(text="🎨 Filtrsiz",     callback_data="filter_none"),
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="scan_start")],
    ])


def pdf_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ PDF yaratish",     callback_data="generate_pdf")],
        [InlineKeyboardButton(text="📦 Siqilgan PDF",    callback_data="generate_pdf_compressed")],
        [InlineKeyboardButton(text="🗑 Tozalab qaytish", callback_data="clear_session")],
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Statistika",        callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 A'zolar ro'yxati",  callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton(text="⭐ Premium berish",    callback_data="admin_give_premium"),
            InlineKeyboardButton(text="❌ Premium olish",     callback_data="admin_remove_premium"),
        ],
        [
            InlineKeyboardButton(text="🚫 Bloklash",          callback_data="admin_block"),
            InlineKeyboardButton(text="✅ Blokdan chiqarish", callback_data="admin_unblock"),
        ],
        [
            InlineKeyboardButton(text="💳 Karta yangilash",   callback_data="admin_set_card"),
            InlineKeyboardButton(text="📢 Xabar yuborish",    callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="📺 Kanal ulash",       callback_data="admin_set_kanal"),
        ],
    ])


def tulov_kb(request_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash",  callback_data=f"pay_approve:{request_id}"),
            InlineKeyboardButton(text="❌ Rad etish",   callback_data=f"pay_decline:{request_id}"),
        ]
    ])


def yordam_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Adminga yozish",    callback_data="yozish_admin")],
        [InlineKeyboardButton(text="💎 Premium olish",     callback_data="premium_info")],
        [InlineKeyboardButton(text="❓ Ko'p so'raladigan", callback_data="faq")],
        [InlineKeyboardButton(text="🔙 Orqaga",            callback_data="main_menu")],
    ])


def shrift_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗕𝗼𝗹𝗱 Qalin",          callback_data="shrift_bold")],
        [InlineKeyboardButton(text="𝘐𝘵𝘢𝘭𝘪𝘤 Qiya",          callback_data="shrift_italic")],
        [InlineKeyboardButton(text="𝕄𝕒𝕘𝕚𝕔 Sehrli",         callback_data="shrift_magic")],
        [InlineKeyboardButton(text="ꜱᴍᴀʟʟ Kichik",         callback_data="shrift_small")],
        [InlineKeyboardButton(text="S̲t̲r̲i̲k̲e̲ Chiziqli",      callback_data="shrift_strike")],
        [InlineKeyboardButton(text="🔙 Orqaga",             callback_data="main_menu")],
    ])


def oyinlar_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Viktorina",          callback_data="oyun_viktorina")],
        [InlineKeyboardButton(text="🎲 Son taxmin qilish",  callback_data="oyun_son")],
        [InlineKeyboardButton(text="🎱 Magic Ball",         callback_data="oyun_magic_ball")],
        [InlineKeyboardButton(text="🔙 Orqaga",             callback_data="main_menu")],
    ])


# ═══════════════════════════════════════════════════════════════
#  KANAL TEKSHIRISH
# ═══════════════════════════════════════════════════════════════

async def kanal_tekshir(user_id, bot: Bot):
    """Foydalanuvchi kanalga a'zo bo'lganini tekshiradi."""
    kanal = await db.get_setting("kanal_username", "")
    if not kanal:
        return True  # Kanal sozlanmagan — ruxsat beriladi
    try:
        member = await bot.get_chat_member(f"@{kanal}", user_id)
        return member.status not in ["left", "kicked", "banned"]
    except Exception:
        return True


def kanal_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga qo'shilish", url=f"https://t.me/{KANAL_USERNAME or 'dunyobot'}")],
        [InlineKeyboardButton(text="✅ Obuna bo'ldim",       callback_data="obuna_tekshir")],
    ])


# ═══════════════════════════════════════════════════════════════
#  YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════

async def royxatdan_otkazish(message: Message):
    u = message.from_user
    await db.add_or_update_user(u.id, u.username, u.full_name)


async def bloklangan_tekshir(message: Message):
    if await db.is_blocked(message.from_user.id):
        await message.answer("🚫 Siz botdan bloklangansiz. Admin bilan bog'laning.")
        return True
    return False


# ═══════════════════════════════════════════════════════════════
#  /START
# ═══════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await royxatdan_otkazish(message)
    if await bloklangan_tekshir(message): return
    await state.clear()

    # Kanal tekshirish
    if not await kanal_tekshir(message.from_user.id, bot):
        kanal = await db.get_setting("kanal_username", "")
        kanal_link = await db.get_setting("kanal_link", f"https://t.me/{kanal}")
        await message.answer(
            "📢 **Botdan foydalanish uchun kanalga a'zo bo'ling!**\n\n"
            f"👇 Quyidagi tugmani bosib kanalga qo'shiling:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga qo'shilish", url=kanal_link)],
                [InlineKeyboardButton(text="✅ A'bo bo'ldim", callback_data="obuna_tekshir")],
            ])
        )
        return

    u = message.from_user
    premium = await db.is_premium(u.id)
    tarif = "⭐ Premium" if premium else "🆓 Bepul"

    await message.answer(
        f"👋 Xush kelibsiz, **{u.first_name}**!\n\n"
        f"🤖 Men — **AI Hujjat Skaneri Boti**\n"
        f"📌 Tarifingiz: {tarif}\n\n"
        f"Quyidagi menyudan kerakli bo'limni tanlang 👇",
        parse_mode="Markdown",
        reply_markup=asosiy_menu(premium)
    )


@router.callback_query(F.data == "obuna_tekshir")
async def cb_obuna_tekshir(call: CallbackQuery, bot: Bot):
    if await kanal_tekshir(call.from_user.id, bot):
        premium = await db.is_premium(call.from_user.id)
        await call.message.edit_text(
            "✅ Rahmat! Kanalga a'zo bo'ldingiz.\n\n"
            "Endi botdan to'liq foydalanishingiz mumkin! 🎉",
            reply_markup=asosiy_menu(premium)
        )
    else:
        await call.answer("❌ Siz hali kanalga a'zo bo'lmagansiz!", show_alert=True)


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    premium = await db.is_premium(call.from_user.id)
    await call.message.edit_text(
        "🏠 **Asosiy Menyu**\n\nKerakli bo'limni tanlang:",
        parse_mode="Markdown",
        reply_markup=asosiy_menu(premium)
    )
    await call.answer()


# ═══════════════════════════════════════════════════════════════
#  HAQIDA
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "haqida")
async def cb_haqida(call: CallbackQuery):
    jami = await db.get_user_count()
    await call.message.edit_text(
        f"🤖 **AI Hujjat Skaneri Boti**\n\n"
        f"📌 Versiya: 2.0\n"
        f"👥 Foydalanuvchilar: {jami} kishi\n\n"
        f"🔧 **Imkoniyatlar:**\n"
        f"• 📄 Hujjat skanerlash va PDF yaratish\n"
        f"• 🗜 PDF siqish\n"
        f"• 🤖 AI yordamchi (GPT-4o)\n"
        f"• 🔤 Matn va shrift o'zgartirish\n"
        f"• 🎮 O'yinlar\n"
        f"• ⭐ Premium tarif\n\n"
        f"📞 Admin: @{BOT_USERNAME}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
        ])
    )
    await call.answer()


# ═══════════════════════════════════════════════════════════════
#  YORDAM
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "yordam_menu")
async def cb_yordam(call: CallbackQuery):
    await call.message.edit_text(
        "📞 **Yordam Markazi**\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=yordam_kb()
    )
    await call.answer()


@router.callback_query(F.data == "faq")
async def cb_faq(call: CallbackQuery):
    await call.message.edit_text(
        "❓ **Ko'p So'raladigan Savollar**\n\n"
        "**❓ Bot qanday ishlaydi?**\n"
        "Rasm yuboring → filtr tanlang → PDF oling.\n\n"
        "**❓ Premium nima beradi?**\n"
        "Suv belgisi yo'q, yuqori sifat, tezkor ishlash.\n\n"
        "**❓ To'lov qanday amalga oshiriladi?**\n"
        "Premium → karta raqamiga to'lang → chek yuboring.\n\n"
        "**❓ Bot ishlamasa nima qilaman?**\n"
        "Adminga yozing, tez yordam beriladi.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Adminga yozish", callback_data="yozish_admin")],
            [InlineKeyboardButton(text="🔙 Orqaga",         callback_data="yordam_menu")],
        ])
    )
    await call.answer()


@router.callback_query(F.data == "yozish_admin")
async def cb_yozish_admin(call: CallbackQuery, state: FSMContext):
    await state.set_state(Yordam.xabar)
    await call.message.edit_text(
        "💬 **Adminga Xabar Yuborish**\n\n"
        "Xabaringizni yozing — admin imkon qadar tez javob beradi. 🙏\n\n"
        "_(Savolingiz, muammongiz yoki taklifingizni yozing)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="main_menu")]
        ])
    )
    await call.answer()


@router.message(Yordam.xabar)
async def yordam_xabar_qabul(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    u = message.from_user

    # Adminga yuborish
    await bot.send_message(
        ADMIN_ID,
        f"📩 **Yangi Yordam So'rovi**\n\n"
        f"👤 [{u.full_name}](tg://user?id={u.id})\n"
        f"🆔 ID: `{u.id}`\n"
        f"🔖 @{u.username or 'Yo\'q'}\n\n"
        f"💬 **Xabar:**\n{message.text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Javob berish", callback_data=f"reply_user:{u.id}")]
        ])
    )

    await message.answer(
        "✅ Xabaringiz adminga yuborildi!\n"
        "Tez orada javob olasiz. ⏳",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="main_menu")]
        ])
    )


@router.callback_query(F.data.startswith("reply_user:"))
async def cb_reply_user(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    user_id = int(call.data.split(":")[1])
    await state.update_data(reply_to=user_id)
    await state.set_state(Admin.broadcast)
    await call.message.answer(
        f"✏️ Foydalanuvchi `{user_id}` ga javob yozing:",
        parse_mode="Markdown"
    )
    await call.answer()


# ═══════════════════════════════════════════════════════════════
#  PREMIUM
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "premium_info")
async def cb_premium(call: CallbackQuery):
    u = call.from_user
    premium = await db.is_premium(u.id)

    if premium:
        await call.message.edit_text(
            "⭐ **Premium Tarifingiz Faol!**\n\n"
            "✅ Suv belgisisiz PDF\n"
            "✅ Yuqori sifatli skanerlash\n"
            "✅ Tezkor ishlov berish\n"
            "✅ Cheksiz skanerlash\n\n"
            "Premium tarifingizdan bahramand bo'ling! 🎉",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
            ])
        )
    else:
        karta = await db.get_setting("card_number", "Admin bilan bog'laning")
        narx  = await db.get_setting("premium_price", "10,000 so'm/oy")
        await call.message.edit_text(
            "💎 **Premium Tarif**\n\n"
            "✅ Suv belgisisiz PDF\n"
            "✅ Yuqori sifatli skanerlash\n"
            "✅ Tezkor ishlov berish\n"
            "✅ Cheksiz skanerlash\n"
            "✅ AI yordamchi\n\n"
            f"💰 **Narx:** {narx}\n"
            f"💳 **To'lov Kartasi:**\n`{karta}`\n\n"
            "To'lov qilgach, chek screenshotini yuboring 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Chek yuborish", callback_data="upload_receipt")],
                [InlineKeyboardButton(text="🔙 Orqaga",        callback_data="main_menu")],
            ])
        )
    await call.answer()


@router.callback_query(F.data == "upload_receipt")
async def cb_chek(call: CallbackQuery, state: FSMContext):
    await state.set_state(Tulov.chek)
    await call.message.edit_text(
        "📸 **To'lov Chekini Yuboring**\n\n"
        "To'lov screenshotini yuboring.\n"
        "Admin tekshirib, Premium tarifingizni faollashtiradi. ⏳",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="main_menu")]
        ])
    )
    await call.answer()


@router.message(Tulov.chek, F.photo)
async def chek_qabul(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    u = message.from_user
    req_id = await db.create_payment_request(u.id)

    yuborildi = await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=(
            f"💳 **Yangi Premium So'rovi** #{req_id}\n\n"
            f"👤 [{u.full_name}](tg://user?id={u.id})\n"
            f"🆔 ID: `{u.id}`\n"
            f"🔖 @{u.username or 'Yo\'q'}"
        ),
        parse_mode="Markdown",
        reply_markup=tulov_kb(req_id)
    )
    await db.set_payment_admin_message(req_id, yuborildi.message_id)

    await message.answer(
        "✅ **Chekingiz yuborildi!**\n\n"
        "Admin tekshirib, Premium tarifingizni faollashtiradi.\n"
        "Odatda 5-30 daqiqa ichida faollashtiriladi. ⏳",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="main_menu")]
        ])
    )


@router.callback_query(F.data.startswith("pay_approve:"))
async def cb_approve(call: CallbackQuery, bot: Bot):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Ruxsat yo'q!", show_alert=True); return

    req_id = int(call.data.split(":")[1])
    req = await db.get_payment_request(req_id)
    if not req:
        await call.answer("❌ Topilmadi!", show_alert=True); return

    await db.set_premium(req["user_id"], True)
    await db.update_payment_status(req_id, "approved")

    await bot.send_message(
        req["user_id"],
        "🎉 **Tabriklaymiz! Premium Faollashtirildi!**\n\n"
        "⭐ Endi siz Premium foydalanuvchisiz!\n\n"
        "✅ Suv belgisisiz PDF\n"
        "✅ Yuqori sifat\n"
        "✅ Tezkor ishlash\n\n"
        "Rahmat! 🙏",
        parse_mode="Markdown",
        reply_markup=asosiy_menu(True)
    )
    await call.message.edit_caption(
        call.message.caption + "\n\n✅ **TASDIQLANDI**", parse_mode="Markdown"
    )
    await call.answer("✅ Premium berildi!", show_alert=True)


@router.callback_query(F.data.startswith("pay_decline:"))
async def cb_decline(call: CallbackQuery, bot: Bot):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Ruxsat yo'q!", show_alert=True); return

    req_id = int(call.data.split(":")[1])
    req = await db.get_payment_request(req_id)
    if not req:
        await call.answer("❌ Topilmadi!", show_alert=True); return

    await db.update_payment_status(req_id, "declined")
    await bot.send_message(
        req["user_id"],
        "❌ **Chekingiz Tasdiqlanmadi**\n\n"
        "Sabab: To'lov tasdiqlanmadi yoki chek noto'g'ri.\n\n"
        "Qayta urinib ko'ring yoki admin bilan bog'laning. 📞",
        parse_mode="Markdown"
    )
    await call.message.edit_caption(
        call.message.caption + "\n\n❌ **RAD ETILDI**", parse_mode="Markdown"
    )
    await call.answer("❌ Rad etildi!", show_alert=True)


# ═══════════════════════════════════════════════════════════════
#  SKANERLASH
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "scan_start")
async def cb_scan(call: CallbackQuery, state: FSMContext):
    await state.set_state(Scan.rejim)
    await call.message.edit_text(
        "📄 **Skanerlash Rejimi**\n\nQanday hujjat skanerlayapsiz?",
        parse_mode="Markdown",
        reply_markup=scan_rejim_kb()
    )
    await call.answer()


@router.callback_query(F.data.startswith("mode_"))
async def cb_mode(call: CallbackQuery, state: FSMContext):
    rejim = call.data.replace("mode_", "")
    nomlar = {"a4": "📄 A4", "passport": "🛂 Pasport", "id_card": "🪪 ID Karta", "photo": "🖼 Rasm"}
    await state.update_data(mode=rejim, images=[])
    await state.set_state(Scan.filtr)
    await call.message.edit_text(
        f"✅ Rejim: **{nomlar.get(rejim, rejim)}**\n\n🎨 Filtrni tanlang:",
        parse_mode="Markdown",
        reply_markup=scan_filtr_kb()
    )
    await call.answer()


@router.callback_query(F.data.startswith("filter_"))
async def cb_filter(call: CallbackQuery, state: FSMContext):
    filtr = call.data.replace("filter_", "")
    nomlar = {"magic_color": "✨ Sehrli Rang", "bw": "⚫ Qora-Oq", "none": "🎨 Filtrsiz"}
    await state.update_data(filter_type=filtr)
    await state.set_state(Scan.rasm)
    await call.message.edit_text(
        f"✅ Filtr: **{nomlar.get(filtr, filtr)}**\n\n"
        f"📸 Rasmlarni yuboring.\n"
        f"Tugatgach **PDF yaratish** yoki **Siqilgan PDF** tugmasini bosing.",
        parse_mode="Markdown",
        reply_markup=pdf_kb()
    )
    await call.answer()


@router.message(Scan.rasm, F.photo)
async def rasm_qabul(message: Message, state: FSMContext):
    data = await state.get_data()
    rasmlar = data.get("images", [])
    rasmlar.append(message.photo[-1].file_id)
    await state.update_data(images=rasmlar)
    await message.answer(
        f"📸 **{len(rasmlar)}-sahifa** qabul qilindi.\n"
        f"Yana rasm yuboring yoki PDF yarating.",
        parse_mode="Markdown",
        reply_markup=pdf_kb()
    )


@router.callback_query(F.data.in_({"generate_pdf", "generate_pdf_compressed"}))
async def cb_pdf(call: CallbackQuery, state: FSMContext, bot: Bot):
    data     = await state.get_data()
    file_ids = data.get("images", [])
    rejim    = data.get("mode", "a4")
    filtr    = data.get("filter_type", "magic_color")
    siqish   = call.data == "generate_pdf_compressed"

    if not file_ids:
        await call.answer("⚠️ Hali rasm yuborilmadi!", show_alert=True); return

    u = call.from_user
    premium = await db.is_premium(u.id)
    suv_belgisi = not premium

    await call.message.edit_text(
        f"⚙️ **{len(file_ids)} ta sahifa** ishlanmoqda…\n"
        f"{'🗜 Siqilgan PDF yaratilmoqda...' if siqish else '📄 Oddiy PDF yaratilmoqda...'}\n"
        f"{'🆓 Suv belgisi qo\'shiladi.' if suv_belgisi else '⭐ Suv belgisi yo\'q.'}",
        parse_mode="Markdown"
    )

    ishlangan = []
    for fid in file_ids:
        fi  = await bot.get_file(fid)
        buf = io.BytesIO()
        await bot.download_file(fi.file_path, buf)

        img = utils.process_image(
            img_bytes   = buf.getvalue(),
            mode        = rejim,
            filter_type = filtr,
            apply_crop  = True,
            watermark   = suv_belgisi,
            high_quality = premium,
            compress    = siqish,
        )
        ishlangan.append(img)

    pdf = utils.images_to_pdf(ishlangan)
    await db.increment_scan(u.id)

    fayl_nomi = "skan_siqilgan.pdf" if siqish else "skan.pdf"
    hajm_kb   = len(pdf) // 1024

    await bot.send_document(
        u.id,
        BufferedInputFile(pdf, filename=fayl_nomi),
        caption=(
            f"{'🗜' if siqish else '📄'} **PDF Tayyor!**\n\n"
            f"📑 Sahifalar: {len(ishlangan)}\n"
            f"📦 Hajm: {hajm_kb} KB\n"
            f"{'🆓 Suv belgisi qo\'shildi.' if suv_belgisi else '⭐ Premium: suv belgisi yo\'q!'}"
        ),
        parse_mode="Markdown"
    )

    await state.clear()
    await bot.send_message(u.id, "✅ Tayyor! Yana nima qilmoqchisiz?",
                           reply_markup=asosiy_menu(premium))


@router.callback_query(F.data == "clear_session")
async def cb_clear(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🗑 Tozalandi. Asosiy menyudan boshlang.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="main_menu")]
        ])
    )


# ═══════════════════════════════════════════════════════════════
#  AI YORDAMCHI
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ai_start")
async def cb_ai(call: CallbackQuery, state: FSMContext):
    await state.set_state(Scan.ai)
    await call.message.edit_text(
        "🤖 **AI Hujjat Yordamchisi**\n\n"
        "Hujjat rasmini yuboring va savolingizni yozing.\n\n"
        "**Misol:**\n"
        "• _Bu hujjat nima haqida?_\n"
        "• _Matnni tarjima qil_\n"
        "• _Umumiy summani ayt_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="main_menu")]
        ])
    )
    await call.answer()


@router.message(Scan.ai, F.photo)
async def ai_rasm(message: Message, state: FSMContext, bot: Bot):
    savol = message.caption or "Bu hujjatni tahlil qilib, qisqacha mazmunini ayt."
    jarayon = await message.answer("🤖 Tahlil qilinmoqda… ⏳")
    fi  = await bot.get_file(message.photo[-1].file_id)
    buf = io.BytesIO()
    await bot.download_file(fi.file_path, buf)
    javob = await utils.ask_ai_about_image(buf.getvalue(), savol)
    await jarayon.delete()
    await message.answer(
        f"🤖 **AI Javobi:**\n\n{javob}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yana so'rash", callback_data="ai_start")],
            [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="main_menu")],
        ])
    )
    await state.clear()


# ═══════════════════════════════════════════════════════════════
#  MATN & SHRIFTLAR
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "shrift_menu")
async def cb_shrift_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(Shrift.matn)
    await call.message.edit_text(
        "🔤 **Matn & Shriftlar**\n\n"
        "O'zgartirmoqchi bo'lgan **matnni** yuboring,\n"
        "keyin shrift turini tanlang 👇",
        parse_mode="Markdown",
        reply_markup=shrift_kb()
    )
    await call.answer()


def matn_ozgartir(matn, tur):
    """Matnni turli shriftlarga o'zgartiradi."""
    bold_map   = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
                               "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵")
    italic_map = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                               "𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻")
    magic_map  = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                               "𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫")
    small_map  = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                               "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘQʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘQʀꜱᴛᴜᴠᴡxʏᴢ")

    if tur == "bold":   return matn.translate(bold_map)
    if tur == "italic": return matn.translate(italic_map)
    if tur == "magic":  return matn.translate(magic_map)
    if tur == "small":  return matn.translate(small_map)
    if tur == "strike": return "".join(c + "̶" for c in matn)
    return matn


@router.message(Shrift.matn)
async def shrift_matn_qabul(message: Message, state: FSMContext):
    await state.update_data(matn=message.text)
    await message.answer(
        f"✅ Matn qabul qilindi:\n`{message.text}`\n\nShrift turini tanlang 👇",
        parse_mode="Markdown",
        reply_markup=shrift_kb()
    )


@router.callback_query(F.data.startswith("shrift_"))
async def cb_shrift(call: CallbackQuery, state: FSMContext):
    tur = call.data.replace("shrift_", "")
    if tur == "menu":
        await cb_shrift_menu(call, state)
        return

    data = await state.get_data()
    matn = data.get("matn", "")

    if not matn:
        await call.answer("⚠️ Avval matn yuboring!", show_alert=True)
        return

    natija = matn_ozgartir(matn, tur)
    await call.message.answer(
        f"🔤 **Natija:**\n\n{natija}\n\n"
        f"_(Nusxa oling va ishlating!)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Boshqa shrift", callback_data="shrift_menu")],
            [InlineKeyboardButton(text="🏠 Asosiy Menyu",  callback_data="main_menu")],
        ])
    )
    await call.answer()


# ═══════════════════════════════════════════════════════════════
#  O'YINLAR
# ═══════════════════════════════════════════════════════════════

VIKTORINA_SAVOLLAR = [
    {"savol": "🌍 O'zbekistonning poytaxti qaysi shahar?",
     "javoblar": ["Samarqand", "Toshkent", "Buxoro", "Namangan"], "togri": 1},
    {"savol": "🔢 Nechta tomoni bor uchburchakning?",
     "javoblar": ["2", "3", "4", "5"], "togri": 1},
    {"savol": "🌊 Dunyo bo'yicha eng katta okean?",
     "javoblar": ["Atlantik", "Hind", "Tinch", "Arktika"], "togri": 2},
    {"savol": "🐘 Quruqlikdagi eng katta hayvon?",
     "javoblar": ["Fil", "Begemot", "Karkidon", "Jiraffa"], "togri": 0},
    {"savol": "☀️ Quyosh sistemasidagi eng katta sayyora?",
     "javoblar": ["Saturn", "Yer", "Yupiter", "Mars"], "togri": 2},
    {"savol": "💧 Suvning kimyoviy formulasi?",
     "javoblar": ["CO2", "H2O", "O2", "NaCl"], "togri": 1},
    {"savol": "🎵 Notalar nechtadan iborat?",
     "javoblar": ["5", "6", "7", "8"], "togri": 2},
    {"savol": "📚 'Alpomish' qaysi xalqning dostoni?",
     "javoblar": ["Qozoq", "O'zbek", "Tojik", "Qirg'iz"], "togri": 1},
]


@router.callback_query(F.data == "oyinlar_menu")
async def cb_oyinlar(call: CallbackQuery):
    await call.message.edit_text(
        "🎮 **O'yinlar**\n\nQaysi o'yinni o'ynamoqchisiz?",
        parse_mode="Markdown",
        reply_markup=oyinlar_kb()
    )
    await call.answer()


@router.callback_query(F.data == "oyun_viktorina")
async def cb_viktorina(call: CallbackQuery, state: FSMContext):
    savol_data = random.choice(VIKTORINA_SAVOLLAR)
    await state.set_state(Oyinlar.viktorina)
    await state.update_data(
        togri_javob=savol_data["togri"],
        savol=savol_data["savol"]
    )

    tugmalar = []
    for i, j in enumerate(savol_data["javoblar"]):
        tugmalar.append([InlineKeyboardButton(text=j, callback_data=f"vikt_javob:{i}")])
    tugmalar.append([InlineKeyboardButton(text="🏠 Chiqish", callback_data="main_menu")])

    await call.message.edit_text(
        f"🧠 **Viktorina**\n\n{savol_data['savol']}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=tugmalar)
    )
    await call.answer()


@router.callback_query(F.data.startswith("vikt_javob:"))
async def cb_vikt_javob(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tanlangan = int(call.data.split(":")[1])
    togri = data.get("togri_javob", -1)

    if tanlangan == togri:
        matn = "✅ **To'g'ri javob!** Barakalla! 🎉"
    else:
        matn = f"❌ **Noto'g'ri!** To'g'ri javob: {data.get('savol', '')}"

    await call.message.edit_text(
        matn,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yana o'ynash", callback_data="oyun_viktorina")],
            [InlineKeyboardButton(text="🎮 O'yinlar",     callback_data="oyinlar_menu")],
            [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="main_menu")],
        ])
    )
    await state.clear()
    await call.answer()


@router.callback_query(F.data == "oyun_son")
async def cb_son_oyun(call: CallbackQuery, state: FSMContext):
    son = random.randint(1, 10)
    await state.set_state(Oyinlar.son_taxmin)
    await state.update_data(maxfiy_son=son, urinish=0)
    await call.message.edit_text(
        "🎲 **Son Taxmin Qilish**\n\n"
        "Men 1 dan 10 gacha son o'yladim.\n"
        "Taxminingizni yozing! 3 ta urinish bor.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Chiqish", callback_data="oyinlar_menu")]
        ])
    )
    await call.answer()


@router.message(Oyinlar.son_taxmin)
async def son_taxmin(message: Message, state: FSMContext):
    data = await state.get_data()
    maxfiy = data.get("maxfiy_son", 5)
    urinish = data.get("urinish", 0) + 1
    await state.update_data(urinish=urinish)

    try:
        taxmin = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Iltimos, raqam yozing!")
        return

    if taxmin == maxfiy:
        await message.answer(
            f"🎉 **To'g'ri! {maxfiy} son edi!**\n"
            f"Siz {urinish} ta urinishda topdingiz!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Yana o'ynash", callback_data="oyun_son")],
                [InlineKeyboardButton(text="🎮 O'yinlar",     callback_data="oyinlar_menu")],
            ])
        )
        await state.clear()
    elif urinish >= 3:
        await message.answer(
            f"😔 **Urinishlar tugadi!**\nTo'g'ri javob: **{maxfiy}**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Qayta o'ynash", callback_data="oyun_son")],
                [InlineKeyboardButton(text="🎮 O'yinlar",      callback_data="oyinlar_menu")],
            ])
        )
        await state.clear()
    elif taxmin < maxfiy:
        await message.answer(f"⬆️ Kattaroq! {3 - urinish} ta urinish qoldi.")
    else:
        await message.answer(f"⬇️ Kichikroq! {3 - urinish} ta urinish qoldi.")


@router.callback_query(F.data == "oyun_magic_ball")
async def cb_magic_ball(call: CallbackQuery):
    javoblar = [
        "🟢 Ha, albatta!", "🟢 Shubhasiz!", "🟢 Bunga ishonch bilan ayta olaman — HA!",
        "🟡 Hozircha aytish qiyin...", "🟡 Qayta so'rang.", "🟡 Bunga ishonch yo'q.",
        "🔴 Yo'q.", "🔴 Umid qilmang.", "🔴 Bu yaxshi fikr emas.",
    ]
    await call.message.edit_text(
        f"🎱 **Magic Ball**\n\n"
        f"Savolingizni o'ylab, javobni o'qing:\n\n"
        f"**{random.choice(javoblar)}**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎱 Yana so'rash",  callback_data="oyun_magic_ball")],
            [InlineKeyboardButton(text="🎮 O'yinlar",      callback_data="oyinlar_menu")],
        ])
    )
    await call.answer()


# ═══════════════════════════════════════════════════════════════
#  ADMIN PANELI
# ═══════════════════════════════════════════════════════════════

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Ruxsat yo'q!"); return
    await message.answer(
        "🛠 **Admin Paneli**\n\nKerakli amalni tanlang:",
        parse_mode="Markdown",
        reply_markup=admin_kb()
    )


@router.callback_query(F.data == "admin_stats")
async def cb_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True); return
    jami    = await db.get_user_count()
    premium = await db.get_premium_count()
    bugun   = await db.get_active_today()
    await call.message.edit_text(
        f"📊 **Bot Statistikasi**\n\n"
        f"👥 Jami foydalanuvchilar: **{jami}**\n"
        f"⭐ Premium foydalanuvchilar: **{premium}**\n"
        f"🆓 Bepul foydalanuvchilar: **{jami - premium}**\n"
        f"📅 Bugun faol: **{bugun}**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]
        ])
    )
    await call.answer()


@router.callback_query(F.data == "admin_users")
async def cb_users(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True); return
    users = await db.get_all_users()
    matn = "👥 **So'nggi 10 ta foydalanuvchi:**\n\n"
    for u in users[:10]:
        tarif = "⭐" if u["is_premium"] else "🆓"
        blok  = "🚫" if u["is_blocked"] else ""
        matn += f"{tarif}{blok} [{u['full_name']}](tg://user?id={u['user_id']}) — `{u['user_id']}`\n"
    await call.message.edit_text(
        matn, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]
        ])
    )
    await call.answer()


@router.callback_query(F.data == "admin_give_premium")
async def cb_give_premium(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True); return
    await state.set_state(Admin.premium_id)
    await call.message.answer("👤 Premium bermoqchi bo'lgan foydalanuvchi **ID** sini yuboring:")
    await call.answer()


@router.message(Admin.premium_id)
async def admin_premium_ber(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID: return
    try:
        uid = int(message.text.strip())
        await db.set_premium(uid, True)
        await state.clear()
        await message.answer(f"✅ `{uid}` ga Premium berildi!", parse_mode="Markdown",
                             reply_markup=admin_kb())
        await bot.send_message(uid,
            "🎉 **Tabriklaymiz! Premium Faollashtirildi!**\n\n"
            "⭐ Endi siz Premium foydalanuvchisiz! 🚀",
            parse_mode="Markdown")
    except Exception:
        await message.answer("❌ Noto'g'ri ID. Qaytadan yuboring:")


@router.callback_query(F.data == "admin_remove_premium")
async def cb_remove_premium(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True); return
    await state.set_state(Admin.block_id)
    await state.update_data(action="remove_premium")
    await call.message.answer("👤 Premiumni olmoqchi bo'lgan foydalanuvchi **ID** sini yuboring:")
    await call.answer()


@router.callback_query(F.data == "admin_block")
async def cb_block(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True); return
    await state.set_state(Admin.block_id)
    await state.update_data(action="block")
    await call.message.answer("👤 Bloklash kerak bo'lgan foydalanuvchi **ID** sini yuboring:")
    await call.answer()


@router.callback_query(F.data == "admin_unblock")
async def cb_unblock(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True); return
    await state.set_state(Admin.unblock_id)
    await call.message.answer("👤 Blokdan chiqarish kerak bo'lgan foydalanuvchi **ID** sini yuboring:")
    await call.answer()


@router.message(Admin.block_id)
async def admin_block_action(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    action = data.get("action", "block")
    try:
        uid = int(message.text.strip())
        await state.clear()
        if action == "block":
            await db.block_user(uid, True)
            await message.answer(f"🚫 `{uid}` bloklandi!", parse_mode="Markdown", reply_markup=admin_kb())
        else:
            await db.set_premium(uid, False)
            await message.answer(f"❌ `{uid}` dan Premium olindi!", parse_mode="Markdown", reply_markup=admin_kb())
    except Exception:
        await message.answer("❌ Noto'g'ri ID!")


@router.message(Admin.unblock_id)
async def admin_unblock(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        uid = int(message.text.strip())
        await db.block_user(uid, False)
        await state.clear()
        await message.answer(f"✅ `{uid}` blokdan chiqarildi!", parse_mode="Markdown", reply_markup=admin_kb())
    except Exception:
        await message.answer("❌ Noto'g'ri ID!")


@router.callback_query(F.data == "admin_set_card")
async def cb_set_card(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True); return
    await state.set_state(Admin.karta)
    joriy = await db.get_setting("card_number", "Kiritilmagan")
    await call.message.answer(
        f"💳 Joriy karta: `{joriy}`\n\nYangi karta raqamini yuboring:",
        parse_mode="Markdown"
    )
    await call.answer()


@router.message(Admin.karta)
async def admin_karta(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await db.set_setting("card_number", message.text.strip())
    await state.clear()
    await message.answer(f"✅ Karta yangilandi: `{message.text.strip()}`",
                         parse_mode="Markdown", reply_markup=admin_kb())


@router.callback_query(F.data == "admin_set_kanal")
async def cb_set_kanal(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True); return
    await state.set_state(Admin.kanal)
    joriy = await db.get_setting("kanal_username", "Kiritilmagan")
    await call.message.answer(
        f"📺 Joriy kanal: `@{joriy}`\n\n"
        f"Yangi kanal username ni yuboring (@ belgisisiz):\n"
        f"Misol: `mening_kanalim`\n\n"
        f"O'chirish uchun `0` yuboring.",
        parse_mode="Markdown"
    )
    await call.answer()


@router.message(Admin.kanal)
async def admin_kanal(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    kanal = message.text.strip().replace("@", "")
    if kanal == "0":
        await db.set_setting("kanal_username", "")
        await db.set_setting("kanal_link", "")
        await message.answer("✅ Majburiy obuna o'chirildi.", reply_markup=admin_kb())
    else:
        await db.set_setting("kanal_username", kanal)
        await db.set_setting("kanal_link", f"https://t.me/{kanal}")
        await message.answer(
            f"✅ Kanal ulandi: @{kanal}\n"
            f"Endi foydalanuvchilar kanalga a'zo bo'lishi shart!",
            reply_markup=admin_kb()
        )
    await state.clear()


@router.callback_query(F.data == "admin_broadcast")
async def cb_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True); return
    await state.set_state(Admin.broadcast)
    await state.update_data(reply_to=None)
    await call.message.answer(
        "📢 **Hammaga Xabar Yuborish**\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni yozing:",
        parse_mode="Markdown"
    )
    await call.answer()


@router.message(Admin.broadcast)
async def admin_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    reply_to = data.get("reply_to")
    await state.clear()

    if reply_to:
        # Faqat bitta foydalanuvchiga javob
        try:
            await bot.send_message(reply_to, f"📩 **Admin javobi:**\n\n{message.text}",
                                   parse_mode="Markdown")
            await message.answer(f"✅ `{reply_to}` ga javob yuborildi!", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ Xato: {e}")
        return

    # Hammaga yuborish
    uids = await db.get_all_user_ids()
    yuborildi = xato = 0
    holat = await message.answer(f"📤 {len(uids)} ta foydalanuvchiga yuborilmoqda…")

    for uid in uids:
        try:
            await bot.send_message(uid, message.text, parse_mode="Markdown")
            yuborildi += 1
        except Exception:
            xato += 1
        await asyncio.sleep(0.05)

    await holat.edit_text(
        f"✅ **Yakunlandi!**\n\n"
        f"📨 Yuborildi: **{yuborildi}**\n"
        f"❌ Xato: **{xato}**",
        parse_mode="Markdown",
        reply_markup=admin_kb()
    )


@router.callback_query(F.data == "admin_back")
async def cb_admin_back(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text(
        "🛠 **Admin Paneli**", parse_mode="Markdown", reply_markup=admin_kb()
    )
    await call.answer()


# ═══════════════════════════════════════════════════════════════
#  NOMA'LUM XABARLAR
# ═══════════════════════════════════════════════════════════════

@router.message()
async def nomalum(message: Message, state: FSMContext):
    await royxatdan_otkazish(message)
    if await bloklangan_tekshir(message): return
    joriy = await state.get_state()

    if joriy == Scan.rasm.state:
        await message.answer(
            "📸 Rasm yuboring yoki PDF yarating.",
            reply_markup=pdf_kb()
        )
    elif joriy == Oyinlar.son_taxmin.state:
        await message.answer("🎲 Raqam yozing (1-10):")
    else:
        premium = await db.is_premium(message.from_user.id)
        await message.answer("👇 Menyudan tanlang:", reply_markup=asosiy_menu(premium))
