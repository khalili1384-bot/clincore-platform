from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from clincore.mcare_engine.mcare_sqlite_engine_v6_1 import score_case, load_params
from clincore.mcare_engine.case_logger import log_case

DB_PATH = r"src/clincore/mcare_engine/data/synthesis.db"
PARAMS_PATH = r"src/clincore/mcare_engine/mcare_config_v6_1.json"

router = APIRouter()

# --- template env ---
tpl_dir = Path(__file__).parent / "templates"
env = Environment(
    loader=FileSystemLoader(str(tpl_dir)),
    autoescape=select_autoescape(["html", "xml"]),
)

def _norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("–", "-").replace("—", "-")
    return s

# --- Rule-based rubric extractor (MIND-first, no AI, no hallucination) ---
@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern
    rubric: str

MIND_RULES = [
    Rule(re.compile(r"(غم|سوگ|فوت|عزاداری|grief|bereav)", re.I), "MIND - grief - ailments from"),
    Rule(re.compile(r"(اضطراب|نگران|دلشوره|anxiety)", re.I), "MIND - anxiety"),
    Rule(re.compile(r"(ترس|fear|phobia)", re.I), "MIND - fear"),
    Rule(re.compile(r"(تنهایی|alone|تنها)", re.I), "MIND - company - aversion to"),
    Rule(re.compile(r"(جمع|مهمانی|social|company)", re.I), "MIND - company - desire for"),
    Rule(re.compile(r"(دلداری|consolation|دلداری دادن)", re.I), "MIND - consolation"),
    Rule(re.compile(r"(گریه|weeping|cry)", re.I), "MIND - weeping"),
    Rule(re.compile(r"(عصبان|خشم|anger|irritab)", re.I), "MIND - anger"),
]

SLEEP_RULES = [
    Rule(re.compile(r"(بیخوابی|insomnia)", re.I), "SLEEP - sleeplessness"),
    Rule(re.compile(r"(کابوس|nightmare)", re.I), "SLEEP - dreams - frightful"),
    Rule(re.compile(r"(نیمه.?شب|midnight|ساعت ?2|ساعت ?3)", re.I), "SLEEP - waking - midnight"),
    Rule(re.compile(r"(صبح زود|early|سحر)", re.I), "SLEEP - waking - early"),
]

GEN_RULES = [
    Rule(re.compile(r"(سرد|cold|سرما)", re.I), "GENERALS - cold - aggravates"),
    Rule(re.compile(r"(گرم|heat|گرما)", re.I), "GENERALS - heat - aggravates"),
    Rule(re.compile(r"(حرکت|motion|walking)", re.I), "GENERALS - motion - aggravates"),
    Rule(re.compile(r"(استراحت|rest)", re.I), "GENERALS - rest - aggravates"),
]

def extract_rubrics(narrative: str, max_n: int = 10) -> list[str]:
    text = narrative or ""
    out: list[str] = []

    def add(r: str) -> None:
        if r not in out:
            out.append(r)

    # MIND first
    for rule in MIND_RULES:
        if rule.pattern.search(text):
            add(rule.rubric)

    # Sleep
    for rule in SLEEP_RULES:
        if rule.pattern.search(text):
            add(rule.rubric)

    # Generals / modalities
    for rule in GEN_RULES:
        if rule.pattern.search(text):
            add(rule.rubric)

    return out[:max_n]

# --- DB rubric -> symptom_id mapper (deterministic, controlled) ---
def _detect_symptoms_table(con: sqlite3.Connection) -> tuple[str, str]:
    """
    Returns (table_name, text_column) for rubrics.
    Tries common schemas safely.
    """
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0].lower(): r[0] for r in cur.fetchall()}

    # prefer "symptoms"
    for cand in ("symptoms", "symptom", "rubrics"):
        if cand in tables:
            tname = tables[cand]
            cur.execute(f"PRAGMA table_info({tname})")
            cols = [r[1] for r in cur.fetchall()]
            # choose best text column
            for c in ("rubric_text", "text", "name", "rubric", "label"):
                if c in cols:
                    return tname, c
            # fallback: first TEXT-like column name guess
            for c in cols:
                if "text" in c.lower() or "rubric" in c.lower() or "name" in c.lower():
                    return tname, c

    raise RuntimeError("Could not detect symptoms table/text column in synthesis.db")

def map_rubrics_to_ids(rubrics: list[str]) -> dict[str, Any]:
    mapped = []
    dbp = DB_PATH
    con = sqlite3.connect(dbp)
    try:
        table, text_col = _detect_symptoms_table(con)
        cur = con.cursor()

        for r in rubrics:
            q = _norm(r)
            # exact match first
            cur.execute(
                f"SELECT symptom_id, {text_col} FROM {table} WHERE lower({text_col})=?",
                (q,),
            )
            row = cur.fetchone()
            if row:
                mapped.append({"rubric": r, "symptom_id": int(row[0]), "matched_text": row[1], "method": "exact"})
                continue

            # controlled contains fallback (shortest first)
            cur.execute(
                f"""
                SELECT symptom_id, {text_col}
                FROM {table}
                WHERE lower({text_col}) LIKE ?
                ORDER BY LENGTH({text_col}) ASC
                LIMIT 5
                """,
                (f"%{q}%",),
            )
            rows = cur.fetchall()
            if rows:
                best = rows[0]
                mapped.append({"rubric": r, "symptom_id": int(best[0]), "matched_text": best[1], "method": "contains_best"})
            else:
                mapped.append({"rubric": r, "symptom_id": None, "matched_text": None, "method": "not_found"})

        return {"mapped": mapped, "db_path": dbp, "table": table, "text_col": text_col}
    finally:
        con.close()

@router.get("/mcare", response_class=HTMLResponse)
def mcare_ui():
    tpl = env.get_template("mcare_ui.html")
    return tpl.render()

@router.post("/mcare/extract")
def mcare_extract(payload: dict[str, Any]):
    narrative = str(payload.get("narrative", "") or "")
    rubrics = extract_rubrics(narrative, max_n=10)
    return {"rubrics": rubrics, "method": "rule_based_mind_first"}

@router.post("/mcare/map")
def mcare_map(payload: dict[str, Any]):
    rubrics = payload.get("rubrics") or []
    rubrics = [str(x) for x in rubrics if str(x).strip()]
    return map_rubrics_to_ids(rubrics)

@router.post("/mcare/score")
def mcare_score(payload: dict[str, Any]):
    symptom_ids = payload.get("symptom_ids") or []
    symptom_ids = [int(x) for x in symptom_ids]

    course = str(payload.get("course", "chronic") or "chronic").lower()
    case_type = str(payload.get("case_type", "AUTO") or "AUTO").upper()
    top_n = int(payload.get("top_n", 10) or 10)

    params = load_params(PARAMS_PATH)
    case_df = pd.DataFrame({"symptom_id": symptom_ids, "weight": [1] * len(symptom_ids)})

    # tags not required for scoring safety (you had ParserError before); keep {} for now
    tags = {}

    df = score_case(DB_PATH, case_df, tags, params, top_n, case_type, course)

    out = {
        "total_remedies_evaluated": int(len(df)),
        "top10": [
            {
                "remedy": str(r["remedy"]),
                "mcare_score": round(float(r["mcare_score"]), 6),
                "raw_score": round(float(r["raw_score"]), 6),
            }
            for _, r in df.iterrows()
        ],
    }
    return out

@router.post("/mcare/save")
def mcare_save(payload: dict[str, Any]):
    symptom_ids = [int(x) for x in (payload.get("symptom_ids") or [])]
    selected_remedy = str(payload.get("selected_remedy") or "").strip()
    if not selected_remedy:
        return {"ok": False, "error": "selected_remedy is required"}

    course = str(payload.get("course", "chronic") or "chronic").lower()
    case_type = str(payload.get("case_type", "AUTO") or "AUTO").upper()
    top_n = int(payload.get("top_n", 10) or 10)

    params = load_params(PARAMS_PATH)
    case_df = pd.DataFrame({"symptom_id": symptom_ids, "weight": [1] * len(symptom_ids)})
    tags = {}
    df = score_case(DB_PATH, case_df, tags, params, top_n, case_type, course)

    case_id = log_case(
        symptom_ids=symptom_ids,
        ranking_df=df,
        selected_remedy=selected_remedy,
        outcome=payload.get("outcome"),
        followup_days=payload.get("followup_days"),
        confidence_physician=payload.get("confidence_physician"),
        engine_version="v1-deterministic-engine",
        dataset_path=DB_PATH,
    )

    return {"ok": True, "case_id": case_id, "saved_to": "data/case_logs.jsonl"}