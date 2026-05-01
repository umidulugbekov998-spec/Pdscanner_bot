"""
handlers.py — Barcha aiogram 3.x handlerlar o'zbek tilida.
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
from config import ADMIN_ID, BOT_USERNAME

logger = logging.getLogger(__name__)
router = Router()


# ─────────────────────────────────────────────────────────────────────────────
#  FSM HOLATLARI
# ─────────────────────────────────────────────────────────────────────────────

class ScanSession(StatesGroup):
    rejim_tanlash      = State()
    filtr_tanlash      = State()
    rasm_qabul         = State()
    ai_savol_kutish    = State()


class AdminHolat(StatesGroup):
    xabar_kutish  = State()
    karta_kutish  = State()


class TulovHolat(StatesGroup):
    chek_kutish = State()


# ─────────────────────────────────────────────────────────────────────────────
#  KLAVIATURALAR
# ─────────────────────────────────────────────────────────────────────────────

def asosiy_menu(premium: bool = False) -> InlineKeyboardMarkup:
    tarif = "⭐ Premium faol" if premium else "💎 Premium olish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 Hujjat skanerlash", callback_data="scan_start"),
            InlineKeyboardButton(text="🤖 AI Yordamchi",      callback_data="ai_start"),
        ],
        [
            InlineKeyboardButton(text=tarif,                   callback_data="premium_info"),
            InlineKeyboardButton(text="📞 Admin bilan bog'lanish", callback_data="contact_admin"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Yordam",             callback_data="help"),
        ],
    ])


def rejim_klaviatura() -> InlineKeyboardMarkup:
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


def filtr_klaviatura() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✨ Sehrli Rang", callback_data="filter_magic_color"),
            InlineKeyboardButton(text="⚫ Qora-Oq",     callback_data="filter_bw"),
        ],
        [
            InlineKeyboardButton(text="🎨 Filtrsiz",    callback_data="filter_none"),
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="scan_start")],
    ])


def pdf_tayyor_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ PDF yaratish",      callback_data="generate_pdf")],
        [InlineKeyboardButton(text="🗑 Tozalab qaytish",   callback_data="clear_session")],
    ])


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Karta raqamini yangilash", callback_data="admin_set_card")],
        [InlineKeyboardButton(text="📢 Hammaga xabar yuborish",   callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Statistika",               callback_data="admin_stats")],
    ])


def tulov_tasdiqlash_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash",  callback_data=f"pay_approve:{request_id}"),
            InlineKeyboardButton(text="❌ Rad etish",   callback_data=f"pay_decline:{request_id}"),
        ]
    ])


# ─────────────────────────────────────────────────────────────────────────────
#  FOYDALANUVCHINI RO'YXATDAN O'TKAZISH
# ─────────────────────────────────────────────────────────────────────────────

async def foydalanuvchi_qoshish(message: Message):
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
    await foydalanuvchi_qoshish(message)
    await state.clear()

    user    = message.from_user
    premium = await db.is_premium(user.id)
    tarif   = "⭐ **Premium**" if premium else "🆓 **Bepul**"

    matn = (
        f"👋 Xush kelibsiz, **{user.first_name}**!\n\n"
        f"🤖 Men — **AI Hujjat Skaneri**. OpenCV va GPT-4o yordamida ishlayman.\n\n"
        f"📌 Sizning tarifingiz: {tarif}\n\n"
        f"Bugun nima qilmoqchisiz?"
    )
    await message.answer(matn, parse_mode="Markdown",
                         reply_markup=asosiy_menu(premium))


# ─────────────────────────────────────────────────────────────────────────────
#  ASOSIY MENYU
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def cb_asosiy_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    premium = await db.is_premium(call.from_user.id)
    await call.message.edit_text(
        "🏠 **Asosiy Menyu** — kerakli bo'limni tanlang:",
        parse_mode="Markdown",
        reply_markup=asosiy_menu(premium)
    )
    await call.answer()


@router.callback_query(F.data == "help")
async def cb_yordam(call: CallbackQuery):
    matn = (
        "ℹ️ **Botdan foydalanish yo'riqnomasi**\n\n"
        "1️⃣ **Hujjat skanerlash** tugmasini bosing.\n"
        "2️⃣ Rejimni tanlang (A4, Pasport, ID Karta, Rasm).\n"
        "3️⃣ Filtrni tanlang (Sehrli Rang yoki Qora-Oq).\n"
        "4️⃣ Bir yoki bir nechta rasm yuboring.\n"
        "5️⃣ **PDF yaratish** tugmasini bosing.\n\n"
        "🤖 **AI Yordamchi** — skaner qilingan rasm haqida savol bering yoki tarjima qilish uchun foydalaning.\n\n"
        "💎 **Premium** afzalliklari:\n"
        "  • PDF da suv belgisi yo'q\n"
        "  • Tezkor ishlov berish\n"
        "  • Yuqori sifatli chiqish\n"
        "  • Cheksiz skanerlash\n\n"
        "📞 Yordam uchun **Admin bilan bog'lanish** tugmasini bosing."
    )
    await call.message.edit_text(matn, parse_mode="Markdown",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                     [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
                                 ]))
    await call.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  ADMIN BILAN BOG'LANISH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "contact_admin")
async def cb_admin_boglanish(call: CallbackQuery):
    await call.message.edit_text(
        f"📞 **Admin bilan bog'lanish**\n\n"
        f"Yordam, to'lov yoki taklif uchun:\n"
        f"👤 [Admin](tg://user?id={ADMIN_ID})\n\n"
        f"Xabar yuboring — admin imkon qadar tez javob beradi. 🙏",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
        ])
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  PREMIUM
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "premium_info")
async def cb_premium(call: CallbackQuery, state: FSMContext):
    user    = call.from_user
    premium = await db.is_premium(user.id)

    if premium:
        await call.message.edit_text(
            "⭐ Siz allaqachon **Premium** foydalanuvchisiz!\n\n"
            "Suv belgisisiz PDF va yuqori sifatli skanerlashdan bahramand bo'ling! 🎉",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
            ])
        )
    else:
        karta = await db.get_setting("card_number", "Hali o'rnatilmagan — admin bilan bog'laning.")
        await call.message.edit_text(
            "💎 **Premium Tarifga O'tish**\n\n"
            "✅ PDF da suv belgisi yo'q\n"
            "✅ Tezkor ishlov berish\n"
            "✅ Maksimal sifat\n"
            "✅ Cheksiz skanerlash\n\n"
            f"💳 **To'lov Kartasi:** `{karta}`\n\n"
            "To'lov qilgandan so'ng, quyidagi tugmani bosing va to'lov chekining "
            "screenshotini yuboring. Admin tekshirib, premiumingizni faollashtiradi.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Chek yuborish", callback_data="upload_receipt")],
                [InlineKeyboardButton(text="🔙 Orqaga",        callback_data="main_menu")],
            ])
        )
    await call.answer()


@router.callback_query(F.data == "upload_receipt")
async def cb_chek_yuklash(call: CallbackQuery, state: FSMContext):
    await state.set_state(TulovHolat.chek_kutish)
    await call.message.edit_text(
        "📸 **To'lov chekini yuboring**\n\n"
        "To'lov screenshotini shu yerga yuboring.\n"
        "Admin tekshirib, Premium tarifingizni faollashtiradi. ⏳",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="main_menu")]
        ])
    )
    await call.answer()


@router.message(TulovHolat.chek_kutish, F.photo)
async def chek_qabul(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user       = message.from_user
    request_id = await db.create_payment_request(user.id)

    izoh = (
        f"💳 **Yangi Premium So'rovi**\n\n"
        f"👤 Foydalanuvchi: [{user.full_name}](tg://user?id={user.id})\n"
        f"🆔 ID: `{user.id}`\n"
        f"🔖 Username: @{user.username or 'Yo\'q'}\n"
        f"📋 So'rov ID: `{request_id}`"
    )
    yuborildi = await bot.send_photo(
        chat_id      = ADMIN_ID,
        photo        = message.photo[-1].file_id,
        caption      = izoh,
        parse_mode   = "Markdown",
        reply_markup = tulov_tasdiqlash_kb(request_id)
    )
    await db.set_payment_admin_message(request_id, yuborildi.message_id)

    await message.answer(
        "✅ Chekingiz adminga yuborildi!\n"
        "Premium faollashtirilgach sizga xabar beriladi. ⏳",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="main_menu")]
        ])
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ADMIN — TASDIQLASH / RAD ETISH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay_approve:"))
async def cb_tasdiqlash(call: CallbackQuery, bot: Bot):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    request_id = int(call.data.split(":")[1])
    req        = await db.get_payment_request(request_id)
    if not req:
        await call.answer("❌ So'rov topilmadi.", show_alert=True)
        return

    await db.set_premium(req["user_id"], True)
    await db.update_payment_status(request_id, "approved")

    await bot.send_message(
        req["user_id"],
        "🎉 **Tabriklaymiz!** To'lovingiz tasdiqlandi.\n\n"
        "⭐ Siz endi **Premium** foydalanuvchisiz!\n"
        "Suv belgisisiz PDF va tezkor skanerlashdan foydalaning! 🚀",
        parse_mode="Markdown"
    )
    await call.message.edit_caption(
        call.message.caption + "\n\n✅ **TASDIQLANDI**",
        parse_mode="Markdown"
    )
    await call.answer("✅ Foydalanuvchi Premium ga o'tkazildi!", show_alert=True)


@router.callback_query(F.data.startswith("pay_decline:"))
async def cb_rad_etish(call: CallbackQuery, bot: Bot):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    request_id = int(call.data.split(":")[1])
    req        = await db.get_payment_request(request_id)
    if not req:
        await call.answer("❌ So'rov topilmadi.", show_alert=True)
        return

    await db.update_payment_status(request_id, "declined")

    await bot.send_message(
        req["user_id"],
        "❌ **To'lov cheki tasdiqlanmadi.**\n\n"
        "Chekni qayta tekshirib yuboring yoki admin bilan bog'laning.",
        parse_mode="Markdown"
    )
    await call.message.edit_caption(
        call.message.caption + "\n\n❌ **RAD ETILDI**",
        parse_mode="Markdown"
    )
    await call.answer("❌ So'rov rad etildi.", show_alert=True)


# ─────────────────────────────────────────────────────────────────────────────
#  SKANERLASH — REJIM TANLASH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "scan_start")
async def cb_scan_boshlash(call: CallbackQuery, state: FSMContext):
    await state.set_state(ScanSession.rejim_tanlash)
    await call.message.edit_text(
        "📂 **Skanerlash Rejimini Tanlang**\n\n"
        "Qanday hujjat skanerlayapsiz?",
        parse_mode="Markdown",
        reply_markup=rejim_klaviatura()
    )
    await call.answer()


@router.callback_query(F.data.startswith("mode_"))
async def cb_rejim_tanlandi(call: CallbackQuery, state: FSMContext):
    rejim = call.data.replace("mode_", "")
    rejim_nomlari = {
        "a4":       "📄 A4 Hujjat",
        "passport": "🛂 Pasport",
        "id_card":  "🪪 ID Karta",
        "photo":    "🖼 Rasm",
    }
    await state.update_data(mode=rejim, images=[])
    await state.set_state(ScanSession.filtr_tanlash)

    await call.message.edit_text(
        f"✅ Rejim: **{rejim_nomlari.get(rejim, rejim)}**\n\n"
        f"🎨 Endi filtrni tanlang:",
        parse_mode="Markdown",
        reply_markup=filtr_klaviatura()
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  SKANERLASH — FILTR TANLASH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("filter_"))
async def cb_filtr_tanlandi(call: CallbackQuery, state: FSMContext):
    filtr = call.data.replace("filter_", "")
    filtr_nomlari = {
        "magic_color": "✨ Sehrli Rang",
        "bw":          "⚫ Qora-Oq",
        "none":        "🎨 Filtrsiz",
    }
    await state.update_data(filter_type=filtr)
    await state.set_state(ScanSession.rasm_qabul)

    await call.message.edit_text(
        f"✅ Filtr: **{filtr_nomlari.get(filtr, filtr)}**\n\n"
        f"📸 Endi rasmlarni yuboring.\n"
        f"Tugatgach **PDF yaratish** tugmasini bosing.",
        parse_mode="Markdown",
        reply_markup=pdf_tayyor_kb()
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  SKANERLASH — RASMLARNI QABUL QILISH
# ─────────────────────────────────────────────────────────────────────────────

@router.message(ScanSession.rasm_qabul, F.photo)
async def rasm_qabul(message: Message, state: FSMContext, bot: Bot):
    data   = await state.get_data()
    rasmlar = data.get("images", [])
    rasmlar.append(message.photo[-1].file_id)
    await state.update_data(images=rasmlar)

    soni = len(rasmlar)
    await message.answer(
        f"📸 **{soni}-sahifa** qabul qilindi.\n"
        f"Yana rasm yuboring yoki **PDF yaratish** tugmasini bosing.",
        parse_mode="Markdown",
        reply_markup=pdf_tayyor_kb()
    )


# ─────────────────────────────────────────────────────────────────────────────
#  SKANERLASH — PDF YARATISH
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "generate_pdf")
async def cb_pdf_yaratish(call: CallbackQuery, state: FSMContext, bot: Bot):
    data     = await state.get_data()
    file_ids = data.get("images", [])
    rejim    = data.get("mode", "a4")
    filtr    = data.get("filter_type", "magic_color")

    if not file_ids:
        await call.answer("⚠️ Hali rasm yuborilmadi! Kamida bitta rasm yuboring.", show_alert=True)
        return

    user    = call.from_user
    premium = await db.is_premium(user.id)
    suv_belgisi = not premium

    await call.message.edit_text(
        f"⚙️ **{len(file_ids)} ta sahifa** ishlanmoqda…\n"
        f"{'🆓 Suv belgisi qo\'shiladi (Bepul tarif).' if suv_belgisi else '⭐ Premium: suv belgisi yo\'q.'}",
        parse_mode="Markdown"
    )

    ishlangan_rasmlar = []
    for fid in file_ids:
        fayl_info = await bot.get_file(fid)
        buf       = io.BytesIO()
        await bot.download_file(fayl_info.file_path, buf)

        ishlangan = utils.process_image(
            img_bytes   = buf.getvalue(),
            mode        = rejim,
            filter_type = filtr,
            apply_crop  = True,
            watermark   = suv_belgisi,
        )
        ishlangan_rasmlar.append(ishlangan)

    pdf_bayt = utils.images_to_pdf(ishlangan_rasmlar)

    await bot.send_document(
        chat_id  = user.id,
        document = BufferedInputFile(pdf_bayt, filename="skan.pdf"),
        caption  = (
            f"📄 **PDF tayyor!**\n"
            f"📑 Sahifalar soni: {len(ishlangan_rasmlar)}\n"
            f"{'🆓 Suv belgisi qo\'shildi. Premium olish uchun /start bosing!' if suv_belgisi else '⭐ Premium: suv belgisi yo\'q!'}"
        ),
    )

    await state.clear()
    await bot.send_message(
        user.id,
        "✅ Tayyor! Yana nima qilmoqchisiz?",
        reply_markup=asosiy_menu(premium)
    )


@router.callback_query(F.data == "clear_session")
async def cb_tozalash(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🗑 Sessiya tozalandi.\n\nAsosiy menyudan yangi skanerlashni boshlang.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="main_menu")]
        ])
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  AI YORDAMCHI
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ai_start")
async def cb_ai_boshlash(call: CallbackQuery, state: FSMContext):
    await state.set_state(ScanSession.ai_savol_kutish)
    await call.message.edit_text(
        "🤖 **AI Hujjat Yordamchisi**\n\n"
        "Hujjat **rasmini** yuboring va savolingizni yozing.\n\n"
        "Misol uchun:\n"
        "• _'Bu hujjat nima haqida?'_\n"
        "• _'Matnni o'zbek tiliga tarjima qil'_\n"
        "• _'Umumiy summani ayt'_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="main_menu")]
        ])
    )
    await call.answer()


@router.message(ScanSession.ai_savol_kutish, F.photo)
async def ai_rasm_qabul(message: Message, state: FSMContext, bot: Bot):
    savol = message.caption or "Iltimos, bu hujjatni tahlil qiling va qisqacha mazmunini aytib bering."

    jarayon_xabari = await message.answer("🤖 Hujjat tahlil qilinmoqda… ⏳")

    fayl_info = await bot.get_file(message.photo[-1].file_id)
    buf       = io.BytesIO()
    await bot.download_file(fayl_info.file_path, buf)

    javob = await utils.ask_ai_about_image(buf.getvalue(), savol)

    await jarayon_xabari.delete()
    await message.answer(
        f"🤖 **AI Javobi:**\n\n{javob}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yana so'rash",   callback_data="ai_start")],
            [InlineKeyboardButton(text="🏠 Asosiy Menyu",   callback_data="main_menu")],
        ])
    )
    await state.clear()


# ─────────────────────────────────────────────────────────────────────────────
#  ADMIN PANELI
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Ruxsat yo'q.")
        return
    await message.answer(
        "🛠 **Admin Paneli**\n\nKerakli amalni tanlang:",
        parse_mode="Markdown",
        reply_markup=admin_panel_kb()
    )


@router.callback_query(F.data == "admin_stats")
async def cb_statistika(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return
    jami    = await db.get_user_count()
    premium = await db.get_premium_count()
    bepul   = jami - premium
    await call.message.edit_text(
        f"📊 **Bot Statistikasi**\n\n"
        f"👥 Jami foydalanuvchilar: **{jami}**\n"
        f"⭐ Premium foydalanuvchilar: **{premium}**\n"
        f"🆓 Bepul foydalanuvchilar: **{bepul}**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]
        ])
    )
    await call.answer()


@router.callback_query(F.data == "admin_back")
async def cb_admin_orqaga(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer()
        return
    await call.message.edit_text(
        "🛠 **Admin Paneli**\n\nKerakli amalni tanlang:",
        parse_mode="Markdown",
        reply_markup=admin_panel_kb()
    )
    await call.answer()


@router.callback_query(F.data == "admin_set_card")
async def cb_karta_yangilash(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminHolat.karta_kutish)
    joriy = await db.get_setting("card_number", "O'rnatilmagan")
    await call.message.edit_text(
        f"💳 **Karta Raqamini Yangilash**\n\n"
        f"Joriy raqam: `{joriy}`\n\n"
        f"Yangi karta raqamini yuboring:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_back")]
        ])
    )
    await call.answer()


@router.message(AdminHolat.karta_kutish)
async def karta_qabul(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    yangi_karta = message.text.strip()
    await db.set_setting("card_number", yangi_karta)
    await state.clear()
    await message.answer(
        f"✅ Karta raqami yangilandi:\n`{yangi_karta}`",
        parse_mode="Markdown",
        reply_markup=admin_panel_kb()
    )


@router.callback_query(F.data == "admin_broadcast")
async def cb_xabar_yuborish(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminHolat.xabar_kutish)
    await call.message.edit_text(
        "📢 **Hammaga Xabar Yuborish**\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni yozing.\n"
        "Markdown formatidan foydalanishingiz mumkin.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_back")]
        ])
    )
    await call.answer()


@router.message(AdminHolat.xabar_kutish)
async def xabar_yuborish(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return

    xabar_matni = message.text
    await state.clear()

    foydalanuvchilar = await db.get_all_user_ids()
    yuborildi        = 0
    xato             = 0
    holat_xabari     = await message.answer(f"📤 {len(foydalanuvchilar)} ta foydalanuvchiga yuborilmoqda…")

    for uid in foydalanuvchilar:
        try:
            await bot.send_message(uid, xabar_matni, parse_mode="Markdown")
            yuborildi += 1
        except Exception:
            xato += 1
        await asyncio.sleep(0.05)

    await holat_xabari.edit_text(
        f"✅ **Xabar yuborish yakunlandi!**\n\n"
        f"📨 Yuborildi: **{yuborildi}**\n"
        f"❌ Xato: **{xato}**",
        parse_mode="Markdown",
        reply_markup=admin_panel_kb()
    )


# ─────────────────────────────────────────────────────────────────────────────
#  NOMA'LUM XABARLAR
# ─────────────────────────────────────────────────────────────────────────────

@router.message()
async def noma_lum(message: Message, state: FSMContext):
    await foydalanuvchi_qoshish(message)
    joriy_holat = await state.get_state()

    if joriy_holat == ScanSession.rasm_qabul.state:
        await message.answer(
            "📸 Iltimos, **rasm** yuboring yoki **PDF yaratish** tugmasini bosing.",
            parse_mode="Markdown",
            reply_markup=pdf_tayyor_kb()
        )
    else:
        premium = await db.is_premium(message.from_user.id)
        await message.answer(
            "👋 Quyidagi menyudan boshlang!",
            reply_markup=asosiy_menu(premium)
        )
