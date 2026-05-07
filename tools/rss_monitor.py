# tools/rss_monitor.py
# Purpose: Main orchestrator — monitors RSS feeds and runs the full pipeline for new articles
# Inputs:  RSS_FEEDS, RECIPIENT_EMAIL, RSS_POLL_INTERVAL from .env
# Outputs: Runs fetch → rewrite → pdf → send for each new article

import json
import logging
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from datetime import datetime
from pathlib import Path

import feedparser
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

load_dotenv()

TMP_DIR = Path(__file__).parent.parent / ".tmp"
TOOLS_DIR = Path(__file__).parent
SEEN_FILE = TMP_DIR / "rss_seen.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("rss_monitor")


def load_seen() -> set:
    if SEEN_FILE.exists():
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        return set(data)
    return set()


def save_seen(seen: set):
    TMP_DIR.mkdir(exist_ok=True)
    SEEN_FILE.write_text(json.dumps(list(seen), ensure_ascii=False, indent=2), encoding="utf-8")


def run_tool(script: str, *args) -> bool:
    """Run a tool script and return True if successful."""
    cmd = [sys.executable, str(TOOLS_DIR / script)] + list(args)
    log.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        log.error(f"{script} failed with code {result.returncode}")
        return False
    return True


def find_latest_pdf() -> Path | None:
    """Return the most recently modified PDF in .tmp/, or None."""
    pdfs = sorted(TMP_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    return pdfs[0] if pdfs else None


def process_article(url: str) -> Path | None:
    """Run fetch→rewrite→image→pdf for one URL. Returns the generated PDF Path or None."""
    log.info(f"=== Processing: {url} ===")

    pdf_before = find_latest_pdf()
    mtime_before = pdf_before.stat().st_mtime if pdf_before else 0

    if not run_tool("fetch_article.py", "--url", url):
        return None

    if not run_tool("rewrite_arabic.py"):
        return None

    if not run_tool("generate_image.py"):
        log.warning("Image generation failed — continuing without image")

    if not run_tool("generate_pdf.py"):
        return None

    # Find the PDF that appeared / was updated after we started
    pdf_after = find_latest_pdf()
    if pdf_after and pdf_after.stat().st_mtime > mtime_before:
        log.info(f"=== Done: {url} → {pdf_after.name} ===")
        return pdf_after

    log.warning(f"Could not locate generated PDF for {url}")
    return None


def send_batch(pdf_paths: list[Path], recipient: str):
    """Send one email with all PDFs attached, using send_email.py --batch."""
    paths_arg = ",".join(str(p) for p in pdf_paths)
    run_tool("send_email.py", "--to", recipient, "--batch", paths_arg)


MAX_ARTICLES_PER_CYCLE = int(os.environ.get("MAX_ARTICLES_PER_CYCLE", "3"))


def poll_feeds():
    feeds_raw = os.environ.get("RSS_FEEDS", "")
    recipient = os.environ.get("RECIPIENT_EMAIL", "")

    if not feeds_raw:
        log.error("RSS_FEEDS not set in .env — nothing to monitor")
        return
    if not recipient:
        log.error("RECIPIENT_EMAIL not set in .env — cannot send emails")
        return

    feed_urls = [f.strip() for f in feeds_raw.split(",") if f.strip()]
    seen = load_seen()
    collected_pdfs: list[Path] = []
    processed_urls: list[str] = []

    for feed_url in feed_urls:
        if len(collected_pdfs) >= MAX_ARTICLES_PER_CYCLE:
            log.info(f"Reached cycle limit ({MAX_ARTICLES_PER_CYCLE} articles) — stopping.")
            break

        log.info(f"Checking feed: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            log.error(f"Failed to parse feed {feed_url}: {e}")
            continue

        for entry in feed.entries:
            if len(collected_pdfs) >= MAX_ARTICLES_PER_CYCLE:
                break

            article_url = entry.get("link", "")
            if not article_url or article_url in seen:
                continue

            # Mark as seen immediately so failed articles don't retry forever
            seen.add(article_url)
            save_seen(seen)

            log.info(f"New article found: {entry.get('title', article_url)[:80]}")
            pdf = process_article(article_url)

            if pdf:
                collected_pdfs.append(pdf)
                processed_urls.append(article_url)
            else:
                log.warning(f"Pipeline failed for: {article_url}")

    if not collected_pdfs:
        log.info("No new articles found this cycle.")
        return

    log.info(f"Sending batch email with {len(collected_pdfs)} PDF(s)...")
    send_batch(collected_pdfs, recipient)
    log.info(f"Cycle complete — {len(collected_pdfs)} article(s) processed and sent.")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Poll once and exit (for CI/GitHub Actions)")
    args = parser.parse_args()

    TMP_DIR.mkdir(exist_ok=True)
    interval_minutes = int(os.environ.get("RSS_POLL_INTERVAL", "60"))

    log.info("=" * 50)
    log.info("RSS Article Arabizer Monitor started")
    log.info(f"Poll interval: every {interval_minutes} minutes")
    feeds = os.environ.get("RSS_FEEDS", "NOT SET")
    log.info(f"Feeds: {feeds[:120]}")
    log.info("=" * 50)

    poll_feeds()

    if args.once:
        log.info("--once mode: exiting after first poll.")
        return

    scheduler = BlockingScheduler(timezone="Asia/Riyadh")
    scheduler.add_job(poll_feeds, "interval", minutes=interval_minutes, id="rss_poll")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Monitor stopped.")


if __name__ == "__main__":
    main()
