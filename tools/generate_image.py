# tools/generate_image.py
# Purpose: Generate branded car image — NO text on image, logo badge only
#          Style: clean car photo + thin brand bar top + gradient bottom + logo badge
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


def _find_font_pil(size: int, bold: bool = True):
    from PIL import ImageFont
    candidates = (
        [ROOT_DIR / "assets" / "fonts" / "tahomabd.ttf",
         "C:/Windows/Fonts/tahomabd.ttf",
         "/usr/share/fonts/truetype/msttcorefonts/Tahoma_Bold.ttf",
         ROOT_DIR / "assets" / "fonts" / "tahoma.ttf",
         "C:/Windows/Fonts/tahoma.ttf"]
        if bold else
        [ROOT_DIR / "assets" / "fonts" / "tahoma.ttf",
         "C:/Windows/Fonts/tahoma.ttf",
         "/usr/share/fonts/truetype/msttcorefonts/Tahoma.ttf"]
    )
    for p in candidates:
        try:
            return ImageFont.truetype(str(p), size)
        except Exception:
            continue
    return ImageFont.load_default()


def _composite_overlay(img_path: Path, primary_hex: str, accent_hex: str) -> None:
    """
    Apply almuraba.net-style branded frame — NO article text on image:
      ┌──── red border (18px all sides) ────┐
      │  ┌──────────────────────────────┐   │
      │  │      clean car photo         │   │
      │  └──────────────────────────────┘   │
      │  ┌── red bottom bar (~68px) ────┐   │
      │  │ tagline (left) | logo (right)│   │
      │  └──────────────────────────────┘   │
      └──────────────────────────────────────┘
    """
    import arabic_reshaper
    from bidi.algorithm import get_display
    from PIL import Image, ImageDraw

    pr, pg, pb = _hex_to_rgb(primary_hex)
    RED = (pr, pg, pb, 255)

    border   = 18                      # red frame thickness (all sides)
    bot_bar  = 68                      # bottom bar height (inside frame)

    # Photo area dimensions
    photo_w = IMG_W - border * 2
    photo_h = IMG_H - border * 2 - bot_bar

    # Load + cover-crop car photo to photo_w × photo_h
    car = Image.open(img_path).convert("RGBA")
    cw, ch = car.size
    scale  = max(photo_w / cw, photo_h / ch)
    nw, nh = int(cw * scale), int(ch * scale)
    car    = car.resize((nw, nh), Image.LANCZOS)
    cx     = (nw - photo_w) // 2
    cy     = (nh - photo_h) // 2
    car    = car.crop((cx, cy, cx + photo_w, cy + photo_h))

    # Build canvas (all red initially)
    canvas = Image.new("RGBA", (IMG_W, IMG_H), RED)

    # Paste car photo in correct position
    canvas.paste(car, (border, border), car)

    # Paint bottom bar (red — already covered by canvas)
    draw = ImageDraw.Draw(canvas)
    bot_y = border + photo_h
    draw.rectangle([(border, bot_y), (IMG_W - border, IMG_H - border)], fill=RED)

    # ── Logo (right side of bottom bar) ──────────────────────────────────────
    logo_path = _find_logo()
    logo_placed = False
    logo_right_edge = IMG_W - border   # for tagline positioning
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            pad = 10
            max_logo_h = bot_bar - pad * 2
            max_logo_w = int(IMG_W * 0.22)
            r = min(max_logo_h / logo.height, max_logo_w / logo.width)
            lw = int(logo.width * r)
            lh = int(logo.height * r)
            logo = logo.resize((lw, lh), Image.LANCZOS)
            lx = IMG_W - border - lw - 14
            ly = bot_y + (bot_bar - lh) // 2
            canvas.paste(logo, (lx, ly), logo)
            logo_right_edge = lx - 12
            logo_placed = True
        except Exception as e:
            print(f"[image] Logo skipped: {e}")

    # ── Tagline (left side of bottom bar, Arabic) ─────────────────────────────
    tagline     = "تابع أخبار السيارات | لحظة بلحظة"
    font_size   = max(16, bot_bar // 3)
    font        = _find_font_pil(font_size, bold=False)
    shaped      = get_display(arabic_reshaper.reshape(tagline))
    tag_y       = bot_y + bot_bar // 2
    tag_x_right = logo_right_edge - 10   # tagline starts from logo's left edge going right→left

    # Draw white tagline text (RTL so anchor right side)
    draw.text((tag_x_right, tag_y), shaped, font=font,
              fill=(255, 255, 255, 220), anchor="rm")

    canvas.convert("RGB").save(img_path, "JPEG", quality=93, optimize=True)
    print(f"[image] Branded frame applied — {IMG_W}×{IMG_H}px (no article text)")


# ── prompt building ────────────────────────────────────────────────────────────

def _subject_from_title(arabic_title: str) -> str:
    mappings = {
        "كهربائي":      "electric car on open road dramatic cinematic lighting",
        "موستانج":      "Ford Mustang side view dramatic lighting",
        "فورد":         "Ford car exterior dynamic angle dramatic lighting",
        "مرسيدس":       "Mercedes-Benz luxury sedan dramatic studio lighting",
        "تويوتا":       "Toyota SUV on road dramatic golden hour lighting",
        "بي ام دبليو":  "BMW sports car dynamic lighting dramatic angle",
        "لامبورغيني":   "Lamborghini supercar low angle dramatic lighting",
        "فيراري":       "Ferrari sports car dramatic red lighting",
        "بورشه":        "Porsche sports car dramatic cinematic",
        "نيسان":        "Nissan car dramatic studio lighting",
        "لكزس":         "Lexus luxury SUV dramatic studio cinematic",
        "هيونداي":      "Hyundai car dramatic lighting studio",
        "كيا":          "Kia car dramatic cinematic road",
        "دفع رباعي":    "SUV off-road dramatic sunset lighting",
        "هايبرد":       "hybrid car dramatic cinematic road lighting",
        "معرض":         "luxury cars auto show dramatic hall lighting",
        "مقارنة":       "two luxury cars side by side dramatic studio",
    }
    for arabic, english in mappings.items():
        if arabic in arabic_title:
            return english
    return "luxury sports car dramatic cinematic lighting automotive photography"


def build_prompt(article: dict) -> str:
    base = article.get("image_prompt", "")
    title = article.get("title", "")
    subject = base if (base and len(base) > 20 and all(ord(c) < 128 for c in base)) \
              else _subject_from_title(title)
    return (
        f"{subject}, "
        f"ultra realistic 4K, professional automotive magazine photography, "
        f"dramatic cinematic lighting, sharp details, no text, no watermark, no logo, "
        f"clean composition, high contrast"
    )


# ── main ──────────────────────────────────────────────────────────────────────

def generate() -> Path:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    article = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    TMP_DIR.mkdir(exist_ok=True)

    primary_hex = os.environ.get("BRAND_COLOR_PRIMARY", "#E60000")
    accent_hex  = os.environ.get("BRAND_COLOR_ACCENT",  "#FFFFFF")

    prompt = build_prompt(article)
    encoded = urllib.parse.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={IMG_W}&height={IMG_H}&nologo=true&enhance=true&seed=42"
    )

    print(f"[image] Prompt: {prompt[:120]}...")
    response = requests.get(url, timeout=90, stream=True)
    response.raise_for_status()
    OUTPUT_FILE.write_bytes(response.content)
    print(f"[image] Base image saved — {OUTPUT_FILE.stat().st_size // 1024} KB")

    _composite_overlay(OUTPUT_FILE, primary_hex, accent_hex)
    return OUTPUT_FILE


def main():
    generate()


if __name__ == "__main__":
    main()
