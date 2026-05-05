# tools/auth_gmail.py
# Purpose: One-time Gmail OAuth2 authorization
# Saves auth URL to auth_url.txt then waits for browser callback on port 8080

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
ROOT_DIR = Path(__file__).parent.parent
CLIENT_SECRET_FILE = ROOT_DIR / os.environ.get(
    "GOOGLE_CLIENT_SECRET_FILE",
    "client_secret_1006107233872-2d42pjqme78p5mtlahon4o4j9eg5crgc.apps.googleusercontent.com.json"
)
TOKEN_FILE = ROOT_DIR / "token.json"
URL_FILE = ROOT_DIR / "auth_url.txt"


class URLSaver:
    """Saves the auth URL to a file instead of just printing it."""
    def format(self, **kwargs):
        url = kwargs.get("url", "")
        URL_FILE.write_text(url, encoding="utf-8")
        return "Auth URL saved to auth_url.txt"


flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)

creds = flow.run_local_server(
    port=8080,
    open_browser=False,
    authorization_prompt_message=URLSaver(),
    success_message="Authorization complete! You can close this tab.",
)

TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
URL_FILE.unlink(missing_ok=True)
print("SUCCESS: token.json saved.", flush=True)
