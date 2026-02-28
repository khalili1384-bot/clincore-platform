"""
Clinical-grade narrative → rubric extraction pipeline.

Three-layer architecture:
  A) Persian normalization (unicode, half-space, diacritics, stemming, synonyms)
  B) Semantic concept mapping (MIND / GENERALS / SLEEP / PARTICULAR clusters)
  C) Weighted rubric construction (MIND=1.8, GENERALS=1.4, PARTICULAR=1.0)

Plus differentiation enhancement (Ars / Nux / Lyc cluster boosting).

Output: { rubrics, weighted_case_df }
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
import logging
from pathlib import Path
from typing import Any

import pandas as pd

_log = logging.getLogger("clincore.mcare_engine.clinical_extractor")

DB_PATH = str(Path(__file__).resolve().parent / "data" / "synthesis.db")

# ═══════════════════════════════════════════════════════════════
# LAYER A — Persian Normalization
# ═══════════════════════════════════════════════════════════════

_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670]")
_MULTI_SPACE = re.compile(r"\s+")

# Common Persian verb/adjective endings for simple stemming
_FA_SUFFIXES = (
    "\u200c\u0627\u0645", "\u200c\u0627\u06cc", "\u200c\u0627\u0646\u062f",  # ‌ام ‌ای ‌اند
    "\u200c\u0627\u06cc\u0645", "\u200c\u0627\u06cc\u062f",  # ‌ایم ‌اید
    "\u0645\u06cc\u200c", "\u0646\u0645\u06cc\u200c",  # می‌ نمی‌
    "\u0647\u0627", "\u0647\u0627\u06cc",  # ها های
    "\u062a\u0631\u06cc\u0646", "\u062a\u0631",  # ترین تر
    "\u0634\u0627\u0646", "\u0634",  # شان ش
    "\u0645\u0646\u062f", "\u0648\u0627\u0631",  # مند وار
)

# Prefix stripping
_FA_PREFIXES = (
    "\u0645\u06cc\u200c",  # می‌
    "\u0646\u0645\u06cc\u200c",  # نمی‌
    "\u0645\u06cc",  # می
    "\u0646\u0645\u06cc",  # نمی
)

# Synonym mapping: map variations to canonical concept keys
SYNONYM_MAP: dict[str, str] = {
    # --- MIND: fear / poverty ---
    "financial fear": "fear_poverty",
    "fear of poverty": "fear_poverty",
    "fear bankruptcy": "fear_poverty",
    "fear of ruin": "fear_poverty",
    "money fear": "fear_poverty",
    "fear of losing money": "fear_poverty",
    "\u062a\u0631\u0633 \u0645\u0627\u0644\u06cc": "fear_poverty",  # ترس مالی
    "\u062a\u0631\u0633 \u0648\u0631\u0634\u06a9\u0633\u062a\u06af\u06cc": "fear_poverty",  # ترس ورشکستگی
    "\u062a\u0631\u0633 \u0641\u0642\u0631": "fear_poverty",  # ترس فقر
    "\u0646\u06af\u0631\u0627\u0646\u06cc \u0645\u0627\u0644\u06cc": "fear_poverty",  # نگرانی مالی
    # --- MIND: control ---
    "control": "desire_control",
    "controlling": "desire_control",
    "need to control": "desire_control",
    "desire to control": "desire_control",
    "\u06a9\u0646\u062a\u0631\u0644": "desire_control",  # کنترل
    "\u0648\u0633\u0648\u0627\u0633 \u06a9\u0646\u062a\u0631\u0644": "desire_control",  # وسواس کنترل
    # --- MIND: order / fastidious ---
    "order": "fastidious",
    "orderliness": "fastidious",
    "cleanliness": "fastidious",
    "neat": "fastidious",
    "tidy": "fastidious",
    "perfectionist": "fastidious",
    "fastidious": "fastidious",
    "\u0646\u0638\u0645": "fastidious",  # نظم
    "\u062a\u0645\u06cc\u0632\u06cc": "fastidious",  # تمیزی
    "\u0648\u0633\u0648\u0627\u0633": "fastidious",  # وسواس
    "\u06a9\u0645\u0627\u0644\u200c\u06af\u0631\u0627": "fastidious",  # کمال‌گرا
    "\u06a9\u0645\u0627\u0644\u06af\u0631\u0627": "fastidious",  # کمالگرا
    # --- MIND: reserved / introvert ---
    "introvert": "reserved",
    "reserved": "reserved",
    "shy": "reserved",
    "withdrawn": "reserved",
    "closed off": "reserved",
    "\u062f\u0631\u0648\u0646\u200c\u06af\u0631\u0627": "reserved",  # درون‌گرا
    "\u062f\u0631\u0648\u0646\u06af\u0631\u0627": "reserved",  # درونگرا
    "\u06a9\u0645\u200c\u062d\u0631\u0641": "reserved",  # کم‌حرف
    # --- MIND: responsibility / conscientious ---
    "responsible": "conscientious",
    "responsibility": "conscientious",
    "conscientious": "conscientious",
    "duty": "conscientious",
    "diligent": "conscientious",
    "\u0645\u0633\u0626\u0648\u0644\u06cc\u062a": "conscientious",  # مسئولیت
    "\u0648\u0638\u06cc\u0641\u0647\u200c\u0634\u0646\u0627\u0633": "conscientious",  # وظیفه‌شناس
    # --- MIND: anger ---
    "anger suppressed": "anger_suppressed",
    "suppressed anger": "anger_suppressed",
    "holds anger": "anger_suppressed",
    "anger inside": "anger_suppressed",
    "\u062e\u0634\u0645 \u0641\u0631\u0648\u062e\u0648\u0631\u062f\u0647": "anger_suppressed",  # خشم فروخورده
    "\u0639\u0635\u0628\u0627\u0646\u06cc\u062a \u067e\u0646\u0647\u0627\u0646": "anger_suppressed",  # عصبانیت پنهان
    "anger explosive": "anger_violent",
    "explosive anger": "anger_violent",
    "violent anger": "anger_violent",
    "rage": "anger_violent",
    "\u062e\u0634\u0645 \u0627\u0646\u0641\u062c\u0627\u0631\u06cc": "anger_violent",  # خشم انفجاری
    "\u0639\u0635\u0628\u0627\u0646\u06cc\u062a \u0634\u062f\u06cc\u062f": "anger_violent",  # عصبانیت شدید
    # --- MIND: ambitious ---
    "business-oriented": "ambitious",
    "ambitious": "ambitious",
    "workaholic": "ambitious",
    "career driven": "ambitious",
    "competitive": "ambitious",
    "\u062c\u0627\u0647\u200c\u0637\u0644\u0628": "ambitious",  # جاه‌طلب
    "\u062c\u0627\u0647\u0637\u0644\u0628": "ambitious",  # جاه‌طلب
    "\u06a9\u0627\u0631\u06cc": "ambitious",  # کاری
    # --- MIND: grief ---
    "grief": "grief",
    "bereavement": "grief",
    "loss": "grief",
    "mourning": "grief",
    "\u063a\u0645": "grief",  # غم
    "\u0633\u0648\u06af": "grief",  # سوگ
    "\u0639\u0632\u0627\u062f\u0627\u0631\u06cc": "grief",  # عزاداری
    "\u0641\u0648\u062a": "grief",  # فوت
    "\u0627\u0632 \u062f\u0633\u062a \u062f\u0627\u062f\u0646": "grief",  # از دست دادن
    # --- MIND: anxiety ---
    "anxiety": "anxiety",
    "anxious": "anxiety",
    "worry": "anxiety",
    "worried": "anxiety",
    "nervous": "anxiety",
    "apprehension": "anxiety",
    "\u0627\u0636\u0637\u0631\u0627\u0628": "anxiety",  # اضطراب
    "\u0646\u06af\u0631\u0627\u0646\u06cc": "anxiety",  # نگرانی
    "\u0646\u06af\u0631\u0627\u0646": "anxiety",  # نگران
    "\u062f\u0644\u0634\u0648\u0631\u0647": "anxiety",  # دلشوره
    "\u0627\u0636\u0637\u0631\u0627\u0628\u06cc": "anxiety",  # اضطرابی
    # --- MIND: fear general ---
    "fear": "fear",
    "phobia": "fear",
    "afraid": "fear",
    "\u062a\u0631\u0633": "fear",  # ترس
    "\u0641\u0648\u0628\u06cc\u0627": "fear",  # فوبیا
    "\u0648\u062d\u0634\u062a": "fear",  # وحشت
    # --- MIND: weeping ---
    "weeping": "weeping",
    "crying": "weeping",
    "tearful": "weeping",
    "\u06af\u0631\u06cc\u0647": "weeping",  # گریه
    # --- MIND: company ---
    "alone": "company_aversion",
    "solitude": "company_aversion",
    "\u062a\u0646\u0647\u0627\u06cc\u06cc": "company_aversion",  # تنهایی
    "\u062a\u0646\u0647\u0627": "company_aversion",  # تنها
    "company desire": "company_desire",
    "social": "company_desire",
    "\u062c\u0645\u0639": "company_desire",  # جمع
    # --- MIND: consolation ---
    "consolation": "consolation",
    "\u062f\u0644\u062f\u0627\u0631\u06cc": "consolation",  # دلداری
    # --- MIND: irritability ---
    "irritable": "irritability",
    "irritability": "irritability",
    "impatient": "irritability",
    "short temper": "irritability",
    "\u062a\u062d\u0631\u06cc\u06a9\u200c\u067e\u0630\u06cc\u0631": "irritability",  # تحریک‌پذیر
    "\u0628\u06cc\u200c\u062d\u0648\u0635\u0644\u0647": "irritability",  # بی‌حوصله
    "\u0639\u0635\u0628\u06cc": "irritability",  # عصبی
    "\u0639\u0635\u0628\u0627\u0646\u06cc": "irritability",  # عصبانی (also anger)
    "\u0632\u0648\u062f\u0631\u0646\u062c": "irritability",  # زودرنج
    # --- MIND: insecurity ---
    "insecurity": "insecurity",
    "insecure": "insecurity",
    "lack of confidence": "insecurity",
    "self-doubt": "insecurity",
    "\u0639\u062f\u0645 \u0627\u0645\u0646\u06cc\u062a": "insecurity",  # عدم امنیت
    "\u0646\u0627\u0627\u0645\u0646\u06cc": "insecurity",  # ناامنی
    "\u0628\u06cc\u200c\u0627\u0639\u062a\u0645\u0627\u062f\u06cc": "insecurity",  # بی‌اعتمادی
    # --- MIND: jealousy ---
    "jealousy": "jealousy",
    "jealous": "jealousy",
    "envy": "jealousy",
    "\u062d\u0633\u0627\u062f\u062a": "jealousy",  # حسادت
    # --- MIND: hurry ---
    "hurry": "hurry",
    "impatience": "hurry",
    "hasty": "hurry",
    "\u0639\u062c\u0644\u0647": "hurry",  # عجله
    # --- MIND: indifference ---
    "indifference": "indifference",
    "apathy": "indifference",
    "\u0628\u06cc\u200c\u062a\u0641\u0627\u0648\u062a\u06cc": "indifference",  # بی‌تفاوتی
    # --- MIND: restlessness ---
    "restless": "restlessness",
    "restlessness": "restlessness",
    "\u0628\u06cc\u200c\u0642\u0631\u0627\u0631\u06cc": "restlessness",  # بی‌قراری
    "\u0628\u06cc\u0642\u0631\u0627\u0631": "restlessness",  # بیقرار
    # --- SLEEP ---
    "insomnia": "insomnia",
    "sleeplessness": "insomnia",
    "\u0628\u06cc\u200c\u062e\u0648\u0627\u0628\u06cc": "insomnia",  # بی‌خوابی
    "\u0628\u06cc\u062e\u0648\u0627\u0628\u06cc": "insomnia",  # بیخوابی
    "nightmare": "nightmares",
    "nightmares": "nightmares",
    "\u06a9\u0627\u0628\u0648\u0633": "nightmares",  # کابوس
    "midnight waking": "waking_midnight",
    "midnight": "waking_midnight",
    "\u0646\u06cc\u0645\u0647\u200c\u0634\u0628": "waking_midnight",  # نیمه‌شب
    "\u0646\u06cc\u0645\u0647 \u0634\u0628": "waking_midnight",  # نیمه شب
    "early waking": "waking_early",
    "early morning": "waking_early",
    "\u0633\u062d\u0631": "waking_early",  # سحر
    "\u0635\u0628\u062d \u0632\u0648\u062f": "waking_early",  # صبح زود
    "bruxism": "grinding_teeth",
    "teeth grinding": "grinding_teeth",
    "grinding teeth": "grinding_teeth",
    "\u062f\u0646\u062f\u0627\u0646\u200c\u0642\u0631\u0648\u0686\u0647": "grinding_teeth",  # دندان‌قروچه
    "sleep talking": "talking_sleep",
    "talking in sleep": "talking_sleep",
    "\u062d\u0631\u0641 \u0632\u062f\u0646 \u062f\u0631 \u062e\u0648\u0627\u0628": "talking_sleep",  # حرف زدن در خواب
    # --- GENERALS ---
    "warm patient": "heat_agg",
    "warm-blooded": "heat_agg",
    "hot patient": "heat_agg",
    "worse heat": "heat_agg",
    "\u06af\u0631\u0645\u0627\u06cc\u06cc": "heat_agg",  # گرمایی
    "\u06af\u0631\u0645": "heat_agg",  # گرم
    "\u06af\u0631\u0645\u0627": "heat_agg",  # گرما
    "chilly": "cold_agg",
    "cold patient": "cold_agg",
    "cold-blooded": "cold_agg",
    "worse cold": "cold_agg",
    "\u0633\u0631\u0645\u0627\u06cc\u06cc": "cold_agg",  # سرمایی
    "\u0633\u0631\u062f": "cold_agg",  # سرد
    "\u0633\u0631\u0645\u0627": "cold_agg",  # سرما
    "desire sour": "desire_sour",
    "sour food": "desire_sour",
    "\u062a\u0631\u0634\u06cc": "desire_sour",  # ترشی
    "\u0645\u06cc\u0644 \u0628\u0647 \u062a\u0631\u0634": "desire_sour",  # میل به ترش
    "desire sweet": "desire_sweet",
    "sweet craving": "desire_sweet",
    "\u0634\u06cc\u0631\u06cc\u0646\u06cc": "desire_sweet",  # شیرینی
    "desire salt": "desire_salt",
    "salty food": "desire_salt",
    "\u0646\u0645\u06a9": "desire_salt",  # نمک
    "offensive sweat": "perspiration_offensive",
    "smelly sweat": "perspiration_offensive",
    "\u0639\u0631\u0642 \u0628\u062f\u0628\u0648": "perspiration_offensive",  # عرق بدبو
    "thirst": "thirst",
    "thirsty": "thirst",
    "\u062a\u0634\u0646\u06af\u06cc": "thirst",  # تشنگی
    "motion agg": "motion_agg",
    "worse motion": "motion_agg",
    "\u062d\u0631\u06a9\u062a": "motion_agg",  # حرکت
    "rest agg": "rest_agg",
    "worse rest": "rest_agg",
    "\u0627\u0633\u062a\u0631\u0627\u062d\u062a": "rest_agg",  # استراحت
    # --- PARTICULAR / digestive ---
    "digestive": "digestive",
    "stomach": "digestive",
    "bloating": "digestive",
    "flatulence": "digestive",
    "indigestion": "digestive",
    "\u06af\u0648\u0627\u0631\u0634": "digestive",  # گوارش
    "\u0645\u0639\u062f\u0647": "digestive",  # معده
    "\u0646\u0641\u062e": "digestive",  # نفخ
    "headache": "headache",
    "\u0633\u0631\u062f\u0631\u062f": "headache",  # سردرد
    "right-sided": "right_sided",
    "right side": "right_sided",
    "\u0633\u0645\u062a \u0631\u0627\u0633\u062a": "right_sided",  # سمت راست
    "\u0631\u0627\u0633\u062a": "right_sided",  # راست
    "left-sided": "left_sided",
    "left side": "left_sided",
    "\u0633\u0645\u062a \u0686\u067e": "left_sided",  # سمت چپ
    "\u0686\u067e": "left_sided",  # چپ
    # --- stimulant ---
    "stimulant": "stimulants",
    "coffee": "stimulants",
    "caffeine": "stimulants",
    "alcohol": "stimulants",
    "\u0642\u0647\u0648\u0647": "stimulants",  # قهوه
    "\u0645\u062d\u0631\u06a9": "stimulants",  # محرک
    # --- MIND: depression / sadness ---
    "depression": "depression",
    "depressed": "depression",
    "worthless": "depression",
    "worthlessness": "depression",
    "hopeless": "depression",
    "no value": "depression",
    "\u0627\u0641\u0633\u0631\u062f\u06af\u06cc": "depression",  # افسردگی
    "\u0627\u0641\u0633\u0631\u062f\u0647": "depression",  # افسرده
    "\u0628\u06cc\u200c\u0627\u0631\u0632\u0634": "depression",  # بی‌ارزش
    # --- MIND: suicidal ---
    "suicidal": "suicidal",
    "suicide": "suicidal",
    "end life": "suicidal",
    "life has no value": "suicidal",
    "\u062e\u0648\u062f\u06a9\u0634\u06cc": "suicidal",  # خودکشی
    # --- MIND: guilt ---
    "guilt": "guilt",
    "guilty": "guilt",
    "self-blame": "guilt",
    "self blame": "guilt",
    "reproach": "guilt",
    "\u06af\u0646\u0627\u0647": "guilt",  # گناه
    "\u062e\u0648\u062f\u0633\u0631\u0632\u0646\u0634\u06cc": "guilt",  # خودسرزنشی
    # --- PARTICULAR: flatulence ---
    "flatulence": "flatulence",
    "gas": "flatulence",
    "abdominal gas": "flatulence",
    "\u06af\u0627\u0632": "flatulence",  # گاز
    # --- MIND: contradiction ---
    "contradicted": "contradiction_agg",
    "contradiction": "contradiction_agg",
    "cannot bear contradiction": "contradiction_agg",
    # --- NUX: natural phrasing ---
    "driven": "ambitious",
    "restless pacing": "restlessness",
    "snaps quickly": "irritability",
    "work obsessed": "ambitious",
    "\u0628\u06cc\u200c\u0642\u0631\u0627\u0631": "restlessness",  # بی‌قرار
    "\u0645\u062f\u0627\u0645 \u0631\u0627\u0647 \u0645\u06cc\u200c\u0631\u0648\u062f": "restlessness",  # مدام راه می‌رود
    "\u0648\u0633\u0648\u0627\u0633 \u06a9\u0627\u0631": "ambitious",  # وسواس کار
    # --- ARS: natural phrasing ---
    "immaculately clean": "fastidious",
    "fear something bad will happen": "anxiety",
    "checks repeatedly": "desire_control",
    "health anxious": "anxiety",
    "\u0648\u0633\u0648\u0627\u0633 \u062a\u0645\u06cc\u0632\u06cc": "fastidious",  # وسواس تمیزی
    "\u062a\u0631\u0633 \u0627\u0632 \u0628\u06cc\u0645\u0627\u0631\u06cc": "anxiety",  # ترس از بیماری
    "\u0645\u0631\u062a\u0628 \u0686\u06a9 \u0645\u06cc\u200c\u06a9\u0646\u062f": "desire_control",  # مرتب چک می‌کند
    # --- LYC: natural phrasing ---
    "fear of public speaking": "insecurity",
    "bloating after meals": "flatulence",
    "\u062a\u0631\u0633 \u0627\u0632 \u062c\u0645\u0639": "insecurity",  # ترس از جمع
    "\u0646\u0641\u062e \u0628\u0639\u062f \u063a\u0630\u0627": "flatulence",  # نفخ بعد غذا
    # --- AUR: natural phrasing ---
    "feels worthless": "depression",
    "deep guilt": "guilt",
    "\u0627\u062d\u0633\u0627\u0633 \u0628\u06cc\u200c\u0627\u0631\u0632\u0634\u06cc": "depression",  # احساس بی‌ارزشی
    "\u0639\u0630\u0627\u0628 \u0648\u062c\u062f\u0627\u0646 \u0634\u062f\u06cc\u062f": "guilt",  # عذاب وجدان شدید
    # --- Additional gap coverage ---
    "rushed": "hurry",
    "perpetually rushed": "hurry",
    "cold-natured": "cold_agg",
    "cold natured": "cold_agg",
    "bundles up": "cold_agg",
    "meticulous": "fastidious",
    "spotless": "fastidious",
    "cannot stay still": "restlessness",
    "health anxiety": "anxiety",
    "loses temper": "irritability",
    "loses his temper": "irritability",
    "short-tempered": "irritability",
    "overbearing": "desire_control",
    "relentlessly": "ambitious",
    # --- Extra synonyms for gaps ---
    "domineering": "desire_control",
    "dominating": "desire_control",
    "delegate": "desire_control",
    "timid": "insecurity",
    "cowardly": "insecurity",
    "anger outbursts": "anger_violent",
    "angry outburst": "anger_violent",
    "flies into rage": "anger_violent",
    "violent temper": "anger_violent",
    "craves sweets": "desire_sweet",
    "craving sweets": "desire_sweet",
    "desire for sweets": "desire_sweet",
    "anxious about money": "fear_poverty",
    "worried about money": "fear_poverty",
    "fear of losing": "fear_poverty",
    "anticipatory anxiety": "anticipatory_anxiety",
    "anticipation anxiety": "anticipatory_anxiety",
    "\u0627\u0636\u0637\u0631\u0627\u0628 \u0642\u0628\u0644": "anticipatory_anxiety",  # اضطراب قبل
}


def normalize_persian(text: str) -> str:
    """Layer A: Unicode + half-space + diacritics + whitespace normalization."""
    # NFKC normalization
    text = unicodedata.normalize("NFKC", text)
    # Arabic Kaf/Yeh -> Persian
    text = text.replace("\u0643", "\u06a9")  # ك → ک
    text = text.replace("\u064a", "\u06cc")  # ي → ی
    # Remove diacritics (tashkeel)
    text = _DIACRITICS.sub("", text)
    # Normalize half-spaces: ZWNJ (\u200c) variants
    text = text.replace("\u200c", "\u200c")  # keep real ZWNJ
    # Normalize dashes
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    # Collapse whitespace
    text = _MULTI_SPACE.sub(" ", text).strip()
    return text


def stem_persian(token: str) -> str:
    """Simple Persian stemmer: strip common suffixes/prefixes."""
    t = token.strip()
    for prefix in _FA_PREFIXES:
        if t.startswith(prefix) and len(t) > len(prefix) + 1:
            t = t[len(prefix):]
            break
    for suffix in _FA_SUFFIXES:
        if t.endswith(suffix) and len(t) > len(suffix) + 1:
            t = t[:-len(suffix)]
            break
    return t


def tokenize(text: str) -> list[str]:
    """Split on whitespace + punctuation, return lowered tokens."""
    text = text.lower()
    # Split on non-alphanumeric (keeping Persian chars)
    tokens = re.findall(r"[\w\u0600-\u06FF\u200c]+", text, re.UNICODE)
    return tokens


# ═══════════════════════════════════════════════════════════════
# LAYER B — Semantic Concept Mapping
# ═══════════════════════════════════════════════════════════════

# concept_key → (rubric_string, category)
# category is used for weight assignment in Layer C
CONCEPT_TO_RUBRIC: dict[str, tuple[str, str]] = {
    # MIND concepts
    "fear_poverty":      ("MIND - FEAR - POVERTY, OF", "mind"),
    "desire_control":    ("MIND - CONTROLLING", "mind"),
    "fastidious":        ("MIND - FASTIDIOUS", "mind"),
    "reserved":          ("MIND - RESERVED", "mind"),
    "conscientious":     ("MIND - CONSCIENTIOUS", "mind"),
    "anger_suppressed":  ("MIND - AILMENTS FROM - ANGER", "mind"),
    "anger_violent":     ("MIND - ANGER - VIOLENT", "mind"),
    "ambitious":         ("MIND - AMBITION", "mind"),
    "grief":             ("MIND - GRIEF", "mind"),
    "anxiety":           ("MIND - ANXIETY", "mind"),
    "fear":              ("MIND - FEAR", "mind"),
    "weeping":           ("MIND - WEEPING", "mind"),
    "company_aversion":  ("MIND - COMPANY - AVERSION TO", "mind"),
    "company_desire":    ("MIND - COMPANY - DESIRE FOR", "mind"),
    "consolation":       ("MIND - CONSOLATION - AGG.", "mind"),
    "irritability":      ("MIND - IRRITABILITY", "mind"),
    "insecurity":        ("MIND - CONFIDENCE - WANT OF SELF", "mind"),
    "jealousy":          ("MIND - JEALOUSY", "mind"),
    "hurry":             ("MIND - HURRY", "mind"),
    "indifference":      ("MIND - INDIFFERENCE", "mind"),
    "restlessness":      ("MIND - RESTLESSNESS", "mind"),
    # SLEEP concepts
    "insomnia":          ("SLEEP - SLEEPLESSNESS", "generals"),
    "nightmares":        ("SLEEP - DREAMS - FRIGHTFUL", "generals"),
    "waking_midnight":   ("SLEEP - WAKING - MIDNIGHT", "generals"),
    "waking_early":      ("SLEEP - WAKING - EARLY", "generals"),
    "grinding_teeth":    ("TEETH - GRINDING", "particular"),
    "talking_sleep":     ("SLEEP - TALKING - SLEEP, IN", "generals"),
    # GENERALS concepts
    "heat_agg":          ("GENERALS - HEAT - AGG.", "generals"),
    "cold_agg":          ("GENERALS - COLD - AGG.", "generals"),
    "desire_sour":       ("GENERALS - FOOD AND DRINKS - SOUR, ACIDS - DESIRE", "generals"),
    "desire_sweet":      ("GENERALS - FOOD AND DRINKS - SWEETS - DESIRE", "generals"),
    "desire_salt":       ("GENERALS - FOOD AND DRINKS - SALT - DESIRE", "generals"),
    "perspiration_offensive": ("PERSPIRATION - ODOR - OFFENSIVE", "generals"),
    "thirst":            ("GENERALS - THIRST", "generals"),
    "motion_agg":        ("GENERALS - MOTION - AGG.", "generals"),
    "rest_agg":          ("GENERALS - REST - AGG.", "generals"),
    # PARTICULAR
    "digestive":         ("STOMACH - COMPLAINTS OF STOMACH", "particular"),
    "headache":          ("HEAD - PAIN", "particular"),
    "right_sided":       ("GENERALS - SIDE - RIGHT", "particular"),
    "left_sided":        ("GENERALS - SIDE - LEFT", "particular"),
    "stimulants":        ("GENERALS - FOOD AND DRINKS - STIMULANTS - AGG.", "generals"),
    # New concepts for calibration
    "depression":        ("MIND - SADNESS", "mind"),
    "suicidal":          ("MIND - SUICIDAL DISPOSITION", "mind"),
    "guilt":             ("MIND - REPROACHING ONESELF", "mind"),
    "flatulence":        ("ABDOMEN - FLATULENCE", "particular"),
    "contradiction_agg": ("MIND - CONTRADICTION - AGG.", "mind"),
    "anticipatory_anxiety": ("MIND - ANXIETY - ANTICIPATORY", "mind"),
}

# Regex-based concept detectors for patterns not easily caught by synonym map
REGEX_CONCEPTS: list[tuple[re.Pattern, str]] = [
    # English patterns
    (re.compile(r"\bgrief\b|\bbereavement\b|\bmourning\b|\bloss\s+of\s+(?:loved|parent|child|spouse)", re.I), "grief"),
    (re.compile(r"\banxi(?:ety|ous)\b|\bworr(?:y|ied)\b|\bapprehens", re.I), "anxiety"),
    (re.compile(r"\bfear\s+(?:of\s+)?(?:poverty|ruin|bankrupt|financial|money)", re.I), "fear_poverty"),
    (re.compile(r"\bfear\b|\bafraid\b|\bphobia\b", re.I), "fear"),
    (re.compile(r"\bcontrol(?:ling)?\b|\bneed\s+to\s+control\b", re.I), "desire_control"),
    (re.compile(r"\border(?:liness)?\b|\bcleanli|\bneat\b|\btidy\b|\bfastidious\b|\bperfection|\bmeticulous\b|\bspotless\b", re.I), "fastidious"),
    (re.compile(r"\bintrovert|\breserved\b|\bwithdrawn\b|\bshy\b|\bclosed\s+off\b", re.I), "reserved"),
    (re.compile(r"\bresponsib|\bconscientious\b|\bduty\b|\bdiligent\b", re.I), "conscientious"),
    (re.compile(r"\bsuppress(?:ed)?\s+anger\b|\banger\s+suppress|\bholds?\s+anger\b|\banger\s+inside\b", re.I), "anger_suppressed"),
    (re.compile(r"\bexplosive\s+anger\b|\bviolent\s+anger\b|\brage\b|\banger\s+explosive\b", re.I), "anger_violent"),
    (re.compile(r"\bambiti(?:on|ous)\b|\bbusiness|\bworkaholic\b|\bcareer\b|\bcompetitiv|\brelentless(?:ly)?\b|\bdriven\b|\boverwork", re.I), "ambitious"),
    (re.compile(r"\bweep(?:ing)?\b|\bcry(?:ing)?\b|\btearful\b", re.I), "weeping"),
    (re.compile(r"\balone\b|\bsolitude\b", re.I), "company_aversion"),
    (re.compile(r"\bcompany\b.*\bdesire\b|\bdesire\b.*\bcompany\b|\bsocial\b", re.I), "company_desire"),
    (re.compile(r"\bconsolation\b", re.I), "consolation"),
    (re.compile(r"\birritab(?:le|ility)\b|\bimpatien(?:t|ce)\b|\bshort[\s-]temper(?:ed)?\b|\bloses?\s+(?:his|her|their|my)?\s*temper\b|\boverbearing\b", re.I), "irritability"),
    (re.compile(r"\binsecur(?:e|ity)\b|\black\s+of\s+confidence\b|\bself-doubt\b", re.I), "insecurity"),
    (re.compile(r"\bjealous(?:y)?\b|\benvy\b", re.I), "jealousy"),
    (re.compile(r"\bhurry\b|\bhasty\b|\bimpatience\b|\brush(?:ed|ing)?\b|\bperpetually\s+rush", re.I), "hurry"),
    (re.compile(r"\bindifferen(?:ce|t)\b|\bapath(?:y|etic)\b", re.I), "indifference"),
    (re.compile(r"\brestless(?:ness)?\b|\brestless\s+pacing\b|\bpaces?\s+(?:the\s+)?(?:room|house|floor)|\bcannot\s+stay\s+still\b|\bcan(?:not|'t)\s+sit\s+still\b", re.I), "restlessness"),
    (re.compile(r"\bdriven\b|\bwork[\s-]obsessed\b|\bworkaholic\b", re.I), "ambitious"),
    (re.compile(r"\bsnaps?\s+quickly\b|\bsnaps?\s+at\b", re.I), "irritability"),
    (re.compile(r"\bimmaculate(?:ly)?\s+clean\b|\bobsessive(?:ly)?\s+clean\b", re.I), "fastidious"),
    (re.compile(r"\bchecks?\s+repeat(?:edly)?\b|\bdouble[\s-]checks?\b", re.I), "desire_control"),
    (re.compile(r"\bhealth[\s-]?anxi(?:ous|ety)\b|\bfear\s+(?:something\s+bad|of\s+illness|of\s+disease|of\s+getting\s+sick)|\bhealth\s+anxiety\b", re.I), "anxiety"),
    (re.compile(r"\bfear\s+of\s+public\s+speaking\b|\bpublic\s+speaking\s+fear\b", re.I), "insecurity"),
    (re.compile(r"\bbloat(?:ing)?\s+after\s+(?:meals?|eating|food)\b|\bpost[\s-]meal\s+bloat", re.I), "flatulence"),
    (re.compile(r"\bfeels?\s+worthless\b|\bfeeling\s+worthless\b", re.I), "depression"),
    (re.compile(r"\bdeep\s+guilt\b|\bintense\s+guilt\b|\boverwhelming\s+guilt\b", re.I), "guilt"),
    (re.compile(r"\binsomnia\b|\bsleepless(?:ness)?\b", re.I), "insomnia"),
    (re.compile(r"\bnightmare\b", re.I), "nightmares"),
    (re.compile(r"\bmidnight\b", re.I), "waking_midnight"),
    (re.compile(r"\bearly\s+(?:morning|waking)\b", re.I), "waking_early"),
    (re.compile(r"\bbruxism\b|\bteeth?\s+grind|\bgrind(?:ing)?\s+teeth\b", re.I), "grinding_teeth"),
    (re.compile(r"\bsleep\s+talk|\btalk(?:ing)?\s+in\s+sleep\b", re.I), "talking_sleep"),
    (re.compile(r"\bwarm[\s-]+(?:blooded|patient)\b|\bworse\s+(?:in\s+)?heat\b|\bhot\s+patient\b", re.I), "heat_agg"),
    (re.compile(r"\bchilly\b|\bcold[\s-]+(?:blooded|patient|natured)\b|\bworse\s+(?:in\s+)?cold\b|\bbundles?\s+up\b|\bwraps?\s+(?:up|herself|himself)", re.I), "cold_agg"),
    (re.compile(r"\bdesire\s+sour\b|\bsour\s+food\b|\bcraving\s+sour\b", re.I), "desire_sour"),
    (re.compile(r"\bdesire\s+sweet\b|\bsweet\s+craving\b|\bcraving\s+sweet\b", re.I), "desire_sweet"),
    (re.compile(r"\bdesire\s+salt\b|\bsalt(?:y)?\s+(?:food|craving)\b", re.I), "desire_salt"),
    (re.compile(r"\boffensive\s+sweat\b|\bsmelly\s+sweat\b", re.I), "perspiration_offensive"),
    (re.compile(r"\bthirst(?:y)?\b", re.I), "thirst"),
    (re.compile(r"\bworse\s+motion\b|\bmotion\s+agg\b", re.I), "motion_agg"),
    (re.compile(r"\bworse\s+rest\b|\brest\s+agg\b", re.I), "rest_agg"),
    (re.compile(r"\bdigestiv|\bstomach\b|\bbloat|\bflatulenc|\bindigest", re.I), "digestive"),
    (re.compile(r"\bheadache\b|\bhead\s+pain\b", re.I), "headache"),
    (re.compile(r"\bright[\s-]+side[d]?\b", re.I), "right_sided"),
    (re.compile(r"\bleft[\s-]+side[d]?\b", re.I), "left_sided"),
    (re.compile(r"\bstimulant|\bcoffee\b|\bcaffeine\b|\balcohol\b", re.I), "stimulants"),
    # Persian regex patterns
    (re.compile(r"\u063a\u0645|\u0633\u0648\u06af|\u0639\u0632\u0627\u062f\u0627\u0631", re.I), "grief"),  # غم سوگ عزادار
    (re.compile(r"\u0627\u0636\u0637\u0631\u0627\u0628|\u0646\u06af\u0631\u0627\u0646|\u062f\u0644\u0634\u0648\u0631\u0647", re.I), "anxiety"),  # اضطراب نگران دلشوره
    (re.compile(r"\u062a\u0631\u0633.*(?:\u0641\u0642\u0631|\u0645\u0627\u0644|\u0648\u0631\u0634\u06a9\u0633\u062a)", re.I), "fear_poverty"),  # ترس...فقر/مال/ورشکست
    (re.compile(r"\u062a\u0631\u0633\s+\u0627\u0632\s+\u0628\u06cc\u0645\u0627\u0631\u06cc", re.I), "anxiety"),  # ترس از بیماری
    (re.compile(r"\u062a\u0631\u0633|\u0648\u062d\u0634\u062a|\u0641\u0648\u0628\u06cc\u0627", re.I), "fear"),  # ترس وحشت فوبیا
    (re.compile(r"\u06a9\u0646\u062a\u0631\u0644", re.I), "desire_control"),  # کنترل
    (re.compile(r"\u0646\u0638\u0645|\u062a\u0645\u06cc\u0632|\u0648\u0633\u0648\u0627\u0633|\u06a9\u0645\u0627\u0644|\u0648\u0633\u0648\u0627\u0633\s+\u062a\u0645\u06cc\u0632\u06cc", re.I), "fastidious"),  # نظم تمیز وسواس کمال / وسواس تمیزی
    (re.compile(r"\u062f\u0631\u0648\u0646\u200c?\u06af\u0631\u0627|\u06a9\u0645\u200c?\u062d\u0631\u0641", re.I), "reserved"),  # درون‌گرا کم‌حرف
    (re.compile(r"\u0645\u0633\u0626\u0648\u0644\u06cc\u062a|\u0648\u0638\u06cc\u0641\u0647", re.I), "conscientious"),  # مسئولیت وظیفه
    (re.compile(r"\u062e\u0634\u0645.*\u0641\u0631\u0648\u062e\u0648\u0631\u062f\u0647|\u0639\u0635\u0628\u0627\u0646\u06cc\u062a.*\u067e\u0646\u0647\u0627\u0646", re.I), "anger_suppressed"),
    (re.compile(r"\u062e\u0634\u0645.*\u0627\u0646\u0641\u062c\u0627\u0631|\u0639\u0635\u0628\u0627\u0646\u06cc\u062a.*\u0634\u062f\u06cc\u062f", re.I), "anger_violent"),
    (re.compile(r"\u062e\u0634\u0645|\u0639\u0635\u0628\u0627\u0646", re.I), "irritability"),  # خشم عصبان
    (re.compile(r"\u062c\u0627\u0647\u200c?\u0637\u0644\u0628|\u0648\u0633\u0648\u0627\u0633\s+\u06a9\u0627\u0631", re.I), "ambitious"),  # جاه‌طلب / وسواس کار
    (re.compile(r"\u06af\u0631\u06cc\u0647", re.I), "weeping"),  # گریه
    (re.compile(r"\u062a\u0646\u0647\u0627", re.I), "company_aversion"),  # تنها
    (re.compile(r"\u062f\u0644\u062f\u0627\u0631\u06cc", re.I), "consolation"),  # دلداری
    (re.compile(r"\u0628\u06cc\u200c?\u062e\u0648\u0627\u0628\u06cc", re.I), "insomnia"),  # بی‌خوابی
    (re.compile(r"\u06a9\u0627\u0628\u0648\u0633", re.I), "nightmares"),  # کابوس
    (re.compile(r"\u0646\u06cc\u0645\u0647\u200c?\u0634\u0628", re.I), "waking_midnight"),  # نیمه‌شب
    (re.compile(r"\u0633\u062d\u0631|\u0635\u0628\u062d \u0632\u0648\u062f", re.I), "waking_early"),  # سحر صبح زود
    (re.compile(r"\u06af\u0631\u0645\u0627?\u06cc?\u06cc?", re.I), "heat_agg"),  # گرم گرما گرمایی
    (re.compile(r"\u0633\u0631\u062f|\u0633\u0631\u0645\u0627", re.I), "cold_agg"),  # سرد سرما
    (re.compile(r"\u062a\u0631\u0634", re.I), "desire_sour"),  # ترش
    (re.compile(r"\u0634\u06cc\u0631\u06cc\u0646", re.I), "desire_sweet"),  # شیرین
    (re.compile(r"\u0646\u0645\u06a9", re.I), "desire_salt"),  # نمک
    (re.compile(r"\u0639\u0631\u0642.*\u0628\u062f\u0628\u0648", re.I), "perspiration_offensive"),  # عرق بدبو
    (re.compile(r"\u062a\u0634\u0646\u0647", re.I), "thirst"),  # تشنه
    (re.compile(r"\u062d\u0631\u06a9\u062a", re.I), "motion_agg"),  # حرکت
    (re.compile(r"\u0627\u0633\u062a\u0631\u0627\u062d\u062a", re.I), "rest_agg"),  # استراحت
    (re.compile(r"\u06af\u0648\u0627\u0631\u0634|\u0645\u0639\u062f\u0647|\u0646\u0641\u062e", re.I), "digestive"),  # گوارش معده نفخ
    (re.compile(r"\u0646\u0641\u062e\s+\u0628\u0639\u062f\s+\u063a\u0630\u0627", re.I), "flatulence"),  # نفخ بعد غذا
    (re.compile(r"\u0633\u0631\u062f\u0631\u062f", re.I), "headache"),  # سردرد
    (re.compile(r"\u0631\u0627\u0633\u062a", re.I), "right_sided"),  # راست
    (re.compile(r"\u0686\u067e", re.I), "left_sided"),  # چپ
    (re.compile(r"\u0628\u06cc\u200c?\u0642\u0631\u0627\u0631|\u0645\u062f\u0627\u0645\s+\u0631\u0627\u0647\s+\u0645\u06cc\u200c?\u0631\u0648\u062f", re.I), "restlessness"),  # بی‌قرار / مدام راه می‌رود
    (re.compile(r"\u062d\u0633\u0627\u062f\u062a", re.I), "jealousy"),  # حسادت
    (re.compile(r"\u0639\u062c\u0644\u0647", re.I), "hurry"),  # عجله
    (re.compile(r"\u0628\u06cc\u200c?\u062a\u0641\u0627\u0648\u062a", re.I), "indifference"),  # بی‌تفاوت
    (re.compile(r"\u0642\u0647\u0648\u0647|\u0645\u062d\u0631\u06a9", re.I), "stimulants"),  # قهوه محرک
    (re.compile(r"\u0646\u0627\u0627\u0645\u0646|\u0628\u06cc\u200c?\u0627\u0639\u062a\u0645\u0627\u062f|\u062a\u0631\u0633\s+\u0627\u0632\s+\u062c\u0645\u0639", re.I), "insecurity"),  # ناامن بی‌اعتماد / ترس از جمع
    (re.compile(r"\u0632\u0648\u062f\u0631\u0646\u062c|\u0628\u06cc\u200c?\u062d\u0648\u0635\u0644\u0647|\u062a\u062d\u0631\u06cc\u06a9\u200c?\u067e\u0630\u06cc\u0631", re.I), "irritability"),  # زودرنج بی‌حوصله تحریک‌پذیر
    # --- New patterns for calibration ---
    (re.compile(r"\bdepress(?:ion|ed)\b|\bworthless(?:ness)?\b|\bhopeless(?:ness)?\b|\bno\s+value\b", re.I), "depression"),
    (re.compile(r"\bsuicid(?:al|e)\b|\bend\s+(?:his|her|my)?\s*life\b|\blife\s+has\s+no\s+value\b", re.I), "suicidal"),
    (re.compile(r"\bguilt(?:y)?\b|\bself[\s-]+blam|\breproach|\bself[\s-]+reproach", re.I), "guilt"),
    (re.compile(r"\bflatulenc|\babdominal\s+gas\b|\bgas\s+after\b|\bpassing\s+gas\b", re.I), "flatulence"),
    (re.compile(r"\bcontradict(?:ed|ion)?\b|\bcannot\s+bear\s+contradict", re.I), "contradiction_agg"),
    (re.compile(r"\banticipat(?:ory|ion)\s+anxi", re.I), "anticipatory_anxiety"),
    (re.compile(r"\bdesire\s+(?:for\s+)?sweets?\b|\bcrav(?:es?|ing)\s+sweets?\b|\bsweet\s+(?:tooth|craving)\b", re.I), "desire_sweet"),
    (re.compile(r"\banxious\s+about\s+money\b|\bworried\s+about\s+money\b|\bfear\s+of\s+losing\b", re.I), "fear_poverty"),
    (re.compile(r"\banger\s+outburst|\bflies?\s+into\s+rage\b|\bviolent\s+temper\b|\brage\s+at\b", re.I), "anger_violent"),
    (re.compile(r"\bdomineering\b|\bdominating\b|\bcannot\s+delegate\b", re.I), "desire_control"),
    (re.compile(r"\btimid\b|\bcoward(?:ly|ice)?\b", re.I), "insecurity"),
    (re.compile(r"\u0627\u0641\u0633\u0631\u062f|\u0628\u06cc\u200c?\u0627\u0631\u0632\u0634|\u0627\u062d\u0633\u0627\u0633\s+\u0628\u06cc\u200c?\u0627\u0631\u0632\u0634\u06cc", re.I), "depression"),  # افسرد بی‌ارزش / احساس بی‌ارزشی
    (re.compile(r"\u062e\u0648\u062f\u06a9\u0634\u06cc", re.I), "suicidal"),  # خودکشی
    (re.compile(r"\u06af\u0646\u0627\u0647|\u062e\u0648\u062f\u0633\u0631\u0632\u0646\u0634|\u0639\u0630\u0627\u0628\s+\u0648\u062c\u062f\u0627\u0646", re.I), "guilt"),  # گناه خودسرزنش / عذاب وجدان
]


def extract_concepts(text: str) -> dict[str, int]:
    """
    Layer B: Extract concept keys with frequency counts.
    Uses synonym map (token + bigram + trigram) and regex patterns.
    Returns {concept_key: occurrence_count}.
    """
    norm = normalize_persian(text)
    low = norm.lower()
    tokens = tokenize(norm)
    stemmed = [stem_persian(t) for t in tokens]

    found: dict[str, int] = {}

    def _add(key: str) -> None:
        found[key] = found.get(key, 0) + 1

    # --- Synonym map: check tokens, bigrams, trigrams ---
    all_tokens = tokens + stemmed
    # Check single tokens
    for t in all_tokens:
        if t in SYNONYM_MAP:
            _add(SYNONYM_MAP[t])

    # Check bigrams
    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]} {tokens[i+1]}"
        if bigram in SYNONYM_MAP:
            _add(SYNONYM_MAP[bigram])
        # stemmed bigram
        sbigram = f"{stemmed[i]} {stemmed[i+1]}"
        if sbigram in SYNONYM_MAP and sbigram != bigram:
            _add(SYNONYM_MAP[sbigram])

    # Check trigrams
    for i in range(len(tokens) - 2):
        trigram = f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}"
        if trigram in SYNONYM_MAP:
            _add(SYNONYM_MAP[trigram])

    # --- Regex patterns ---
    for pattern, concept_key in REGEX_CONCEPTS:
        matches = pattern.findall(low)
        if matches:
            _add(concept_key)

    return found


# ═══════════════════════════════════════════════════════════════
# LAYER C — Weighted Rubric Construction
# ═══════════════════════════════════════════════════════════════

CATEGORY_WEIGHTS: dict[str, float] = {
    "mind": 2.2,
    "generals": 1.4,
    "particular": 1.0,
}


def build_weighted_rubrics(concepts: dict[str, int]) -> list[dict[str, Any]]:
    """
    Convert concept keys to weighted rubric entries.
    Weight = category_base_weight * occurrence_count.
    Returns list of {rubric, category, weight, concept_key}.
    """
    rubrics: list[dict[str, Any]] = []
    seen: set[str] = set()

    for concept_key, count in concepts.items():
        if concept_key not in CONCEPT_TO_RUBRIC:
            continue
        rubric_str, category = CONCEPT_TO_RUBRIC[concept_key]
        if rubric_str in seen:
            # If same rubric already added, boost its weight
            for entry in rubrics:
                if entry["rubric"] == rubric_str:
                    entry["weight"] += CATEGORY_WEIGHTS.get(category, 1.0) * (count - 1)
                    break
            continue
        seen.add(rubric_str)
        base_weight = CATEGORY_WEIGHTS.get(category, 1.0)
        rubrics.append({
            "rubric": rubric_str,
            "category": category,
            "weight": base_weight * count,
            "concept_key": concept_key,
        })

    return rubrics


# ═══════════════════════════════════════════════════════════════
# PHASE 4 — Differentiation Enhancement
# ═══════════════════════════════════════════════════════════════

# Cluster definitions: (name, indicators, min_match, boost_rubrics, bonus_rubrics)
# bonus_rubrics: extra rubrics INJECTED when cluster activates — high-specificity paths
DIFFERENTIATION_CLUSTERS: list[tuple[str, set[str], int, list[str], list[tuple[str, str]]]] = [
    # Ars cluster
    (
        "ars",
        {"desire_control", "fear_poverty", "fastidious", "restlessness", "cold_agg"},
        2,
        ["MIND - FEAR - POVERTY, OF", "MIND - FASTIDIOUS",
         "MIND - ANXIETY", "MIND - RESTLESSNESS", "GENERALS - COLD - AGG."],
        [  # bonus: ars degree=4, specific
            ("MIND - AVARICE", "mind"),                    # 45 rems, ars=4
            ("MIND - FEAR - DEATH, OF", "mind"),            # 257 rems, ars=4
            ("MIND - ANGUISH", "mind"),                     # 206 rems, ars=4
            ("MIND - SADNESS - ALONE - WHEN", "mind"),      # 37 rems, ars=4
            ("MIND - FEAR - ROBBERS, OF", "mind"),           # 44 rems, ars=4
        ],
    ),
    # Nux cluster
    (
        "nux",
        {"ambitious", "irritability", "stimulants", "hurry", "anger_violent", "contradiction_agg"},
        2,
        ["MIND - IRRITABILITY", "MIND - ANGER - VIOLENT",
         "GENERALS - FOOD AND DRINKS - STIMULANTS - AGG.", "MIND - HURRY"],
        [  # bonus: nux-v degree=4, specific
            ("MIND - AILMENTS FROM - MENTAL EXERTION", "mind"),   # 69 rems, nux-v=4
            ("MIND - AILMENTS FROM - ANGER", "mind"),              # 146 rems, nux-v=4
            ("MIND - ANGER", "mind"),                              # 427 rems, nux-v=4
            ("MIND - CONCENTRATION - DIFFICULT", "mind"),          # 433 rems, nux-v=4
        ],
    ),
    # Lyc cluster
    (
        "lyc",
        {"insecurity", "digestive", "right_sided", "desire_sweet", "flatulence", "anticipatory_anxiety"},
        2,
        ["MIND - CONFIDENCE - WANT OF SELF", "ABDOMEN - FLATULENCE",
         "GENERALS - SIDE - RIGHT", "GENERALS - FOOD AND DRINKS - SWEETS - DESIRE"],
        [  # bonus: lyc degree=3-4, specific
            ("MIND - HAUGHTY", "mind"),                                     # 136 rems, lyc=4
            ("MIND - FEAR - PEOPLE; OF", "mind"),                            # 132 rems, lyc=4
            ("MIND - CONTRADICTION - INTOLERANT OF CONTRADICTION", "mind"),  # 129 rems, lyc=4
            ("MIND - INSOLENCE", "mind"),                                   # 48 rems, lyc=4
            ("MIND - SUSPICIOUS", "mind"),                                  # 148 rems, lyc=4
            ("MIND - IRRESOLUTION - TRIFLES, ABOUT", "mind"),               # 17 rems, lyc=3 (very specific!)
            ("MIND - COWARDICE", "mind"),                                   # 103 rems, lyc=3
        ],
    ),
    # Aur cluster
    (
        "aur",
        {"grief", "conscientious", "anger_suppressed", "depression", "guilt", "reserved"},
        2,
        ["MIND - GRIEF", "MIND - SADNESS", "MIND - SUICIDAL DISPOSITION",
         "MIND - AILMENTS FROM - ANGER", "MIND - RESERVED"],
        [  # bonus: aur degree=4, specific
            ("MIND - DESPAIR", "mind"),                           # 252 rems, aur=4
            ("MIND - ANXIETY - CONSCIENCE; ANXIETY OF", "mind"),  # 124 rems, aur=4
            ("MIND - ANGER - VIOLENT", "mind"),                   # 111 rems, aur=4
        ],
    ),
]

BOOST_MULTIPLIER = 3.0
BONUS_WEIGHT = 6.0  # multiplier for bonus rubric base weight


def apply_differentiation(concepts: dict[str, int], rubrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Phase 4: If enough of a cluster's indicator concepts are present (>= min_match),
    boost weight of matching rubrics and inject bonus rubrics.
    Does NOT hardcode remedy — only modifies rubric weights.
    """
    concept_keys = set(concepts.keys())
    rubric_map = {r["rubric"]: r for r in rubrics}

    for cluster_name, indicators, min_match, boost_rubrics, bonus_rubrics in DIFFERENTIATION_CLUSTERS:
        overlap = indicators & concept_keys
        if len(overlap) >= min_match:
            _log.info("Differentiation cluster '%s' activated (matched %d/%d: %s)",
                      cluster_name, len(overlap), len(indicators), sorted(overlap))
            # Boost existing rubrics
            for br in boost_rubrics:
                if br in rubric_map:
                    rubric_map[br]["weight"] *= BOOST_MULTIPLIER
            # Inject bonus rubrics (highly-specific remedy-indicative paths)
            for rubric_str, category in bonus_rubrics:
                if rubric_str not in rubric_map:
                    base_weight = CATEGORY_WEIGHTS.get(category, 1.0)
                    entry = {
                        "rubric": rubric_str,
                        "category": category,
                        "weight": base_weight * BONUS_WEIGHT,
                        "concept_key": f"_bonus_{cluster_name}",
                    }
                    rubrics.append(entry)
                    rubric_map[rubric_str] = entry
                    _log.info("  Bonus rubric injected: %s (weight=%.1f)", rubric_str, entry["weight"])

    return rubrics


# ═══════════════════════════════════════════════════════════════
# PHASE 2 — Accurate DB Mapping
# ═══════════════════════════════════════════════════════════════

def map_rubric_to_symptom_id(cur: sqlite3.Cursor, rubric: str) -> tuple[int | None, str | None, str]:
    """
    Map rubric string to symptom_id using:
    1) syntree.search_path exact (case-insensitive)
    2) syntree.search_path LIKE shortest match
    3) cross_references.text exact
    4) cross_references.text LIKE shortest match

    All rubric strings must be uppercase with dash-separated path segments.
    """
    q = rubric.strip().upper()

    # 1) syntree exact
    cur.execute("SELECT id, search_path FROM syntree WHERE upper(search_path) = ? LIMIT 1", (q,))
    row = cur.fetchone()
    if row:
        return int(row[0]), row[1], "syntree_exact"

    # 2) syntree LIKE shortest match
    cur.execute(
        "SELECT id, search_path FROM syntree WHERE upper(search_path) LIKE ? ORDER BY LENGTH(search_path) ASC LIMIT 1",
        (f"%{q}%",),
    )
    row = cur.fetchone()
    if row:
        return int(row[0]), row[1], "syntree_like"

    # 2b) syntree token search: split on " - " and search each segment >= 4 chars
    for token in [t.strip() for t in q.split(" - ") if len(t.strip()) >= 4]:
        cur.execute(
            "SELECT id, search_path FROM syntree WHERE upper(search_path) LIKE ? ORDER BY LENGTH(search_path) ASC LIMIT 1",
            (f"%{token}%",),
        )
        row = cur.fetchone()
        if row:
            return int(row[0]), row[1], f"syntree_token:{token}"

    # 3) cross_references exact
    cur.execute("SELECT symptom_id, text FROM cross_references WHERE upper(text) = ? LIMIT 1", (q,))
    row = cur.fetchone()
    if row:
        return int(row[0]), row[1], "xref_exact"

    # 4) cross_references LIKE shortest match
    cur.execute(
        "SELECT symptom_id, text FROM cross_references WHERE upper(text) LIKE ? ORDER BY LENGTH(text) ASC LIMIT 1",
        (f"%{q}%",),
    )
    row = cur.fetchone()
    if row:
        return int(row[0]), row[1], "xref_like"

    return None, None, "not_found"


def map_all_rubrics(rubrics: list[dict[str, Any]], db_path: str | None = None) -> list[dict[str, Any]]:
    """Map all rubric entries to symptom_ids. Mutates entries in-place."""
    _db = db_path or DB_PATH
    con = sqlite3.connect(_db)
    try:
        cur = con.cursor()
        for entry in rubrics:
            sid, matched, method = map_rubric_to_symptom_id(cur, entry["rubric"])
            entry["symptom_id"] = sid
            entry["matched_text"] = matched
            entry["method"] = method
        return rubrics
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════
# PUBLIC API — build_clinical_case
# ═══════════════════════════════════════════════════════════════

def build_clinical_case(
    narrative: str,
    db_path: str | None = None,
) -> dict[str, Any]:
    """
    Full clinical extraction pipeline:
      narrative → concepts → weighted rubrics → DB mapping → weighted case_df

    Returns:
      {
        "rubrics": list[str],
        "rubric_details": list[dict],   # full detail per rubric
        "weighted_case_df": pd.DataFrame(symptom_id, weight),
        "concepts": dict[str, int],
        "mind_count": int,
        "clusters_active": list[str],
      }
    """
    # Layer A + B: extract semantic concepts
    concepts = extract_concepts(narrative)
    if not concepts:
        return {
            "rubrics": [],
            "rubric_details": [],
            "weighted_case_df": pd.DataFrame(columns=["symptom_id", "weight"]),
            "concepts": {},
            "mind_count": 0,
            "clusters_active": [],
        }

    # Layer C: build weighted rubrics
    rubric_entries = build_weighted_rubrics(concepts)

    # Phase 4: differentiation enhancement
    rubric_entries = apply_differentiation(concepts, rubric_entries)

    # Track active clusters
    concept_keys = set(concepts.keys())
    clusters_active = []
    for cluster_name, indicators, min_match, *_ in DIFFERENTIATION_CLUSTERS:
        if len(indicators & concept_keys) >= min_match:
            clusters_active.append(cluster_name)

    # Phase 2: DB mapping
    _db = db_path or DB_PATH
    rubric_entries = map_all_rubrics(rubric_entries, _db)

    # Phase 2b: Filter dead-end symptom_ids (parent nodes with 0 remedy associations)
    _con = sqlite3.connect(_db)
    try:
        _cur = _con.cursor()
        sids = [e["symptom_id"] for e in rubric_entries if e.get("symptom_id") is not None]
        if sids:
            ph = ",".join("?" * len(sids))
            _cur.execute(f"SELECT DISTINCT symptom_id FROM symptom_remedies WHERE symptom_id IN ({ph})", sids)
            valid_sids = {r[0] for r in _cur.fetchall()}
            for entry in rubric_entries:
                sid = entry.get("symptom_id")
                if sid is not None and sid not in valid_sids:
                    _log.debug("Dead-end filtered: sid=%d rubric=%s", sid, entry["rubric"])
                    entry["symptom_id"] = None
                    entry["method"] = "dead_end_filtered"
    finally:
        _con.close()

    # Build weighted case_df (only mapped rubrics with valid symptom_ids)
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for entry in rubric_entries:
        sid = entry.get("symptom_id")
        if sid is not None and sid not in seen_ids:
            seen_ids.add(sid)
            rows.append({"symptom_id": int(sid), "weight": float(entry["weight"])})

    case_df = pd.DataFrame(rows, columns=["symptom_id", "weight"]) if rows else pd.DataFrame(columns=["symptom_id", "weight"])

    rubric_strs = [e["rubric"] for e in rubric_entries]
    mind_count = sum(1 for e in rubric_entries if e.get("category") == "mind")

    _log.info(
        "Clinical extraction: %d concepts → %d rubrics (%d mind) → %d symptom_ids, clusters=%s",
        len(concepts), len(rubric_entries), mind_count, len(rows), clusters_active,
    )

    return {
        "rubrics": rubric_strs,
        "rubric_details": rubric_entries,
        "weighted_case_df": case_df,
        "concepts": concepts,
        "mind_count": mind_count,
        "clusters_active": clusters_active,
    }
