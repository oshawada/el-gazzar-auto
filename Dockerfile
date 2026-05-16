FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browser — used as fallback for JS-rendered article pages
RUN playwright install chromium --with-deps || echo "[docker] Playwright install skipped"

# Download Amiri (open-source Arabic font) mapped as tahoma.ttf
# so generate_pdf.py finds it without code changes on Linux
RUN mkdir -p assets/fonts && \
    wget -q -O assets/fonts/tahoma.ttf \
      "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf" && \
    wget -q -O assets/fonts/tahomabd.ttf \
      "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Bold.ttf"

COPY . .

CMD ["python", "tools/rss_monitor.py"]
