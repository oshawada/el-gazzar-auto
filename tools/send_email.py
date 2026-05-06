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


def load_article_title() -> str:
    if ARABIC_JSON.exists():
        data = json.loads(ARABIC_JSON.read_text(encoding="utf-8"))
        return data.get("title", "مقال جديد")
    return "مقال جديد"


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

    title = load_article_title()
    sender = os.environ.get("GMAIL_USER", "me")
    date_str = datetime.now().strftime("%Y-%m-%d")

    body_text = (
        f"السلام عليكم،\n\n"
        f"نقدّم لكم أحدث تقرير في عالم السيارات:\n\n"
        f"  {title}\n\n"
        f"تجدون التقرير كاملاً في الملف المرفق.\n\n"
        f"مع تحيات فريق التحرير"
    )

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = title
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    _attach_pdf(msg, pdf_path, f"report_{date_str}.pdf")

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

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

    if count == 1:
        subject = load_article_title()
    else:
        subject = f"تقارير السيارات - {count} مقالات جديدة - {date_str}"

    body_text = (
        f"السلام عليكم،\n\n"
        f"نقدّم لكم {'أحدث تقرير' if count == 1 else f'{count} تقارير'} في عالم السيارات.\n\n"
        f"تجدون {'التقرير' if count == 1 else 'التقارير'} كاملاً في {'الملف المرفق' if count == 1 else 'الملفات المرفقة'}.\n\n"
        f"مع تحيات فريق التحرير"
    )

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    for i, pdf_path in enumerate(pdf_paths, start=1):
        filename = f"report_{date_str}_{i}.pdf" if count > 1 else f"report_{date_str}.pdf"
        _attach_pdf(msg, pdf_path, filename)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

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
