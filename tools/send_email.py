# tools/send_email.py
# Purpose: Send the generated PDF via Gmail API (OAuth2)
# Inputs:  --to <email> (or RECIPIENT_EMAIL from .env), latest .pdf from .tmp/
# Outputs: Email sent confirmation

import argparse
import base64
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
import os
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
ROOT_DIR = Path(__file__).parent.parent
TMP_DIR = ROOT_DIR / ".tmp"
ARABIC_JSON = TMP_DIR / "article_arabic.json"
TOKEN_FILE = ROOT_DIR / "token.json"
CLIENT_SECRET_FILE = ROOT_DIR / os.environ.get(
    "GOOGLE_CLIENT_SECRET_FILE",
    "client_secret_1006107233872-2d42pjqme78p5mtlahon4o4j9eg5crgc.apps.googleusercontent.com.json"
)


def get_gmail_service():
    creds = None
    if TOKEN_FILE.exists():
        # utf-8-sig strips BOM if present (common when secret was saved via PowerShell)
        token_data = json.loads(TOKEN_FILE.read_text(encoding="utf-8-sig"))
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
            print("\n[email] افتح الرابط التالي في المتصفح وامنح الصلاحيات:")
            creds = flow.run_console()
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def find_latest_pdf() -> Path:
    pdfs = sorted(TMP_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pdfs:
        raise FileNotFoundError(f"No PDF found in {TMP_DIR}")
    return pdfs[0]


def load_article_data() -> dict:
    if ARABIC_JSON.exists():
        return json.loads(ARABIC_JSON.read_text(encoding="utf-8"))
    return {}


def load_article_title() -> str:
    return load_article_data().get("title", "مقال جديد")


IMAGE_CID = "article_image_cid"
IMAGE_FILE = TMP_DIR / "article_image.jpg"

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?family=Tajawal:"
    "wght@400;500;700;900&display=swap');"
)
FONT_STACK = "'Tajawal', 'Segoe UI', Tahoma, Arial, sans-serif"


def build_article_html(data: dict, has_image: bool = False) -> str:
    """Build full article as styled HTML email — Tajawal font + embedded image."""
    primary  = "#E60000"
    dark     = "#1a1a1a"
    light_bg = "#f9f9f9"
    border_c = "#e6e6e6"

    title      = data.get("title", "")
    intro      = data.get("intro", "")
    sections   = data.get("sections", [])
    conclusion = data.get("conclusion", "")
    keywords   = data.get("seo_keywords", [])
    date_str   = datetime.now().strftime("%Y/%m/%d")

    # Image block
    img_html = ""
    if has_image:
        img_html = f"""
    <tr><td style="padding:0;line-height:0;">
      <img src="cid:{IMAGE_CID}" width="640" alt="{title}"
           style="width:100%;max-width:640px;height:auto;display:block;border:0;">
    </td></tr>"""

    # Sections
    sections_html = ""
    for s in sections:
        h = s.get("heading", "")
        b = s.get("body", "")
        sections_html += f"""
      <div style="margin-bottom:26px;">
        <h2 style="font-size:17px;font-weight:700;color:{primary};margin:0 0 9px;
                   border-right:4px solid {primary};padding-right:11px;
                   direction:rtl;text-align:right;line-height:1.5;">{h}</h2>
        <p style="font-size:15px;line-height:2;color:{dark};margin:0;
                  direction:rtl;text-align:right;">{b}</p>
      </div>"""

    # Keywords pills
    kw_html = ""
    if keywords:
        pills = "".join(
            f'<span style="display:inline-block;background:#f0f0f0;color:#555;'
            f'font-size:12px;padding:4px 11px;border-radius:20px;margin:3px 3px 0 0;'
            f'font-family:{FONT_STACK};">{k}</span>'
            for k in keywords[:8]
        )
        kw_html = f"""
      <div style="margin-top:4px;direction:rtl;text-align:right;">
        <p style="font-size:12px;color:#999;margin:0 0 7px;">الكلمات المفتاحية:</p>
        {pills}
      </div>"""

    conclusion_html = ""
    if conclusion:
        conclusion_html = f"""
    <tr><td style="padding:0 30px 22px;">
      <div style="background:{light_bg};border:1px solid {border_c};
                  border-right:4px solid {primary};border-radius:5px;padding:16px 18px;">
        <p style="font-size:12px;font-weight:700;color:{primary};margin:0 0 7px;
                  direction:rtl;text-align:right;text-transform:uppercase;">الخلاصة</p>
        <p style="font-size:15px;line-height:1.9;color:{dark};margin:0;
                  direction:rtl;text-align:right;">{conclusion}</p>
      </div>
    </td></tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
{FONT_IMPORT}
body,table,td,p,h1,h2,span {{font-family:{FONT_STACK};}}
</style>
</head>
<body style="margin:0;padding:0;background:{light_bg};
             font-family:{FONT_STACK};">

<table width="100%" cellpadding="0" cellspacing="0"
       style="background:{light_bg};padding:20px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0"
       style="max-width:640px;width:100%;background:#fff;
              border-radius:8px;overflow:hidden;
              box-shadow:0 2px 14px rgba(0,0,0,0.09);">

  <!-- Header -->
  <tr><td style="background:{primary};padding:18px 28px;text-align:center;">
    <p style="font-size:26px;font-weight:900;color:#fff;margin:0;
              font-family:{FONT_STACK};">المربع نت</p>
    <p style="font-size:12px;color:rgba(255,255,255,0.75);margin:5px 0 0;
              font-family:{FONT_STACK};">تابع أخبار السيارات لحظة بلحظة</p>
  </td></tr>

  <!-- Article image (embedded) -->
  {img_html}

  <!-- Date -->
  <tr><td style="padding:16px 30px 4px;">
    <p style="font-size:12px;color:#aaa;margin:0;
              text-align:right;direction:rtl;">{date_str}</p>
  </td></tr>

  <!-- Title -->
  <tr><td style="padding:6px 30px 18px;">
    <h1 style="font-size:21px;font-weight:900;color:{dark};margin:0;
               line-height:1.6;direction:rtl;text-align:right;
               border-bottom:3px solid {primary};padding-bottom:14px;
               font-family:{FONT_STACK};">{title}</h1>
  </td></tr>

  <!-- Intro -->
  <tr><td style="padding:0 30px 22px;">
    <p style="font-size:15px;line-height:2;color:#333;margin:0;
              direction:rtl;text-align:right;
              background:{light_bg};padding:15px 16px;border-radius:6px;
              border-right:4px solid {primary};
              font-family:{FONT_STACK};">{intro}</p>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding:0 30px 22px;">
    <hr style="border:none;border-top:1px solid {border_c};margin:0;">
  </td></tr>

  <!-- Sections -->
  <tr><td style="padding:0 30px 6px;">
    {sections_html}
  </td></tr>

  <!-- Conclusion -->
  {conclusion_html}

  <!-- Keywords -->
  <tr><td style="padding:0 30px 26px;">
    {kw_html}
  </td></tr>

  <!-- Footer -->
  <tr><td style="background:{primary};padding:18px 28px;text-align:center;">
    <p style="color:rgba(255,255,255,0.92);font-size:13px;margin:0;
              font-family:{FONT_STACK};">
      التقرير الكامل موجود في الملف المرفق (PDF)
    </p>
    <p style="color:rgba(255,255,255,0.55);font-size:11px;margin:6px 0 0;">
      almuraba.net — جميع الحقوق محفوظة
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
    return html


def _attach_pdf(msg: MIMEMultipart, pdf_path: Path, filename: str):
    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "pdf")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    part.add_header("Content-Type", f'application/pdf; name="{filename}"')
    msg.attach(part)


def send(recipient: str, pdf_path: Path = None):
    if pdf_path is None:
        pdf_path = find_latest_pdf()

    data = load_article_data()
    title = data.get("title", "مقال جديد")
    sender = os.environ.get("GMAIL_USER", "me")
    date_str = datetime.now().strftime("%Y-%m-%d")

    has_img = IMAGE_FILE.exists()
    body_html = build_article_html(data, has_image=has_img)

    # multipart/mixed  →  multipart/related  →  multipart/alternative + image
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body_html, "html", "utf-8"))

    related = MIMEMultipart("related")
    related.attach(alt)
    if has_img:
        with open(IMAGE_FILE, "rb") as f:
            img_part = MIMEImage(f.read(), _subtype="jpeg")
        img_part.add_header("Content-ID", f"<{IMAGE_CID}>")
        img_part.add_header("Content-Disposition", "inline", filename="article_image.jpg")
        related.attach(img_part)

    outer = MIMEMultipart("mixed")
    outer["From"] = sender
    outer["To"] = recipient
    outer["Subject"] = title
    outer.attach(related)
    _attach_pdf(outer, pdf_path, f"report_{date_str}.pdf")

    raw = base64.urlsafe_b64encode(outer.as_bytes()).decode("utf-8")

    print("[email] Authenticating with Gmail API...")
    service = get_gmail_service()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[email] Sent to {recipient} at {timestamp}")
    print(f"[email] PDF: {pdf_path.name}")


def send_batch(recipient: str, pdf_paths: list[Path]):
    """Send one email with multiple PDFs attached."""
    sender = os.environ.get("GMAIL_USER", "me")
    date_str = datetime.now().strftime("%Y-%m-%d")
    count = len(pdf_paths)

    data = load_article_data()
    subject = data.get("title", load_article_title()) if count == 1 \
              else f"تقارير السيارات — {count} مقالات جديدة — {date_str}"

    has_img = IMAGE_FILE.exists()
    body_html = build_article_html(data, has_image=has_img)

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body_html, "html", "utf-8"))

    related = MIMEMultipart("related")
    related.attach(alt)
    if has_img:
        with open(IMAGE_FILE, "rb") as f:
            img_part = MIMEImage(f.read(), _subtype="jpeg")
        img_part.add_header("Content-ID", f"<{IMAGE_CID}>")
        img_part.add_header("Content-Disposition", "inline", filename="article_image.jpg")
        related.attach(img_part)

    outer = MIMEMultipart("mixed")
    outer["From"] = sender
    outer["To"] = recipient
    outer["Subject"] = subject
    outer.attach(related)

    for i, pdf_path in enumerate(pdf_paths, start=1):
        filename = f"report_{date_str}_{i}.pdf" if count > 1 else f"report_{date_str}.pdf"
        _attach_pdf(outer, pdf_path, filename)

    raw = base64.urlsafe_b64encode(outer.as_bytes()).decode("utf-8")

    print("[email] Authenticating with Gmail API...")
    service = get_gmail_service()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[email] Batch sent to {recipient} at {timestamp} — {count} PDF(s) attached")


def main():
    parser = argparse.ArgumentParser(description="Send PDF via Gmail API")
    parser.add_argument(
        "--to",
        default=os.environ.get("RECIPIENT_EMAIL", ""),
        help="Comma-separated recipient email addresses"
    )
    parser.add_argument(
        "--batch",
        default="",
        help="Comma-separated PDF file paths for batch send"
    )
    args = parser.parse_args()

    if not args.to:
        raise ValueError("Recipient email required — use --to or set RECIPIENT_EMAIL in .env")

    recipients = [r.strip() for r in args.to.split(",") if r.strip()]

    if args.batch:
        pdf_paths = [Path(p.strip()) for p in args.batch.split(",") if p.strip()]
        for recipient in recipients:
            send_batch(recipient, pdf_paths)
    else:
        for recipient in recipients:
            send(recipient)


if __name__ == "__main__":
    main()
