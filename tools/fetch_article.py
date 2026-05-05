# tools/fetch_article.py
# Purpose: Fetch and extract article content from a URL
# Inputs:  --url <article_url>
# Outputs: .tmp/article_raw.json with {title, body, source_url, published_date}

import argparse
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
TMP_DIR = Path(__file__).parent.parent / ".tmp"
OUTPUT_FILE = TMP_DIR / "article_raw.json"
MIN_BODY_LENGTH = 200
JS_THRESHOLD = 500


def _extract_with_bs4(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title = ""
    if soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)
    elif soup.find("title"):
        title = soup.find("title").get_text(strip=True)

    # Published date
    published_date = ""
    time_tag = soup.find("time")
    if time_tag:
        published_date = time_tag.get("datetime", time_tag.get_text(strip=True))
    if not published_date:
        meta_date = soup.find("meta", attrs={"property": "article:published_time"})
        if meta_date:
            published_date = meta_date.get("content", "")
    if not published_date:
        published_date = datetime.now().strftime("%Y-%m-%d")

    # Body — try <article>, then <main>, then largest <div> with <p> tags
    body_text = ""
    for container_tag in ["article", "main"]:
        container = soup.find(container_tag)
        if container:
            paragraphs = container.find_all("p")
            body_text = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            if len(body_text) >= MIN_BODY_LENGTH:
                break

    if len(body_text) < MIN_BODY_LENGTH:
        # Fallback: find all <p> tags in the page
        all_p = soup.find_all("p")
        body_text = " ".join(p.get_text(strip=True) for p in all_p if len(p.get_text(strip=True)) > 40)

    return {"title": title, "body": body_text, "source_url": url, "published_date": published_date}


def _fetch_with_playwright(url: str) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        html = page.content()
        browser.close()
    return html


def fetch(url: str) -> dict:
    TMP_DIR.mkdir(exist_ok=True)

    # First attempt: plain requests
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    html = response.text
    data = _extract_with_bs4(html, url)

    # If body is too short, assume JS-rendered — retry with Playwright
    if len(data["body"]) < JS_THRESHOLD:
        print(f"[fetch] Body too short ({len(data['body'])} chars), retrying with Playwright...")
        try:
            html = _fetch_with_playwright(url)
            data = _extract_with_bs4(html, url)
        except Exception as e:
            print(f"[fetch] Playwright failed: {e} — using original content")

    if len(data["body"]) < MIN_BODY_LENGTH:
        raise ValueError(
            f"Article body too short ({len(data['body'])} chars) — not a valid article: {url}"
        )

    OUTPUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fetch] Saved → {OUTPUT_FILE}")
    print(f"[fetch] Title: {data['title'][:80]}")
    print(f"[fetch] Body:  {len(data['body'])} chars")
    return data


def main():
    parser = argparse.ArgumentParser(description="Fetch article content from URL")
    parser.add_argument("--url", required=True, help="Article URL to fetch")
    args = parser.parse_args()
    fetch(args.url)


if __name__ == "__main__":
    main()
