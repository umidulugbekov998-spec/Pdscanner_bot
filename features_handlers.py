# features_handlers.py — Qo'shimcha imkoniyatlar handlerlari
# OCR, QR, Fon o'chirish, Valyuta, Tarjimon, Referal

import io
import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, BufferedInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import features as ft
from config import BOT_USERNAME, ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()


# ═══════════════════════════════════════════════════════════════
#  FSM HOLATLARI
# ═══════════════════════════════════════════════════════════════

class OCRHolat(StatesGroup):
    rasm_kutish = State()

class QRHolat(StatesGroup):
    matn_kutish = State()
    oqish_kutish = State()

class FonHolat(StatesGroup):
    rasm_kutish = State()

class TarjimonHolat(StatesGroup):
    til_tanlash = State()
    matn_kutish = State()

class ValyutaHolat(StatesGroup):
    hisoblash = State()


# ═══════════════════════════════════════════════════════════════
#  ASOSIY MENYU — YANGI TUGMALAR
# ═══════════════════════════════════════════════════════════════

def qoshimcha_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔤 OCR — Matn o'qish",    callback_data="ocr_start"),
            InlineKeyboardButton(text="📱 QR Kod",               callback_data="qr_menu"),
        ],
        [
            InlineKeyboardButton(text="🖼 Fon O'chirish",        callback_data="fon_start"),
            InlineKeyboardButton(text="💱 Valyuta Kursi",        callback_data="valyuta_menu"),
        ],
        [
            InlineKeyboardButton(text="🌐 Tarjimon",             callback_data="tarjimon_menu"),
            InlineKeyboardButton(text="👥 Referal",              callback_data="referal_menu"),
        ],
        [InlineKeyboardButton(text="🔙 Asosiy Menyu",           callback_data="main_menu")],
    ])


# ═══════════════════════════════════════════════════════════════
#  OCR — RASMDAN MATN O'QISH
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ocr_start")
async def cb_ocr_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(OCRHolat.rasm_kutish)
    await call.message.edit_text(
        "🔤 **OCR — Rasmdan Matn O'qish**\n\n"
        "Matn ajratmoqchi bo'lgan **rasmni** yuboring.\n\n"
        "📌 Qo'llab-quvvatlanadigan tillar:\n"
        "• O'zbek 🇺🇿\n"
        "• Rus 🇷🇺\n"
        "• Ingliz 🇺🇸",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="main_menu")]
        ])
    )
    await call.answer()


@router.message(OCRHolat.rasm_kutish, F.photo)
async def ocr_rasm_qabul(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    jarayon = await message.answer("🔤 Matn o'qilmoqda… ⏳")

    fi  = await bot.get_file(message.photo[-1].file_id)
    buf = io.BytesIO()
    await bot.download_file(fi.file_path, buf)

    matn = ft.ocr_rasmdan_matn(buf.getvalue())

    await jarayon.delete()

    if len(matn) > 3000:
        # Uzun matnni fayl sifatida yuborish
        await message.answer_document(
            BufferedInputFile(matn.encode("utf-8"), filename="matn.txt"),
            caption="📄 Matn juda uzun — fayl sifatida yuborildi."
        )
    else:
        await message.answer(
            f"✅ **O'qilgan Matn:**\n\n`{matn}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Tarjima qilish", callback_data="tarjimon_menu")],
                [InlineKeyboardButton(text="🔄 Yana o'qish",    callback_data="ocr_start")],
                [InlineKeyboardButton(text="🏠 Asosiy Menyu",   callback_data="main_menu")],
            ])
        )


# ═══════════════════════════════════════════════════════════════
#  QR KOD
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "qr_menu")
async def cb_qr_menu(call: CallbackQuery):
    await call.message.edit_text(
        "📱 **QR Kod**\n\nNima qilmoqchisiz?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ QR Yaratish",  callback_data="qr_yaratish")],
            [InlineKeyboardButton(text="📷 QR O'qish",    callback_data="qr_oqish")],
            [InlineKeyboardButton(text="🔙 Orqaga",       callback_data="main_menu")],
        ])
    )
    await call.answer()


@router.callback_query(F.data == "qr_yaratish")
async def cb_qr_yaratish(call: CallbackQuery, state: FSMContext):
    await state.set_state(QRHolat.matn_kutish)
    await call.message.edit_text(
        "✏️ **QR Kod Yaratish**\n\n"
        "QR kodga aylantirilishi kerak bo'lgan **matn yoki linkni** yuboring.\n\n"
        "**Misol:**\n"
        "• `https://t.me/Pdscanner_bot`\n"
        "• `+998901234567`\n"
        "• `Istalgan matn`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="qr_menu")]
        ])
    )
    await call.answer()


@router.message(QRHolat.matn_kutish)
async def qr_matn_qabul(message: Message, state: FSMContext):
    await state.clear()
    jarayon = await message.answer("📱 QR kod yaratilmoqda… ⏳")

    qr_bytes = ft.qr_yaratish(message.text)

    await jarayon.delete()
    await message.answer_photo(
        BufferedInputFile(qr_bytes, filename="qr_kod.png"),
        caption=f"✅ **QR Kod Tayyor!**\n\n📝 Matn: `{message.text[:100]}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yana yaratish", callback_data="qr_yaratish")],
            [InlineKeyboardButton(text="🏠 Asosiy Menyu",  callback_data="main_menu")],
        ])
    )


@router.callback_query(F.data == "qr_oqish")
async def cb_qr_oqish(call: CallbackQuery, state: FSMContext):
    await state.set_state(QRHolat.oqish_kutish)
    await call.message.edit_text(
        "📷 **QR Kod O'qish**\n\n"
        "QR kod yoki barcode bo'lgan **rasmni** yuboring.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="qr_menu")]
        ])
    )
    await call.answer()


@router.message(QRHolat.oqish_kutish, F.photo)
async def qr_oqish_rasm(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    fi  = await bot.get_file(message.photo[-1].file_id)
    buf = io.BytesIO()
    await bot.download_file(fi.file_path, buf)

    natija = ft.qr_oqish(buf.getvalue())

    await message.answer(
        f"📱 **QR Kod Natijasi:**\n\n{natija}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yana o'qish",  callback_data="qr_oqish")],
            [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="main_menu")],
        ])
    )


# ═══════════════════════════════════════════════════════════════
#  FON O'CHIRISH
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "fon_start")
async def cb_fon_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(FonHolat.rasm_kutish)
    await call.message.edit_text(
        "🖼 **Fon O'chirish**\n\n"
        "Fonini o'chirmoqchi bo'lgan **rasmni** yuboring.\n\n"
        "✅ Natija PNG formatida (shaffof fon) qaytariladi.\n\n"
        "⚠️ _Premium foydalanuvchilar uchun sifat yuqoriroq_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="main_menu")]
        ])
    )
    await call.answer()


@router.message(FonHolat.rasm_kutish, F.photo)
async def fon_rasm_qabul(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    premium = await db.is_premium(message.from_user.id)
    jarayon = await message.answer(
        f"🖼 Fon o'chirilmoqda… ⏳\n"
        f"{'⭐ Premium sifat' if premium else '🆓 Oddiy sifat'}"
    )

    fi  = await bot.get_file(message.photo[-1].file_id)
    buf = io.BytesIO()
    await bot.download_file(fi.file_path, buf)

    natija = ft.fon_ochirish(buf.getvalue())

    await jarayon.delete()
    await message.answer_document(
        BufferedInputFile(natija, filename="fon_ochirilgan.png"),
        caption="✅ **Fon O'chirildi!**\n\nRasm PNG formatida — shaffof fon bilan.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yana o'chirish", callback_data="fon_start")],
            [InlineKeyboardButton(text="🏠 Asosiy Menyu",   callback_data="main_menu")],
        ])
    )


# ═══════════════════════════════════════════════════════════════
#  VALYUTA KURSI
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "valyuta_menu")
async def cb_valyuta(call: CallbackQuery):
    jarayon = await call.message.edit_text("💱 Kurslar yuklanmoqda… ⏳")
    matn = ft.valyuta_kursi()
    await jarayon.edit_text(
        matn,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Hisoblash",     callback_data="valyuta_hisob")],
            [InlineKeyboardButton(text="🔄 Yangilash",     callback_data="valyuta_menu")],
            [InlineKeyboardButton(text="🔙 Asosiy Menyu",  callback_data="main_menu")],
        ])
    )
    await call.answer()


@router.callback_query(F.data == "valyuta_hisob")
async def cb_valyuta_hisob(call: CallbackQuery, state: FSMContext):
    await state.set_state(ValyutaHolat.hisoblash)
    await call.message.edit_text(
        "💱 **Valyuta Hisoblash**\n\n"
        "Quyidagi formatda yuboring:\n\n"
        "`100 USD UZS` — 100 dollar so'mga\n"
        "`50000 UZS USD` — 50000 so'm dollarga\n"
        "`200 EUR RUB` — 200 evro rublga",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="valyuta_menu")]
        ])
    )
    await call.answer()


@router.message(ValyutaHolat.hisoblash)
async def valyuta_hisob_qabul(message: Message, state: FSMContext):
    await state.clear()
    try:
        qismlar = message.text.strip().upper().split()
        if len(qismlar) != 3:
            raise ValueError("Format noto'g'ri")

        miqdor = float(qismlar[0])
        dan    = qismlar[1]
        ga     = qismlar[2]

        natija = ft.valyuta_hisoblash(miqdor, dan, ga)
        await message.answer(
            natija, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Yana hisoblash", callback_data="valyuta_hisob")],
                [InlineKeyboardButton(text="💱 Kurslar",        callback_data="valyuta_menu")],
            ])
        )
    except Exception:
        await message.answer(
            "❌ Format noto'g'ri!\n\n"
            "To'g'ri format: `100 USD UZS`",
            parse_mode="Markdown"
        )


# ═══════════════════════════════════════════════════════════════
#  TARJIMON
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tarjimon_menu")
async def cb_tarjimon(call: CallbackQuery, state: FSMContext):
    await state.set_state(TarjimonHolat.til_tanlash)
    await call.message.edit_text(
        "🌐 **Tarjimon**\n\nQaysi tilga tarjima qilmoqchisiz?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbek",   callback_data="til_uz"),
                InlineKeyboardButton(text="🇷🇺 Rus",      callback_data="til_ru"),
            ],
            [
                InlineKeyboardButton(text="🇺🇸 Ingliz",   callback_data="til_en"),
                InlineKeyboardButton(text="🇹🇷 Turk",     callback_data="til_tr"),
            ],
            [
                InlineKeyboardButton(text="🇸🇦 Arab",     callback_data="til_ar"),
                InlineKeyboardButton(text="🇨🇳 Xitoy",    callback_data="til_zh-cn"),
            ],
            [
                InlineKeyboardButton(text="🇩🇪 Nemis",    callback_data="til_de"),
                InlineKeyboardButton(text="🇰🇷 Koreys",   callback_data="til_ko"),
            ],
            [InlineKeyboardButton(text="🔙 Orqaga",       callback_data="main_menu")],
        ])
    )
    await call.answer()


@router.callback_query(F.data.startswith("til_"))
async def cb_til_tanlandi(call: CallbackQuery, state: FSMContext):
    til = call.data.replace("til_", "")
    await state.update_data(til=til)
    await state.set_state(TarjimonHolat.matn_kutish)

    til_nomlari = {
        "uz": "O'zbek 🇺🇿", "ru": "Rus 🇷🇺", "en": "Ingliz 🇺🇸",
        "tr": "Turk 🇹🇷", "ar": "Arab 🇸🇦", "zh-cn": "Xitoy 🇨🇳",
        "de": "Nemis 🇩🇪", "ko": "Koreys 🇰🇷"
    }

    await call.message.edit_text(
        f"🌐 **{til_nomlari.get(til, til)} tiliga tarjima**\n\n"
        f"Tarjima qilmoqchi bo'lgan **matnni** yuboring:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tarjimon_menu")]
        ])
    )
    await call.answer()


@router.message(TarjimonHolat.matn_kutish)
async def tarjimon_matn_qabul(message: Message, state: FSMContext):
    data = await state.get_data()
    til  = data.get("til", "uz")
    await state.clear()

    jarayon = await message.answer("🌐 Tarjima qilinmoqda… ⏳")
    natija  = ft.matn_tarjima(message.text, til)
    await jarayon.delete()

    await message.answer(
        natija, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yana tarjima",  callback_data="tarjimon_menu")],
            [InlineKeyboardButton(text="🏠 Asosiy Menyu",  callback_data="main_menu")],
        ])
    )


# ═══════════════════════════════════════════════════════════════
#  REFERAL TIZIM
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "referal_menu")
async def cb_referal(call: CallbackQuery):
    u    = call.from_user
    link = ft.referal_link_yaratish(u.id, BOT_USERNAME)

    # Referal statistikani olish
    try:
        count  = await db.get_referal_count(u.id)
        earned = await db.get_referal_bonus(u.id)
    except Exception:
        count  = 0
        earned = 0

    await call.message.edit_text(
        f"👥 **Referal Tizim**\n\n"
        f"Do'stlaringizni taklif qiling va bonus oling!\n\n"
        f"🔗 **Sizning havolangiz:**\n`{link}`\n\n"
        f"📊 **Statistika:**\n"
        f"👤 Taklif qilganlar: **{count}** kishi\n"
        f"🎁 Bonus: **{earned}** ta skanerlash\n\n"
        f"💡 **Qoidalar:**\n"
        f"• Har 1 ta taklif = 5 ta bepul skanerlash\n"
        f"• 10 ta taklif = 1 oy Premium\n"
        f"• Cheksiz taklif qilish mumkin!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Ulashish", switch_inline_query=f"Do'stingizni @{BOT_USERNAME} ga taklif qiling!")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")],
        ])
    )
    await call.answer()
