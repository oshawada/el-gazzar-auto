# tools/generate_image.py
# Purpose: Generate article image (Pollinations.ai) then composite brand overlay
#          matching almuraba.net visual style: car photo + title + logo + brand colors
# Inputs:  .tmp/article_arabic.json (reads image_prompt + title)
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

FALLBACK_PROMPT = "luxury car on open road, professional automotive photography, magazine cover style"

IMG_W, IMG_H = 1200, 630  # 16:9 social media size


# ── helpers ────────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hex_to_color_name(hex_color: str) -> str:
    h = hex_color.lstrip("#").upper()
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return "deep blue"
    if r < 80 and b > r and b > g:
        return "deep navy blue"
    elif r < 100 and g < 140 and b > 100:
        return "dark teal blue"
    elif r > 200 and g > 150 and b < 80:
        return "golden amber"
    elif r > 200 and g > 200 and b < 100:
        return "bright yellow gold"
    elif r > 150 and g < 80 and b < 80:
        return "deep red"
    elif r > 180 and g > 180 and b > 180:
        return "silver white"
    elif r < 50 and g < 50 and b < 50:
        return "matte black"
    else:
        return f"rgb({r},{g},{b}) color"


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


def _find_font(size: int):
    """Return PIL ImageFont for Arabic text."""
    from PIL import ImageFont
    candidates = [
        ROOT_DIR / "assets" / "fonts" / "tahomabd.ttf",
        ROOT_DIR / "assets" / "fonts" / "tahoma.ttf",
        "C:/Windows/Fonts/tahomabd.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Tahoma_Bold.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Tahoma.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(str(p), size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_arabic(text: str, font, max_width: int, draw) -> list[str]:
    """Split Arabic title into display lines that fit max_width."""
    import arabic_reshaper
    from bidi.algorithm import get_display

    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        shaped = get_display(arabic_reshaper.reshape(test))
        try:
            w = draw.textlength(shaped, font=font)
        except AttributeError:
            w = draw.textsize(shaped, font=font)[0]
        if w > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines[:3]  # max 3 lines


def _composite_overlay(img_path: Path, title: str, primary_hex: str, accent_hex: str) -> None:
    """Overlay brand elements on the generated car image (almuraba.net style)."""
    from PIL import Image, ImageDraw

    img = Image.open(img_path).convert("RGBA")
    W, H = img.size

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    # Dark gradient at bottom 55% — makes title text readable
    grad_start = int(H * 0.45)
    for y in range(grad_start, H):
        progress = (y - grad_start) / (H - grad_start)
        alpha = int(220 * (progress ** 1.4))
        draw_ov.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Primary color top bar
    pr, pg, pb = _hex_to_rgb(primary_hex)
    top_bar_h = max(14, H // 45)
    draw.rectangle([(0, 0), (W, top_bar_h)], fill=(pr, pg, pb, 255))

    # Accent stripe below top bar
    ar, ag, ab = _hex_to_rgb(accent_hex)
    accent_h = max(5, H // 120)
    draw.rectangle([(0, top_bar_h), (W, top_bar_h + accent_h)], fill=(ar, ag, ab, 255))

    # Logo in top-right corner
    logo_path = _find_logo()
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo_target_w = max(120, W // 8)
            ratio = logo_target_w / logo.width
            logo_target_h = int(logo.height * ratio)
            logo = logo.resize((logo_target_w, logo_target_h), Image.LANCZOS)
            margin = 12
            lx = W - logo_target_w - margin
            ly = top_bar_h + accent_h + margin
            img.paste(logo, (lx, ly), logo)
            draw = ImageDraw.Draw(img)
        except Exception as e:
            print(f"[image] Logo paste skipped: {e}")

    # Arabic title text at bottom
    import arabic_reshaper
    from bidi.algorithm import get_display

    font_size = max(44, W // 17)
    font = _find_font(font_size)
    margin_x = int(W * 0.05)
    max_text_w = W - margin_x * 2

    lines = _wrap_arabic(title, font, max_text_w, draw)
    line_height = int(font_size * 1.35)
    total_text_h = len(lines) * line_height
    text_block_bottom = H - int(H * 0.06)
    text_block_top = text_block_bottom - total_text_h

    for i, line in enumerate(lines):
        shaped = get_display(arabic_reshaper.reshape(line))
        y = text_block_top + i * line_height + line_height // 2
        # Shadow pass
        for dx, dy in [(2, 2), (-2, 2), (2, -2), (-2, -2)]:
            draw.text((W // 2 + dx, y + dy), shaped, font=font,
                      fill=(0, 0, 0, 200), anchor="mm")
        # White text
        draw.text((W // 2, y), shaped, font=font,
                  fill=(255, 255, 255, 255), anchor="mm")

    # Thin accent bar at very bottom
    bar_h = max(6, H // 100)
    draw.rectangle([(0, H - bar_h), (W, H)], fill=(ar, ag, ab, 255))

    img.convert("RGB").save(img_path, "JPEG", quality=92, optimize=True)
    print(f"[image] Composite overlay applied — {W}×{H}px")


# ── image generation ──────────────────────────────────────────────────────────

def _build_prompt_from_title(arabic_title: str) -> str:
    mappings = {
        "كهربائي": "electric car charging at night futuristic",
        "سباق":    "racing car on track motion blur",
        "فورد":    "Ford car exterior side profile",
        "موستانج": "Ford Mustang muscle car dynamic angle",
        "مرسيدس": "Mercedes-Benz luxury sedan front view",
        "تويوتا":  "Toyota SUV on mountain road",
        "بي ام دبليو": "BMW sports car on empty road",
        "لامبورغيني": "Lamborghini supercar low angle dramatic",
        "فيراري":  "Ferrari sports car on road",
        "بورشه":   "Porsche sports car dynamic",
        "نيسان":   "Nissan car sleek modern design",
        "لكزس":    "Lexus luxury SUV studio shot",
        "معرض":    "international auto show luxury cars exhibition hall",
        "دفع رباعي": "SUV off-road adventure rugged terrain",
        "هايبرد":  "hybrid car eco friendly road",
        "مقارنة":  "two luxury cars side by side comparison",
    }
    for arabic, english in mappings.items():
        if arabic in arabic_title:
            return english
    return FALLBACK_PROMPT


def build_image_prompt(article: dict, color_style: str) -> str:
    base = article.get("image_prompt", "")
    title = article.get("title", "")

    if base and len(base) > 20 and all(ord(c) < 128 for c in base):
        subject = base
    else:
        subject = _build_prompt_from_title(title)

    return (
        f"{subject}, "
        f"{color_style}, "
        f"ultra realistic, 4K, professional automotive magazine photography, "
        f"cinematic lighting, clean composition, no text, no watermark"
    )


def generate() -> Path:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    article = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    TMP_DIR.mkdir(exist_ok=True)

    primary_hex = os.environ.get("BRAND_COLOR_PRIMARY", "#1A2F5A")
    accent_hex  = os.environ.get("BRAND_COLOR_ACCENT",  "#F4A300")
    primary_name = hex_to_color_name(primary_hex)
    accent_name  = hex_to_color_name(accent_hex)
    color_style = (
        f"dramatic {primary_name} background with {accent_name} accent lighting, "
        f"brand color palette"
    )

    prompt = build_image_prompt(article, color_style)
    encoded = urllib.parse.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={IMG_W}&height={IMG_H}&nologo=true&enhance=true&seed=42"
    )

    print(f"[image] Brand colors: {primary_name} + {accent_name}")
    print(f"[image] Prompt: {prompt[:120]}...")

    response = requests.get(url, timeout=90, stream=True)
    response.raise_for_status()
    OUTPUT_FILE.write_bytes(response.content)
    size_kb = OUTPUT_FILE.stat().st_size // 1024
    print(f"[image] Base image saved → {OUTPUT_FILE} ({size_kb} KB)")

    # Apply almuraba.net-style overlay: gradient + title + logo + brand bars
    title = article.get("title", "")
    if title:
        _composite_overlay(OUTPUT_FILE, title, primary_hex, accent_hex)

    return OUTPUT_FILE


def main():
    generate()


if __name__ == "__main__":
    main()
