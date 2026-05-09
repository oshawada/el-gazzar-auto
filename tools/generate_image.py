# tools/generate_image.py
# Purpose: Generate branded article image matching almuraba.net visual style:
#          [TOP BAR: brand color + title] [CENTER: car photo] [BOTTOM BAR: logo]
# Inputs:  .tmp/article_arabic.json
# Outputs: .tmp/article_image.jpg

import json
import os
import sys
import urllib.parse
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

ROOT_DIR = Path(__file__).parent.parent
TMP_DIR = ROOT_DIR / ".tmp"
INPUT_FILE = TMP_DIR / "article_arabic.json"
OUTPUT_FILE = TMP_DIR / "article_image.jpg"

IMG_W, IMG_H = 1200, 630


# ── helpers ────────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _find_logo() -> Path | None:
    candidates = [
        ROOT_DIR / os.environ.get("LOGO_PATH", "assets/logo.png"),
        ROOT_DIR / "assets" / "logo.png.PNG",
        ROOT_DIR / "assets" / "logo.png",
        ROOT_DIR / "assets" / "logo.PNG",
        ROOT_DIR / "assets" / "logo.jpeg",
        ROOT_DIR / "assets" / "logo.jpg",
    ]
    for p in candidates:
        if Path(p).exists():
            return Path(p)
    return None


def _find_font(size: int, bold: bool = True):
    from PIL import ImageFont
    candidates = []
    if bold:
        candidates = [
            ROOT_DIR / "assets" / "fonts" / "tahomabd.ttf",
            "C:/Windows/Fonts/tahomabd.ttf",
            "/usr/share/fonts/truetype/msttcorefonts/Tahoma_Bold.ttf",
            ROOT_DIR / "assets" / "fonts" / "tahoma.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "/usr/share/fonts/truetype/msttcorefonts/Tahoma.ttf",
        ]
    else:
        candidates = [
            ROOT_DIR / "assets" / "fonts" / "tahoma.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "/usr/share/fonts/truetype/msttcorefonts/Tahoma.ttf",
            ROOT_DIR / "assets" / "fonts" / "tahomabd.ttf",
            "C:/Windows/Fonts/tahomabd.ttf",
        ]
    for p in candidates:
        try:
            return ImageFont.truetype(str(p), size)
        except Exception:
            continue
    return ImageFont.load_default()


def _measure_text(draw, text: str, font) -> int:
    try:
        return int(draw.textlength(text, font=font))
    except AttributeError:
        return draw.textsize(text, font=font)[0]


def _draw_arabic_text_centered(draw, text: str, font, y_center: int, x_center: int,
                                fill=(255, 255, 255, 255), shadow=True):
    """Draw reshaped Arabic text centered at (x_center, y_center)."""
    import arabic_reshaper
    from bidi.algorithm import get_display
    shaped = get_display(arabic_reshaper.reshape(text))
    if shadow:
        for dx, dy in [(2, 2), (-2, 2), (2, -2), (-2, -2)]:
            draw.text((x_center + dx, y_center + dy), shaped, font=font,
                      fill=(0, 0, 0, 160), anchor="mm")
    draw.text((x_center, y_center), shaped, font=font, fill=fill, anchor="mm")


def _wrap_arabic_lines(title: str, font, max_width: int, draw) -> list[str]:
    """Split title into display lines respecting max_width."""
    import arabic_reshaper
    from bidi.algorithm import get_display
    words = title.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        shaped = get_display(arabic_reshaper.reshape(test))
        if _measure_text(draw, shaped, font) > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines[:3]


def _composite_overlay(img_path: Path, title: str, primary_hex: str, accent_hex: str) -> None:
    """
    Apply almuraba.net-style branded overlay:
      TOP BAR  (28% height) — brand primary color + Arabic title (white)
      CENTER   (60% height) — car photo (no overlay, clean)
      BOTTOM BAR (12% height) — brand primary color + centered logo
    """
    from PIL import Image, ImageDraw

    pr, pg, pb = _hex_to_rgb(primary_hex)
    ar, ag, ab = _hex_to_rgb(accent_hex)

    car_img = Image.open(img_path).convert("RGBA")
    cw, ch = car_img.size

    # Heights of each zone
    top_h    = int(IMG_H * 0.28)   # title bar
    accent_h = max(6, IMG_H // 100) # thin accent stripe
    bot_h    = int(IMG_H * 0.14)   # logo bar
    car_h    = IMG_H - top_h - accent_h - bot_h

    # Canvas
    canvas = Image.new("RGBA", (IMG_W, IMG_H), (pr, pg, pb, 255))
    draw = ImageDraw.Draw(canvas)

    # ── TOP BAR: primary color (already filled) ──────────────────────────────
    # Accent stripe at bottom of top bar
    draw.rectangle([(0, top_h), (IMG_W, top_h + accent_h)], fill=(ar, ag, ab, 255))

    # ── TITLE TEXT in top bar ─────────────────────────────────────────────────
    text_margin = int(IMG_W * 0.05)
    max_text_w = IMG_W - text_margin * 2
    padding_v = int(top_h * 0.10)          # vertical padding inside bar
    available_h = top_h - padding_v * 2    # usable height for text

    # Auto-fit font: reduce size until all lines fit inside available_h
    font_size = max(36, int(top_h * 0.40))
    font = _find_font(font_size, bold=True)
    lines = _wrap_arabic_lines(title, font, max_text_w, draw)
    line_h = int(font_size * 1.28)

    while len(lines) * line_h > available_h and font_size > 32:
        font_size -= 3
        font = _find_font(font_size, bold=True)
        lines = _wrap_arabic_lines(title, font, max_text_w, draw)
        line_h = int(font_size * 1.28)

    total_txt_h = len(lines) * line_h
    txt_start_y = padding_v + (available_h - total_txt_h) // 2 + line_h // 2

    for i, line in enumerate(lines):
        y = txt_start_y + i * line_h
        _draw_arabic_text_centered(draw, line, font, y, IMG_W // 2,
                                   fill=(255, 255, 255, 255), shadow=True)

    # ── CAR PHOTO in center zone ──────────────────────────────────────────────
    car_y = top_h + accent_h
    # Scale car image to fill center zone width, crop height to fit
    ratio = IMG_W / cw
    scaled_h = int(ch * ratio)
    car_resized = car_img.resize((IMG_W, scaled_h), Image.LANCZOS)

    # Crop to car_h, centered vertically
    if scaled_h > car_h:
        crop_top = (scaled_h - car_h) // 2
        car_resized = car_resized.crop((0, crop_top, IMG_W, crop_top + car_h))
    else:
        # Fill gaps with primary color (already on canvas)
        car_h = scaled_h

    canvas.paste(car_resized, (0, car_y), car_resized)

    # ── BOTTOM BAR: primary color + logo ─────────────────────────────────────
    bot_y = IMG_H - bot_h
    draw.rectangle([(0, bot_y), (IMG_W, IMG_H)], fill=(pr, pg, pb, 255))

    # Thin accent line at top of bottom bar
    draw.rectangle([(0, bot_y), (IMG_W, bot_y + accent_h)], fill=(ar, ag, ab, 255))

    logo_path = _find_logo()
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            # Scale logo to fit inside bottom bar with padding
            padding = int(bot_h * 0.15)
            logo_max_h = bot_h - padding * 2
            logo_max_w = int(IMG_W * 0.25)
            r = min(logo_max_h / logo.height, logo_max_w / logo.width)
            logo_w = int(logo.width * r)
            logo_h = int(logo.height * r)
            logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
            lx = (IMG_W - logo_w) // 2
            ly = bot_y + (bot_h - logo_h) // 2 + accent_h
            canvas.paste(logo, (lx, ly), logo)
        except Exception as e:
            print(f"[image] Logo skipped: {e}")

    canvas.convert("RGB").save(img_path, "JPEG", quality=93, optimize=True)
    print(f"[image] Composite saved — {IMG_W}×{IMG_H}px")


# ── prompt building ────────────────────────────────────────────────────────────

def _build_prompt_from_title(arabic_title: str) -> str:
    mappings = {
        "كهربائي": "electric car on open road daylight clean background",
        "موستانج": "Ford Mustang side view bright daylight",
        "فورد":    "Ford car exterior bright studio shot",
        "مرسيدس": "Mercedes-Benz luxury sedan clean white studio",
        "تويوتا":  "Toyota SUV bright daylight clean background",
        "بي ام دبليو": "BMW sports car on road bright daylight",
        "لامبورغيني": "Lamborghini supercar low angle bright studio",
        "فيراري":  "Ferrari sports car bright daylight clean",
        "بورشه":   "Porsche sports car daylight clean background",
        "نيسان":   "Nissan car clean white studio shot",
        "لكزس":    "Lexus luxury SUV bright studio shot clean",
        "هيونداي": "Hyundai car clean bright studio shot",
        "كيا":     "Kia car clean daylight road background",
        "دفع رباعي": "SUV off-road bright daylight clean",
        "هايبرد":  "hybrid car clean bright daylight road",
        "معرض":    "auto show luxury cars bright exhibition hall",
        "مقارنة":  "two luxury cars side by side bright studio",
    }
    for arabic, english in mappings.items():
        if arabic in arabic_title:
            return english
    return "luxury car exterior professional automotive photography bright daylight clean background"


def build_image_prompt(article: dict) -> str:
    base = article.get("image_prompt", "")
    title = article.get("title", "")
    if base and len(base) > 20 and all(ord(c) < 128 for c in base):
        subject = base
    else:
        subject = _build_prompt_from_title(title)
    return (
        f"{subject}, "
        f"ultra realistic, 4K, professional automotive photography, "
        f"clean bright composition, well-lit, no text, no watermark, no logo, "
        f"magazine quality"
    )


# ── main ──────────────────────────────────────────────────────────────────────

def generate() -> Path:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    article = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    TMP_DIR.mkdir(exist_ok=True)

    primary_hex = os.environ.get("BRAND_COLOR_PRIMARY", "#1A2F5A")
    accent_hex  = os.environ.get("BRAND_COLOR_ACCENT",  "#F4A300")

    prompt = build_image_prompt(article)
    encoded = urllib.parse.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={IMG_W}&height={int(IMG_H * 0.6)}&nologo=true&enhance=true&seed=42"
    )

    print(f"[image] Prompt: {prompt[:120]}...")
    response = requests.get(url, timeout=90, stream=True)
    response.raise_for_status()
    OUTPUT_FILE.write_bytes(response.content)
    size_kb = OUTPUT_FILE.stat().st_size // 1024
    print(f"[image] Base image saved — {size_kb} KB")

    title = article.get("title", "")
    if title:
        _composite_overlay(OUTPUT_FILE, title, primary_hex, accent_hex)

    return OUTPUT_FILE


def main():
    generate()


if __name__ == "__main__":
    main()
