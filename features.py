# features.py — Qo'shimcha imkoniyatlar moduli
# OCR, QR, Fon o'chirish, Valyuta, Tarjimon, Referal

import io
import os
import qrcode
import requests
import logging
from PIL import Image

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  OCR — RASMDAN MATN AJRATISH
# ═══════════════════════════════════════════════════════════════

def ocr_rasmdan_matn(img_bytes: bytes) -> str:
    """
    Rasmdan matnni ajratib oladi.
    pytesseract ishlatadi — serverda o'rnatish kerak:
    sudo apt install tesseract-ocr tesseract-ocr-uzb tesseract-ocr-rus
    """
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # O'zbek + Rus + Ingliz tillari
        matn = pytesseract.image_to_string(img, lang="uzb+rus+eng")
        matn = matn.strip()

        if not matn:
            return "❌ Rasmda o'qiladigan matn topilmadi."
        return matn

    except ImportError:
        return "⚠️ OCR xizmati o'rnatilmagan."
    except Exception as e:
        logger.error(f"OCR xato: {e}")
        return f"❌ OCR xato: {str(e)}"


# ═══════════════════════════════════════════════════════════════
#  QR KOD — YARATISH VA O'QISH
# ═══════════════════════════════════════════════════════════════

def qr_yaratish(matn: str) -> bytes:
    """Matndan QR kod rasmini yaratadi."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )
    qr.add_data(matn)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def qr_oqish(img_bytes: bytes) -> str:
    """Rasmdan QR kod yoki barcodeni o'qiydi."""
    try:
        from pyzbar.pyzbar import decode
        import numpy as np
        import cv2

        nparr = np.frombuffer(img_bytes, np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        natijalar = decode(img)
        if not natijalar:
            return "❌ Rasmda QR kod yoki barcode topilmadi."

        matn = ""
        for r in natijalar:
            tur  = r.type
            data = r.data.decode("utf-8", errors="ignore")
            matn += f"📌 **Tur:** {tur}\n📝 **Ma'lumot:** `{data}`\n\n"
        return matn.strip()

    except ImportError:
        return "⚠️ QR o'qish xizmati o'rnatilmagan."
    except Exception as e:
        logger.error(f"QR o'qish xato: {e}")
        return f"❌ Xato: {str(e)}"


# ═══════════════════════════════════════════════════════════════
#  FON O'CHIRISH
# ═══════════════════════════════════════════════════════════════

def fon_ochirish(img_bytes: bytes) -> bytes:
    """
    Rasmdan fonni avtomatik o'chiradi.
    rembg kutubxonasi ishlatadi.
    """
    try:
        from rembg import remove

        natija = remove(img_bytes)
        return natija

    except ImportError:
        # rembg yo'q bo'lsa oddiy usul bilan
        logger.warning("rembg yo'q, oddiy usul ishlatilmoqda")
        return _fon_ochirish_oddiy(img_bytes)
    except Exception as e:
        logger.error(f"Fon o'chirish xato: {e}")
        return img_bytes


def _fon_ochirish_oddiy(img_bytes: bytes) -> bytes:
    """GrabCut algoritmi bilan fon o'chirish."""
    import cv2
    import numpy as np

    nparr = np.frombuffer(img_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    mask  = np.zeros(img.shape[:2], np.uint8)

    h, w = img.shape[:2]
    rect = (10, 10, w - 20, h - 20)

    bgModel = np.zeros((1, 65), np.float64)
    fgModel = np.zeros((1, 65), np.float64)

    cv2.grabCut(img, mask, rect, bgModel, fgModel, 5, cv2.GC_INIT_WITH_RECT)

    mask2  = np.where((mask == 2) | (mask == 0), 0, 1).astype("uint8")
    result = img * mask2[:, :, np.newaxis]

    # PNG formatida saqlash (shaffoflik uchun)
    pil_img = Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
    pil_rgba = pil_img.convert("RGBA")

    # Qora piksellarni shaffof qilish
    data = pil_rgba.getdata()
    yangi_data = []
    for piksel in data:
        if piksel[0] < 10 and piksel[1] < 10 and piksel[2] < 10:
            yangi_data.append((0, 0, 0, 0))
        else:
            yangi_data.append(piksel)
    pil_rgba.putdata(yangi_data)

    buf = io.BytesIO()
    pil_rgba.save(buf, format="PNG")
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  VALYUTA KURSI
# ═══════════════════════════════════════════════════════════════

def valyuta_kursi() -> str:
    """O'zbekiston Markaziy Banki API dan valyuta kurslarini oladi."""
    try:
        url = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
        response = requests.get(url, timeout=10)
        data     = response.json()

        # Kerakli valyutalarni filtrlash
        keraklilar = ["USD", "EUR", "RUB", "GBP", "CNY", "KZT", "TRY"]

        emoji_map = {
            "USD": "🇺🇸", "EUR": "🇪🇺", "RUB": "🇷🇺",
            "GBP": "🇬🇧", "CNY": "🇨🇳", "KZT": "🇰🇿", "TRY": "🇹🇷"
        }

        matn = "💱 **Valyuta Kurslari** (CBU)\n\n"
        for v in data:
            if v["Ccy"] in keraklilar:
                emoji = emoji_map.get(v["Ccy"], "💰")
                nom   = v["CcyNm_UZ"]
                kurs  = float(v["Rate"])
                matn += f"{emoji} **{v['Ccy']}** — `{kurs:,.2f}` so'm\n"

        matn += f"\n🕐 Yangilandi: {data[0].get('Date', 'noma\'lum')}"
        return matn

    except Exception as e:
        logger.error(f"Valyuta xato: {e}")
        return "❌ Valyuta kurslari olishda xato. Keyinroq urinib ko'ring."


def valyuta_hisoblash(miqdor: float, dan: str, ga: str) -> str:
    """Valyutani boshqasiga hisoblaydi."""
    try:
        url  = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
        resp = requests.get(url, timeout=10)
        data = resp.json()

        kurslar = {"UZS": 1.0}
        for v in data:
            kurslar[v["Ccy"]] = float(v["Rate"])

        dan = dan.upper()
        ga  = ga.upper()

        if dan not in kurslar or ga not in kurslar:
            return f"❌ '{dan}' yoki '{ga}' valyuta topilmadi."

        uzs_miqdor = miqdor * kurslar[dan]
        natija     = uzs_miqdor / kurslar[ga]

        return (
            f"💱 **Hisoblash Natijasi:**\n\n"
            f"`{miqdor:,.2f} {dan}` = `{natija:,.2f} {ga}`"
        )

    except Exception as e:
        return f"❌ Hisoblashda xato: {str(e)}"


# ═══════════════════════════════════════════════════════════════
#  TARJIMON
# ═══════════════════════════════════════════════════════════════

def matn_tarjima(matn: str, til: str = "uz") -> str:
    """
    Google Translate API (bepul versiya) orqali tarjima qiladi.
    googletrans kutubxonasi ishlatadi.
    """
    try:
        from googletrans import Translator

        translator = Translator()

        til_nomlari = {
            "uz": "O'zbek 🇺🇿",
            "ru": "Rus 🇷🇺",
            "en": "Ingliz 🇺🇸",
            "tr": "Turk 🇹🇷",
            "ar": "Arab 🇸🇦",
            "zh-cn": "Xitoy 🇨🇳",
            "de": "Nemis 🇩🇪",
            "fr": "Fransuz 🇫🇷",
            "ko": "Koreys 🇰🇷",
            "ja": "Yapon 🇯🇵",
        }

        natija = translator.translate(matn, dest=til)
        manba_til = til_nomlari.get(natija.src, natija.src)
        maqsad_til = til_nomlari.get(til, til)

        return (
            f"🌐 **Tarjima**\n\n"
            f"📥 Manba: {manba_til}\n"
            f"📤 Maqsad: {maqsad_til}\n\n"
            f"**Natija:**\n{natija.text}"
        )

    except ImportError:
        return "⚠️ Tarjimon xizmati o'rnatilmagan."
    except Exception as e:
        logger.error(f"Tarjima xato: {e}")
        return f"❌ Tarjimada xato: {str(e)}"


# ═══════════════════════════════════════════════════════════════
#  REFERAL TIZIM
# ═══════════════════════════════════════════════════════════════

def referal_link_yaratish(user_id: int, bot_username: str) -> str:
    """Foydalanuvchi uchun referal link yaratadi."""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


async def referal_statistika(user_id: int) -> dict:
    """Foydalanuvchining referal statistikasini qaytaradi."""
    import database as db

    try:
        count  = await db.get_referal_count(user_id)
        earned = await db.get_referal_bonus(user_id)
        return {"count": count, "earned": earned}
    except Exception:
        return {"count": 0, "earned": 0}
