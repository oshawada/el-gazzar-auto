# Workflow: Article Arabizer

## Objective
مراقبة مواقع إخبارية عبر RSS، وعند نزول مقالة جديدة: إعادة صياغتها بالعربية السعودية مع كلمات SEO تسويقية، تحويلها لـ PDF مُبرند، وإرسالها بالإيميل.

## Required Inputs
- `RSS_FEEDS` في `.env` — روابط الـ RSS feeds (comma-separated)
- `RECIPIENT_EMAIL` في `.env` — إيميل المستلِم
- `ANTHROPIC_API_KEY` في `.env` — مفتاح Claude API
- `GMAIL_USER` + `GMAIL_APP_PASSWORD` في `.env` — بيانات Gmail SMTP
- `LOGO_PATH` في `.env` — مسار ملف اللوجو (PNG/SVG)
- `BRAND_COLOR_PRIMARY` + `BRAND_COLOR_ACCENT` في `.env` — ألوان البراند

## Steps

### Step 1 — مراقبة RSS (rss_monitor.py)
- يشتغل كـ background process
- كل `RSS_POLL_INTERVAL` دقيقة يفحص كل feed
- يقارن بـ `.tmp/rss_seen.json` لتجنب التكرار
- لما يلاقي مقالة جديدة: يشغّل Steps 2-5

### Step 2 — جلب المقالة
Run: `python tools/fetch_article.py --url "<URL>"`
- يستخدم requests + BeautifulSoup
- Fallback: Playwright لو الصفحة JS-rendered
- يحفظ: `.tmp/article_raw.json`

### Step 3 — إعادة الصياغة بالعربية
Run: `python tools/rewrite_arabic.py`
- يكشف موضوع المقالة → يختار كلمات SEO سعودية
- يستدعي Claude API بـ prompt محكم
- يطلب JSON: `{title, intro, sections[], conclusion, meta_description, seo_keywords[]}`
- يحفظ: `.tmp/article_arabic.json`

### Step 4 — توليد PDF
Run: `python tools/generate_pdf.py`
- عربي RTL بخط Tahoma
- لوجو + ألوان البراند
- هيكل: لوجو → عنوان → مقدمة → أقسام → خاتمة → footer
- يحفظ: `.tmp/article_<slug>_<YYYYMMDD>.pdf`

### Step 5 — إرسال الإيميل
Run: `python tools/send_email.py`
- Gmail SMTP SSL (port 465)
- Subject: "مقال جديد: {title}"
- المرفق: الـ PDF

## Tools Used
- `tools/rss_monitor.py` — الـ orchestrator الرئيسي
- `tools/fetch_article.py`
- `tools/rewrite_arabic.py`
- `tools/generate_pdf.py`
- `tools/send_email.py`

## Expected Output
- PDF عربي في `.tmp/` يُرسَل بالإيميل لـ RECIPIENT_EMAIL
- Log في الـ terminal لكل خطوة

## Edge Cases & Known Issues
- صفحة JS-rendered: Playwright fallback تلقائي
- Claude JSON مش صالح: retry مرة واحدة
- Gmail: يحتاج App Password مش باسورد الحساب الأصلي
- `.tmp/rss_seen.json` يتحفظ بين الـ runs لمنع التكرار
- لو الـ fetch فشل: يلوج الخطأ ويكمل للمقالة الجاية
