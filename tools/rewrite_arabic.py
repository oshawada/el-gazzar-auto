# tools/rewrite_arabic.py
# Purpose: Rewrite article in Saudi Arabic with SEO marketing keywords using Groq API
# Inputs:  .tmp/article_raw.json
# Outputs: .tmp/article_arabic.json with {title, intro, sections[], conclusion, meta_description, seo_keywords[]}

import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

TMP_DIR = Path(__file__).parent.parent / ".tmp"
INPUT_FILE = TMP_DIR / "article_raw.json"
OUTPUT_FILE = TMP_DIR / "article_arabic.json"

# كلمات SEO سعودية حسب الموضوع
SEO_KEYWORDS = {
    # السيارات — الكاتيجوري الرئيسية لأن كل المواقع للسيارات
    "automotive_review": [
        "تجربة قيادة", "مراجعة سيارة", "أفضل السيارات 2026", "تقييم سيارة",
        "مواصفات السيارة", "أداء المحرك", "استهلاك الوقود", "سيارات فاخرة",
        "سيارة عائلية", "تجربة الطريق", "راحة القيادة", "نظام الصوت",
        "تقنيات السلامة", "نظام المساعدة بالقيادة", "شاشة لمس السيارة"
    ],
    "automotive_news": [
        "أخبار السيارات", "موديلات 2026", "إطلاق سيارة جديدة", "معرض السيارات",
        "سيارات جديدة في السعودية", "أسعار السيارات في السعودية", "السوق السعودية للسيارات",
        "وكلاء السيارات", "عروض السيارات", "السيارات الكهربائية في السعودية",
        "سيارات هايبرد", "رؤية 2030 والسيارات", "مستقبل النقل في السعودية"
    ],
    "automotive_compare": [
        "مقارنة سيارات", "أفضل سيارة في فئتها", "سيارة دفع رباعي",
        "SUV مقابل سيدان", "السيارات الاقتصادية", "سيارات بأفضل سعر",
        "أقوى محرك", "أوسع سيارة", "أوفر استهلاكاً للوقود",
        "قائمة أفضل السيارات", "تصنيف السيارات", "اختبار الأمان"
    ],
    "automotive_electric": [
        "السيارات الكهربائية", "سيارة كهربائية بالسعودية", "شحن السيارة الكهربائية",
        "مدى السيارة الكهربائية", "توفير الوقود", "المركبات الصديقة للبيئة",
        "هايبرد", "بلوق إن هايبرد", "الطاقة المتجددة والسيارات",
        "Tesla السعودية", "سيارات المستقبل", "الاستدامة في قطاع النقل"
    ],
    "automotive_general": [
        "سيارات للبيع", "أسعار السيارات", "سيارات جديدة", "سيارات مستعملة",
        "معرض سيارات السعودية", "أفضل السيارات", "موديلات السيارات",
        "تويوتا السعودية", "هيونداي السعودية", "BMW السعودية",
        "مرسيدس السعودية", "لكزس", "نيسان", "كيا", "فورد",
        "قطع غيار السيارات", "صيانة السيارات", "ضمان السيارة"
    ],
}

# كلمات للكشف عن نوع المحتوى الخودموتيفي
TOPIC_KEYWORDS = {
    "automotive_review": [
        "review", "test drive", "driven", "first drive", "behind the wheel",
        "ride quality", "handling", "performance", "interior", "exterior",
        "تجربة", "مراجعة", "قيادة", "أداء", "مقعد", "داخلية"
    ],
    "automotive_news": [
        "debut", "reveal", "launch", "unveil", "announced", "new model",
        "price", "release", "production", "concept", "show", "motor show",
        "إطلاق", "موديل جديد", "سعر", "معرض", "كشف", "إعلان"
    ],
    "automotive_compare": [
        "vs", "versus", "comparison", "compare", "better", "best",
        "ranking", "top 10", "alternatives", "مقارنة", "أفضل", "تصنيف"
    ],
    "automotive_electric": [
        "electric", "ev", "hybrid", "plug-in", "battery", "charging",
        "range", "emissions", "كهربائي", "هايبرد", "شحن", "بطارية"
    ],
}


def detect_topic(text: str) -> str:
    text_lower = text.lower()
    scores = {topic: 0 for topic in TOPIC_KEYWORDS}
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[topic] += 1
    best = max(scores, key=scores.get)
    # Default إلى automotive_general لأن كل المواقع للسيارات
    return best if scores[best] > 0 else "automotive_general"


def build_prompt(article: dict, keywords: list[str]) -> tuple[str, str]:
    kw_list = "، ".join(keywords[:8])
    system = (
        "أنت كاتب محتوى سعودي متخصص في مجال السيارات، أسلوبك يجمع بين العامية السعودية والمصطلحات التقنية. "
        "مهمتك كتابة مقالات تُنشر على مواقع ومدونات سيارات سعودية، يقرأها الشباب السعودي المهتم بالسيارات. "
        "\n\nأسلوب الكتابة المطلوب:"
        "\n- اللهجة: عامية سعودية واضحة ومفهومة — مثل: 'الحين'، 'زين'، 'ترا'، 'ابغى'، 'واجد'، 'يبيلك'، 'ما تلقى'، 'صراحة'، 'بصراحة تامة'"
        "\n- النبرة: حماسية وودية كأنك تحكي لصاحبك اللي يهواه السيارات"
        "\n- العناوين: مباشرة وجذابة — مثل: 'ليش هذي السيارة تستاهل فلوسك؟' أو 'الحقيقة اللي ما يقولونها'"
        "\n- المصطلحات التقنية: اكتبها بالعربية واشرحها بأسلوب بسيط"
        "\n- التشويق: ابدأ كل قسم بجملة تشدّ الانتباه"
        "\n\nقواعد صارمة:"
        "\n1. استخدم الأسماء والأرقام الحقيقية من المصدر — لا تخترع معلومات"
        "\n2. اكتب بالعربية فقط — ممنوع أي حرف من لغة أخرى"
        "\n3. ادمج الكلمات المفتاحية بشكل طبيعي في السياق"
        "\n4. حقل image_prompt فقط يُكتب بالإنجليزية — جملة واحدة تصف مشهد السيارة في المقال"
        "\n\nرد بـ JSON صالح فقط — لا تضع أي نص قبله أو بعده."
    )
    user = f"""حوّل المحتوى التالي إلى مقالة صحفية متكاملة جاهزة للنشر:

الكلمات المفتاحية للدمج: {kw_list}

عنوان المصدر: {article['title']}

محتوى المصدر:
{article['body'][:4000]}

اكتب JSON بهذا الشكل بالضبط:
{{
  "title": "عنوان جذاب يعكس موضوع المقال الحقيقي",
  "intro": "مقدمة من 3 جمل تشد القارئ وتذكر الموضوع الرئيسي بوضوح",
  "sections": [
    {{"heading": "عنوان القسم 1", "body": "فقرة تفصيلية تعتمد على معلومات حقيقية من المصدر، لا تقل عن 5 جمل"}},
    {{"heading": "عنوان القسم 2", "body": "فقرة تفصيلية تعتمد على معلومات حقيقية من المصدر، لا تقل عن 5 جمل"}},
    {{"heading": "عنوان القسم 3", "body": "فقرة تفصيلية تعتمد على معلومات حقيقية من المصدر، لا تقل عن 5 جمل"}}
  ],
  "conclusion": "خاتمة من 3 جمل تلخص وتفتح باب النقاش",
  "meta_description": "وصف SEO لا يتجاوز 155 حرفاً",
  "seo_keywords": ["كلمات", "مفتاحية", "مستخدمة"],
  "image_prompt": "ENGLISH ONLY: photorealistic image describing the main subject of the article, automotive photography style"
}}"""
    return system, user


def _clean_non_arabic(obj):
    """إزالة الكلمات المختلطة والأحرف الأجنبية من النصوص العربية."""
    import re
    import unicodedata

    # أنماط الأحرف الأجنبية غير المرغوب فيها
    FORBIDDEN_SCRIPTS = ("CJK", "HIRAGANA", "KATAKANA", "HANGUL", "THAI", "DEVANAGARI", "GEORGIAN", "ARMENIAN")

    def has_arabic(word: str) -> bool:
        return any("؀" <= ch <= "ۿ" for ch in word)

    def has_latin(word: str) -> bool:
        return any("LATIN" in unicodedata.name(ch, "") for ch in word if ch.isalpha())

    def clean_str(s: str) -> str:
        # 1. إزالة أحرف من لغات غير مرغوبة (صينية، يابانية إلخ)
        cleaned = []
        for ch in s:
            name = unicodedata.name(ch, "")
            if any(script in name for script in FORBIDDEN_SCRIPTS):
                cleaned.append(" ")
            else:
                cleaned.append(ch)
        s = "".join(cleaned)

        # 2. إزالة الكلمات المختلطة (عربي + لاتيني في نفس الكلمة)
        words = s.split(" ")
        result = []
        for word in words:
            if has_arabic(word) and has_latin(word):
                # احتفظ بالجزء العربي فقط
                arabic_only = re.sub(r"[a-zA-Z]+", "", word)
                result.append(arabic_only if arabic_only.strip() else "")
            else:
                result.append(word)
        s = " ".join(result)

        # 3. تنظيف مسافات متعددة
        s = re.sub(r" {2,}", " ", s).strip()
        return s

    if isinstance(obj, str):
        return clean_str(obj)
    if isinstance(obj, dict):
        return {k: _clean_non_arabic(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_non_arabic(i) for i in obj]
    return obj


def rewrite(max_retries: int = 2) -> dict:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    article = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    topic = detect_topic(article["title"] + " " + article["body"])
    keywords = os.environ.get("SEO_KEYWORDS_OVERRIDE", "").split(",")
    keywords = [k.strip() for k in keywords if k.strip()] or SEO_KEYWORDS.get(topic, SEO_KEYWORDS["automotive_general"])

    print(f"[rewrite] Detected topic: {topic}")
    print(f"[rewrite] SEO keywords: {keywords[:5]}...")

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    system, user = build_prompt(article, keywords)

    for attempt in range(1, max_retries + 1):
        print(f"[rewrite] Calling Groq API (attempt {attempt})...")
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            result = json.loads(raw)
            # تنظيف أي أحرف غير عربية أو لاتينية وردت بالخطأ
            result = _clean_non_arabic(result)
            break
        except json.JSONDecodeError as e:
            print(f"[rewrite] JSON parse failed (attempt {attempt}): {e}")
            if attempt == max_retries:
                raise RuntimeError(f"Claude returned invalid JSON after {max_retries} attempts") from e
            # Add explicit JSON demand to the next attempt
            user += "\n\nتنبيه: يجب أن يكون ردك JSON صالحاً فقط، بدون أي نص إضافي قبله أو بعده."

    TMP_DIR.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[rewrite] Saved → {OUTPUT_FILE}")
    print(f"[rewrite] Title: {result.get('title', '')[:80]}")
    return result


def main():
    rewrite()


if __name__ == "__main__":
    main()
