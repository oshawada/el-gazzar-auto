# tools/rewrite_arabic.py
# Purpose: Rewrite article in Saudi Arabic with SEO marketing keywords using Claude API
# Inputs:  .tmp/article_raw.json
# Outputs: .tmp/article_arabic.json with {title, intro, sections[], conclusion, meta_description, seo_keywords[]}

import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

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
        "أنت محرر صحفي متخصص في مجال السيارات، أسلوبك مطابق تماماً لموقع المربع نت (almuraba.net) — "
        "المرجع الأول للمحتوى السياراتي السعودي الاحترافي."
        "\n\n## أسلوب المربع نت الذي يجب محاكاته بدقة:"
        "\n\n**اللغة والنبرة:**"
        "\n- فصحى عربية سلسة وواضحة تماماً — لا عامية ولا كلمات دارجة إطلاقاً"
        "\n- نبرة صحفية تحليلية محترفة ومحايدة — ليست حماسية مبالغاً فيها"
        "\n- الجمل متوسطة الطول، مترابطة، تسرد السياق قبل الحكم"
        "\n- الاعتماد على الحقائق والأرقام والمواصفات التقنية الدقيقة من المصدر"
        "\n\n**العنوان الرئيسي:**"
        "\n- مباشر ومعلوماتي يحتوي على المعلومة الأهم أو الرقم الأبرز"
        "\n- أمثلة: 'لكزس TZ 2027 الجديدة بقوة تتجاوز 400 حصان' / 'السيارات الكهربائية: الحقيقة الكاملة عن الصيانة'"
        "\n\n**المقدمة:**"
        "\n- تبدأ بتحديد الموضوع مباشرة في الجملة الأولى دون مقدمات"
        "\n- تذكر الجهة أو الشركة أو الموديل الرئيسي في أول سطر"
        "\n- 2-3 جمل تضع القارئ في الصورة الكاملة فوراً"
        "\n\n**العناوين الفرعية للأقسام:**"
        "\n- وصفية تخبر القارئ بما سيقرأه بالضبط"
        "\n- أمثلة: 'التركيز الأكبر كان على الهدوء' / 'بطاريات أكبر ونظام دفع أكثر ذكاءً' / 'السيارات الصينية تضغط سوق المستعمل بقوة'"
        "\n- لا تكن غامضة أو تشويقية مبهمة — كن محدداً ومعلوماتياً"
        "\n\n**محتوى الأقسام:**"
        "\n- كل قسم يبدأ بالنقطة الجوهرية مباشرة"
        "\n- يضم الأرقام والمواصفات والتفاصيل التقنية الحقيقية"
        "\n- اشرح المصطلحات التقنية بعبارات واضحة في السياق"
        "\n- ربط المعلومة بالسياق السعودي أو الخليجي حين يكون مناسباً"
        "\n- الاستشهاد بتصريحات المسؤولين بين علامات اقتباس إن وُجدت في المصدر"
        "\n\n**الخاتمة:**"
        "\n- قصيرة (2-3 جمل) تلخص الأهمية وتشير للمستقبل أو تطرح توقعاً"
        "\n- لا تنهِ بسؤال مباشر للقارئ"
        "\n\n## قواعد صارمة:"
        "\n1. استخدم الأسماء والأرقام الحقيقية من المصدر فقط — لا تخترع معلومات"
        "\n2. اكتب بالعربية الفصحى فقط — ممنوع أي حرف من لغة أخرى إلا في حقل image_prompt"
        "\n3. ادمج الكلمات المفتاحية بشكل طبيعي داخل السياق دون إقحام"
        "\n4. لا تستخدم كلمات عامية مثل: الحين، ترا، ابغى، زين، واجد، يبيلك، صراحة"
        "\n5. لا مبالغة في الحماس — حافظ على النبرة التحليلية المحترفة"
        "\n6. حقل image_prompt فقط يُكتب بالإنجليزية — جملة واحدة تصف مشهد السيارة"
        "\n\nرد بـ JSON صالح فقط — لا تضع أي نص قبله أو بعده."
    )
    user = f"""حوّل المحتوى التالي إلى مقالة صحفية متكاملة جاهزة للنشر بأسلوب موقع المربع نت:

الكلمات المفتاحية للدمج: {kw_list}

عنوان المصدر: {article['title']}

محتوى المصدر:
{article['body'][:4000]}

اكتب JSON بهذا الشكل بالضبط:
{{
  "title": "عنوان مباشر معلوماتي يحتوي على المعلومة أو الرقم الأبرز في المقال",
  "intro": "مقدمة من 2-3 جمل تحدد الموضوع والجهة الرئيسية فوراً، أسلوب المربع نت الصحفي المحترف",
  "sections": [
    {{"heading": "عنوان قسم وصفي محدد يخبر القارئ بما سيقرأه", "body": "فقرة تفصيلية بالحقائق والأرقام والمواصفات من المصدر، لا تقل عن 5 جمل، أسلوب المربع نت التحليلي"}},
    {{"heading": "عنوان قسم وصفي محدد يخبر القارئ بما سيقرأه", "body": "فقرة تفصيلية بالحقائق والأرقام والمواصفات من المصدر، لا تقل عن 5 جمل، أسلوب المربع نت التحليلي"}},
    {{"heading": "عنوان قسم وصفي محدد يخبر القارئ بما سيقرأه", "body": "فقرة تفصيلية بالحقائق والأرقام والمواصفات من المصدر، لا تقل عن 5 جمل، أسلوب المربع نت التحليلي"}}
  ],
  "conclusion": "خاتمة من 2-3 جمل تلخص الأهمية وتشير للمستقبل، قصيرة ومكثفة",
  "meta_description": "وصف SEO لا يتجاوز 155 حرفاً",
  "seo_keywords": ["كلمات", "مفتاحية", "مستخدمة"],
  "image_prompt": "ENGLISH ONLY: photorealistic automotive photography, [describe the specific car or scene from the article], studio or road setting, high quality"
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

    from google import genai
    from google.genai import types as gtypes

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
    client = genai.Client(api_key=api_key)
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    system, user = build_prompt(article, keywords)

    for attempt in range(1, max_retries + 1):
        print(f"[rewrite] Calling Gemini API (attempt {attempt})...")
        response = client.models.generate_content(
            model=model,
            contents=user,
            config=gtypes.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=8192,
                temperature=0.7,
            ),
        )
        raw = response.text.strip()

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
