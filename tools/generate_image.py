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

IMG_W, IMG_H = 1280, 720   # 16:9 HD — matches almuraba.net reference images


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
    almuraba.net-style frame — NO article text:
      ┌──── red border (20px top/sides, 0 bottom) ───────────────────────┐
      │  ┌──────────────────────────────────────────────────────────┐    │
      │  │  car photo              [logo badge — top right corner]  │    │
      │  └──────────────────────────────────────────────────────────┘    │
      │  ┌── red bottom bar (72px) ───────────────────────────────── ┐   │
      │  │           tagline text centered (white)                    │   │
      │  └────────────────────────────────────────────────────────────┘   │
      └───────────────────────────────────────────────────────────────────┘
    Logo: placed as badge inside photo — top-right corner, white rounded bg
    """
    import arabic_reshaper
    from bidi.algorithm import get_display
    from PIL import Image, ImageDraw

    pr, pg, pb = _hex_to_rgb(primary_hex)
    RED  = (pr, pg, pb, 255)

    border  = 20    # red frame on top + left + right
    bot_bar = 72    # red bottom bar height

    photo_w = IMG_W - border * 2
    photo_h = IMG_H - border - bot_bar   # top border only (bottom bar replaces bottom border)

    # ── Load + cover-crop car photo ───────────────────────────────────────────
    car = Image.open(img_path).convert("RGBA")
    cw, ch = car.size
    scale = max(photo_w / cw, photo_h / ch)
    nw, nh = int(cw * scale), int(ch * scale)
    car = car.resize((nw, nh), Image.LANCZOS)
    cx = (nw - photo_w) // 2
    cy = (nh - photo_h) // 2
    car = car.crop((cx, cy, cx + photo_w, cy + photo_h))

    # ── Canvas — full red base ────────────────────────────────────────────────
    canvas = Image.new("RGBA", (IMG_W, IMG_H), RED)
    canvas.paste(car, (border, border), car)
    draw = ImageDraw.Draw(canvas)

    # Bottom bar (already red from canvas, just re-affirm)
    bot_y = border + photo_h
    draw.rectangle([(0, bot_y), (IMG_W, IMG_H)], fill=RED)

    # ── Logo badge — top-right INSIDE the photo area ──────────────────────────
    logo_path = _find_logo()
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")

            # Scale logo to a nice badge size
            badge_w = int(IMG_W * 0.18)          # ~230px wide
            r       = badge_w / logo.width
            badge_h = int(logo.height * r)

            logo_resized = logo.resize((badge_w, badge_h), Image.LANCZOS)

            # White rounded rectangle behind logo
            pad_x, pad_y = 10, 8
            pill_w = badge_w + pad_x * 2
            pill_h = badge_h + pad_y * 2
            margin = 14
            pill_x = border + photo_w - pill_w - margin   # right-aligned in photo
            pill_y = border + margin                        # top-aligned in photo

            draw.rounded_rectangle(
                [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                radius=10,
                fill=(255, 255, 255, 245),
            )
            canvas.paste(logo_resized, (pill_x + pad_x, pill_y + pad_y), logo_resized)

        except Exception as e:
            print(f"[image] Logo badge skipped: {e}")

    # ── Bottom bar: tagline centred in white text ─────────────────────────────
    tagline   = "تابع أخبار السيارات  |  لحظة بلحظة"
    font_size = max(18, bot_bar // 3)
    font      = _find_font_pil(font_size, bold=False)
    shaped    = get_display(arabic_reshaper.reshape(tagline))
    draw.text((IMG_W // 2, bot_y + bot_bar // 2), shaped,
              font=font, fill=(255, 255, 255, 230), anchor="mm")

    canvas.convert("RGB").save(img_path, "JPEG", quality=95, optimize=True)
    print(f"[image] Branded frame — {IMG_W}×{IMG_H}px, logo badge top-right")


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

    article = json.loads(INPUT_FILE.read_text(encoding="utf-8-sig"))
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
