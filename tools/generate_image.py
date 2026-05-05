# tools/generate_image.py
# Purpose: Generate article-related image using Pollinations.ai (free, no API key)
# Inputs:  .tmp/article_arabic.json (reads image_prompt field)
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

TMP_DIR = Path(__file__).parent.parent / ".tmp"
INPUT_FILE = TMP_DIR / "article_arabic.json"
OUTPUT_FILE = TMP_DIR / "article_image.jpg"

FALLBACK_PROMPT = "luxury car on open road, professional automotive photography, magazine cover style"


def hex_to_color_name(hex_color: str) -> str:
    """تحويل HEX إلى وصف لوني إنجليزي يفهمه نموذج توليد الصور."""
    hex_color = hex_color.lstrip("#").upper()
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except Exception:
        return "deep blue"

    # تصنيف اللون بناءً على قيم RGB
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
    elif r > 100 and g < 60 and b > 100:
        return "rich purple"
    else:
        return f"rgb({r},{g},{b}) color"


def build_color_style(primary_hex: str, accent_hex: str) -> str:
    """بناء وصف الألوان للـ prompt."""
    primary_name = hex_to_color_name(primary_hex)
    accent_name = hex_to_color_name(accent_hex)
    return (
        f"color scheme: {primary_name} and {accent_name}, "
        f"dramatic {primary_name} background with {accent_name} accent lighting, "
        f"brand color palette"
    )


def build_prompt(article: dict, color_style: str) -> str:
    base = article.get("image_prompt", "")
    title = article.get("title", "")

    if base and len(base) > 20 and all(ord(c) < 128 for c in base):
        subject = base
    else:
        subject = _build_prompt_from_title(title)

    prompt = (
        f"{subject}, "
        f"{color_style}, "
        f"ultra realistic, 4K, professional automotive magazine photography, "
        f"cinematic lighting, no text, no watermark, no logo"
    )
    return prompt


def _build_prompt_from_title(arabic_title: str) -> str:
    mappings = {
        "كهربائي": "electric car charging at night futuristic",
        "سباق":    "racing car on track motion blur",
        "فورد":    "classic Ford muscle car side view",
        "موستانج": "Ford Mustang classic muscle car",
        "مرسيدس": "Mercedes-Benz luxury sedan front view",
        "تويوتا":  "Toyota SUV on mountain road",
        "بي ام دبليو": "BMW sports car on empty road",
        "لامبورغيني": "Lamborghini supercar low angle",
        "فيراري":  "Ferrari sports car on road",
        "بورشه":   "Porsche sports car dynamic",
        "نيسان":   "Nissan car sleek modern design",
        "معرض":    "international auto show luxury cars exhibition",
        "دفع رباعي": "SUV off-road adventure rugged terrain",
        "هايبرد":  "hybrid car eco friendly green energy road",
        "مقارنة":  "two luxury cars side by side comparison studio",
        "حريق":    "dramatic car event scene cinematic",
        "تاريخ":   "vintage classic car museum display",
    }
    for arabic, english in mappings.items():
        if arabic in arabic_title:
            return english
    return FALLBACK_PROMPT


def generate() -> Path:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    article = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    TMP_DIR.mkdir(exist_ok=True)

    primary_hex = os.environ.get("BRAND_COLOR_PRIMARY", "#1A2F5A")
    accent_hex  = os.environ.get("BRAND_COLOR_ACCENT",  "#F4A300")
    color_style = build_color_style(primary_hex, accent_hex)

    prompt = build_prompt(article, color_style)
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=630&nologo=true&enhance=true&seed=42"

    primary_name = hex_to_color_name(primary_hex)
    accent_name  = hex_to_color_name(accent_hex)
    print(f"[image] Brand colors: {primary_name} + {accent_name}")
    print(f"[image] Prompt: {prompt[:100]}...")

    response = requests.get(url, timeout=90, stream=True)
    response.raise_for_status()

    OUTPUT_FILE.write_bytes(response.content)
    size_kb = OUTPUT_FILE.stat().st_size // 1024
    print(f"[image] Saved -> {OUTPUT_FILE} ({size_kb} KB)")
    return OUTPUT_FILE


def main():
    generate()


if __name__ == "__main__":
    main()
