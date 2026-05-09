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


def _composite_overlay(img_path: Path, primary_hex: str, accent_hex: str) -> None:
    """
    Apply clean branded overlay — NO text on image:
      - Thin primary-color bar at very top
      - Car photo fills the frame
      - Soft gradient at bottom (~35% height) fading to primary color
      - Logo badge centered inside the gradient zone (with white pill background)
    """
    from PIL import Image, ImageDraw, ImageFilter

    pr, pg, pb = _hex_to_rgb(primary_hex)

    # Load and resize car photo to fill canvas
    car = Image.open(img_path).convert("RGBA")
    cw, ch = car.size
    # Scale to fill IMG_W x IMG_H (cover-fit, center-crop)
    scale = max(IMG_W / cw, IMG_H / ch)
    new_w, new_h = int(cw * scale), int(ch * scale)
    car = car.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - IMG_W) // 2
    top  = (new_h - IMG_H) // 2
    car  = car.crop((left, top, left + IMG_W, top + IMG_H))

    canvas = Image.new("RGBA", (IMG_W, IMG_H))
    canvas.paste(car, (0, 0))

    draw = ImageDraw.Draw(canvas)

    # ── Top brand bar (thin, clean) ───────────────────────────────────────────
    top_bar_h = max(10, IMG_H // 55)
    draw.rectangle([(0, 0), (IMG_W, top_bar_h)], fill=(pr, pg, pb, 255))

    # ── Bottom gradient: transparent → primary color ───────────────────────────
    grad_zone_h = int(IMG_H * 0.40)
    grad_start  = IMG_H - grad_zone_h
    overlay = Image.new("RGBA", (IMG_W, IMG_H), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    for y in range(grad_start, IMG_H):
        progress = (y - grad_start) / grad_zone_h
        # Ease-in curve: slow start, strong end
        alpha = int(230 * (progress ** 1.6))
        ov_draw.line([(0, y), (IMG_W, y)], fill=(pr, pg, pb, alpha))
    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)

    # ── Logo badge centered in gradient zone ──────────────────────────────────
    logo_path = _find_logo()
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")

            # Target logo size: proportional to canvas
            logo_target_w = int(IMG_W * 0.22)   # ~264px
            ratio = logo_target_w / logo.width
            logo_target_h = int(logo.height * ratio)
            logo = logo.resize((logo_target_w, logo_target_h), Image.LANCZOS)

            # White rounded-rectangle pill behind logo (for contrast)
            pad_x, pad_y = 18, 12
            pill_w = logo_target_w + pad_x * 2
            pill_h = logo_target_h + pad_y * 2
            pill_x = (IMG_W - pill_w) // 2
            pill_y = IMG_H - logo_target_h - pad_y * 2 - int(IMG_H * 0.035)

            radius = min(pill_h // 3, 20)
            # Draw white pill
            draw.rounded_rectangle(
                [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                radius=radius,
                fill=(255, 255, 255, 240),
            )

            # Paste logo centered on pill
            lx = pill_x + pad_x
            ly = pill_y + pad_y
            canvas.paste(logo, (lx, ly), logo)

        except Exception as e:
            print(f"[image] Logo skipped: {e}")

    canvas.convert("RGB").save(img_path, "JPEG", quality=93, optimize=True)
    print(f"[image] Branded image saved — {IMG_W}×{IMG_H}px (no text)")


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
