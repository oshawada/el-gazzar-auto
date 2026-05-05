# tools/generate_pdf.py
# Purpose: Generate branded Arabic RTL PDF from rewritten article
# Inputs:  .tmp/article_arabic.json
# Outputs: .tmp/article_<slug>_<YYYYMMDD>.pdf

import json
import os
import re
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from pathlib import Path

from arabic_reshaper import reshape
from bidi.algorithm import get_display
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

load_dotenv()

TMP_DIR = Path(__file__).parent.parent / ".tmp"
ROOT_DIR = Path(__file__).parent.parent
INPUT_FILE = TMP_DIR / "article_arabic.json"


def _resolve_font(env_var: str, candidates: list) -> str:
    override = os.environ.get(env_var, "")
    if override and Path(override).exists():
        return override
    for p in candidates:
        if Path(p).exists():
            return str(p)
    raise FileNotFoundError(
        f"Arabic font not found. Set {env_var} in .env or copy the font to assets/fonts/.\n"
        f"Searched: {candidates}"
    )


FONT_PATH = _resolve_font("ARABIC_FONT_PATH", [
    ROOT_DIR / "assets" / "fonts" / "tahoma.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Tahoma.ttf",
])

FONT_BOLD_PATH = _resolve_font("ARABIC_FONT_BOLD_PATH", [
    ROOT_DIR / "assets" / "fonts" / "tahomabd.ttf",
    "C:/Windows/Fonts/tahomabd.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Tahoma_Bold.ttf",
])

# Brand colors (from .env or defaults)
COLOR_PRIMARY_HEX = os.environ.get("BRAND_COLOR_PRIMARY", "#1A2F5A")
COLOR_ACCENT_HEX = os.environ.get("BRAND_COLOR_ACCENT", "#F4A300")
LOGO_PATH = os.environ.get("LOGO_PATH", "assets/logo.png")


def hex_to_rgb(hex_color: str) -> colors.Color:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    return colors.Color(r, g, b)


def ar(text: str) -> str:
    """Reshape and apply BiDi to Arabic text for correct RTL rendering."""
    if not text:
        return ""
    return get_display(reshape(str(text)))


def slug(title: str) -> str:
    """Create a safe filename slug from the title."""
    clean = re.sub(r"[^\w\s]", "", title, flags=re.UNICODE)
    words = clean.split()[:5]
    return "_".join(words) if words else "article"


def register_fonts():
    pdfmetrics.registerFont(TTFont("Tahoma", FONT_PATH))
    if Path(FONT_BOLD_PATH).exists():
        pdfmetrics.registerFont(TTFont("Tahoma-Bold", FONT_BOLD_PATH))
    else:
        pdfmetrics.registerFont(TTFont("Tahoma-Bold", FONT_PATH))


def build_styles() -> dict:
    primary = hex_to_rgb(COLOR_PRIMARY_HEX)
    accent = hex_to_rgb(COLOR_ACCENT_HEX)

    return {
        "title": ParagraphStyle(
            "ArabicTitle",
            fontName="Tahoma-Bold",
            fontSize=22,
            textColor=primary,
            alignment=TA_RIGHT,
            spaceAfter=8,
            leading=30,
        ),
        "meta": ParagraphStyle(
            "ArabicMeta",
            fontName="Tahoma",
            fontSize=9,
            textColor=colors.Color(0.5, 0.5, 0.5),
            alignment=TA_RIGHT,
            spaceAfter=12,
            leading=14,
        ),
        "intro": ParagraphStyle(
            "ArabicIntro",
            fontName="Tahoma-Bold",
            fontSize=12,
            textColor=primary,
            alignment=TA_RIGHT,
            spaceAfter=10,
            leading=20,
        ),
        "heading": ParagraphStyle(
            "ArabicHeading",
            fontName="Tahoma-Bold",
            fontSize=14,
            textColor=primary,
            alignment=TA_RIGHT,
            spaceBefore=14,
            spaceAfter=6,
            leading=20,
        ),
        "body": ParagraphStyle(
            "ArabicBody",
            fontName="Tahoma",
            fontSize=11,
            textColor=colors.black,
            alignment=TA_RIGHT,
            spaceAfter=8,
            leading=20,
        ),
        "conclusion": ParagraphStyle(
            "ArabicConclusion",
            fontName="Tahoma",
            fontSize=11,
            textColor=primary,
            alignment=TA_RIGHT,
            spaceAfter=8,
            leading=20,
        ),
        "footer": ParagraphStyle(
            "ArabicFooter",
            fontName="Tahoma",
            fontSize=8,
            textColor=colors.Color(0.6, 0.6, 0.6),
            alignment=TA_RIGHT,
            leading=12,
        ),
    }


def generate(output_path: Path = None) -> Path:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    article = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    TMP_DIR.mkdir(exist_ok=True)

    if output_path is None:
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"article_{slug(article.get('title', 'article'))}_{date_str}.pdf"
        output_path = TMP_DIR / filename

    register_fonts()
    styles = build_styles()
    primary = hex_to_rgb(COLOR_PRIMARY_HEX)
    accent = hex_to_rgb(COLOR_ACCENT_HEX)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=article.get("title", ""),
    )

    story = []

    # Logo
    logo_path = Path(LOGO_PATH)
    if logo_path.exists():
        try:
            img = Image(str(logo_path), width=5 * cm, height=2 * cm, kind="proportional")
            img.hAlign = "RIGHT"
            story.append(img)
            story.append(Spacer(1, 0.3 * cm))
        except Exception as e:
            print(f"[pdf] Logo load failed: {e} — skipping")

    # Top accent line
    story.append(HRFlowable(width="100%", thickness=3, color=accent, spaceAfter=12))

    # Title
    story.append(Paragraph(ar(article.get("title", "")), styles["title"]))

    # Meta description
    meta = article.get("meta_description", "")
    if meta:
        story.append(Paragraph(ar(meta), styles["meta"]))

    # Divider
    story.append(HRFlowable(width="100%", thickness=1, color=primary, spaceAfter=10))

    # Article Image (if exists)
    article_image = TMP_DIR / "article_image.jpg"
    if article_image.exists():
        try:
            page_width = A4[0] - 4 * cm  # عرض الصفحة ناقص الهوامش
            img = Image(str(article_image), width=page_width, height=page_width * 0.45, kind="proportional")
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 0.4 * cm))
        except Exception as e:
            print(f"[pdf] Article image load failed: {e} — skipping")

    # Intro
    intro = article.get("intro", "")
    if intro:
        story.append(Paragraph(ar(intro), styles["intro"]))
        story.append(Spacer(1, 0.5 * cm))

    # Sections
    for section in article.get("sections", []):
        heading = section.get("heading", "")
        body = section.get("body", "")
        if heading:
            story.append(Paragraph(ar(heading), styles["heading"]))
        if body:
            story.append(Paragraph(ar(body), styles["body"]))

    # Conclusion
    conclusion = article.get("conclusion", "")
    if conclusion:
        story.append(HRFlowable(width="100%", thickness=1, color=accent, spaceBefore=12, spaceAfter=10))
        story.append(Paragraph(ar(conclusion), styles["conclusion"]))

    # SEO keywords footer
    keywords = article.get("seo_keywords", [])
    if keywords:
        story.append(Spacer(1, 0.8 * cm))
        kw_text = ar("الكلمات المفتاحية: ") + " | ".join(ar(k) for k in keywords)
        story.append(Paragraph(kw_text, styles["footer"]))

    # Date footer
    date_text = ar(f"تاريخ الإنشاء: {datetime.now().strftime('%Y-%m-%d')}")
    story.append(Paragraph(date_text, styles["footer"]))

    doc.build(story)
    print(f"[pdf] Generated → {output_path}")
    # Print path for orchestrator to pick up
    print(f"OUTPUT_PDF={output_path}")
    return output_path


def main():
    generate()


if __name__ == "__main__":
    main()
