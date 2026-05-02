# utils.py — Yaxshilangan rasm ishlov berish va PDF yaratish

import io
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import img2pdf
import logging
import base64
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY_HERE")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
WATERMARK_TEXT = "📄 @Pdscanner_bot — Premium oling!"


# ── Auto-crop ──────────────────────────────────────────────────────────────────

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    widthA  = np.linalg.norm(br - bl)
    widthB  = np.linalg.norm(tr - tl)
    maxW    = max(int(widthA), int(widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxH    = max(int(heightA), int(heightB))
    dst = np.array([[0,0],[maxW-1,0],[maxW-1,maxH-1],[0,maxH-1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxW, maxH))


def auto_crop(img_bytes):
    nparr = np.frombuffer(img_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    orig  = img.copy()

    gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged   = cv2.Canny(blurred, 75, 200)

    contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours     = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    screen_cnt = None
    for c in contours:
        peri   = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            screen_cnt = approx
            break

    result = four_point_transform(orig, screen_cnt.reshape(4, 2)) if screen_cnt is not None else orig
    _, buf = cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, 98])
    return buf.tobytes()


# ── Filtrlar ───────────────────────────────────────────────────────────────────

def apply_magic_color(img_bytes, high_quality=False):
    """Sehrli rang filtri — yuqori sifatli versiya."""
    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    # Yuqori sifat uchun kattalashtirish
    if high_quality:
        w, h = pil_img.size
        pil_img = pil_img.resize((w * 2, h * 2), Image.LANCZOS)

    # Keskinlashtirish
    pil_img = pil_img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

    # Kontrast
    pil_img = ImageEnhance.Contrast(pil_img).enhance(1.5)

    # To'yinganlik
    pil_img = ImageEnhance.Color(pil_img).enhance(1.3)

    # Yorqinlik
    pil_img = ImageEnhance.Brightness(pil_img).enhance(1.1)

    # Keskinlik
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(2.5)

    sifat = 97 if high_quality else 90
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=sifat, optimize=True)
    return buf.getvalue()


def apply_bw_filter(img_bytes, high_quality=False):
    """Qora-oq filtri — adaptiv chegara."""
    nparr = np.frombuffer(img_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if high_quality:
        h, w = img.shape[:2]
        img = cv2.resize(img, (w*2, h*2), interpolation=cv2.INTER_CUBIC)

    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Shovqinni kamaytirish
    gray = cv2.fastNlMeansDenoising(gray, h=10)

    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=15, C=8
    )

    sifat = 97 if high_quality else 90
    _, buf = cv2.imencode(".jpg", thresh, [cv2.IMWRITE_JPEG_QUALITY, sifat])
    return buf.tobytes()


# ── Suv belgisi ────────────────────────────────────────────────────────────────

def add_watermark(img_bytes, text=WATERMARK_TEXT):
    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    w, h    = pil_img.size

    overlay  = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))
    draw     = ImageDraw.Draw(overlay)
    banner_h = max(35, int(h * 0.045))

    draw.rectangle([(0, h - banner_h), (w, h)], fill=(0, 0, 0, 180))

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                  max(14, banner_h - 10))
    except Exception:
        font = ImageFont.load_default()

    bbox   = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_x = (w - text_w) // 2
    text_y = h - banner_h + (banner_h - (bbox[3] - bbox[1])) // 2
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 240))

    combined = Image.alpha_composite(pil_img, overlay).convert("RGB")
    buf = io.BytesIO()
    combined.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


# ── Siqish ─────────────────────────────────────────────────────────────────────

def compress_image(img_bytes, target_quality=60):
    """Rasmni siqib, fayl hajmini kamaytiradi."""
    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    # Hajmni kamaytirish (max 1200px kenglik)
    w, h = pil_img.size
    if w > 1200:
        ratio = 1200 / w
        pil_img = pil_img.resize((1200, int(h * ratio)), Image.LANCZOS)

    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=target_quality, optimize=True)
    return buf.getvalue()


# ── To'liq pipeline ────────────────────────────────────────────────────────────

def process_image(img_bytes, mode="a4", filter_type="magic_color",
                  apply_crop=True, watermark=True,
                  high_quality=False, compress=False):
    """
    To'liq skanerlash jarayoni:
    1. Auto-crop
    2. Filtr
    3. Siqish (ixtiyoriy)
    4. Suv belgisi (bepul foydalanuvchilar uchun)
    """
    data = img_bytes

    if apply_crop:
        try:
            data = auto_crop(data)
        except Exception as e:
            logger.warning(f"Auto-crop xato: {e}")

    if filter_type == "magic_color":
        data = apply_magic_color(data, high_quality=high_quality)
    elif filter_type == "bw":
        data = apply_bw_filter(data, high_quality=high_quality)

    if compress:
        data = compress_image(data, target_quality=55)

    if watermark:
        data = add_watermark(data)

    return data


# ── PDF yaratish ───────────────────────────────────────────────────────────────

def images_to_pdf(image_bytes_list):
    """Rasmlar ro'yxatidan PDF yaratish."""
    return img2pdf.convert(image_bytes_list)


# ── AI Yordamchi ───────────────────────────────────────────────────────────────

async def ask_ai_about_image(img_bytes, user_question):
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1500,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Siz hujjat tahlili bo'yicha yordamchisiz. "
                        "Foydalanuvchi hujjat rasmini yuboradi va savol beradi. "
                        "O'zbek tilida aniq, qisqa va foydali javob bering."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
                        {"type": "text", "text": user_question}
                    ]
                }
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI xato: {e}")
        return "⚠️ AI yordamchi hozircha ishlamayapti. Keyinroq urinib ko'ring."
