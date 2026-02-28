from __future__ import annotations

import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from clincore.mcare_engine.mcare_sqlite_engine_v6_1 import score_case, load_params
from clincore.mcare_engine.case_logger import log_case
from clincore.mcare_engine.clinical_extractor import build_clinical_case

DB_PATH = r"src/clincore/mcare_engine/data/synthesis.db"
PARAMS_PATH = r"src/clincore/mcare_engine/mcare_config_v6_1.json"

router = APIRouter()

# ── Runtime safeguard: log where this router was loaded from ──
_log = logging.getLogger("clincore.mcare_engine.ui.router")
_log.info("MCARE router loaded from: %s", __file__)
_log.info("Python: %s", sys.version)
_log.info("sys.path[0]: %s", sys.path[0] if sys.path else "EMPTY")

# ── Template env ──
tpl_dir = Path(__file__).parent / "templates"
env = Environment(
    loader=FileSystemLoader(str(tpl_dir)),
    autoescape=select_autoescape(["html", "xml"]),
)

# ── Backward-compat wrapper: clinical.router imports extract_rubrics ──
def extract_rubrics(narrative: str, max_n: int = 10) -> list[str]:
    """Wrapper around clinical_extractor for backward compatibility."""
    clinical = build_clinical_case(narrative, db_path=DB_PATH)
    return clinical["rubrics"][:max_n]


# ── DB rubric → symptom_id mapper (deterministic, syntree + cross_references) ──

def _lookup_rubric_in_db(cur: sqlite3.Cursor, rubric: str) -> tuple:
    """Deterministic rubric→symptom_id using syntree + cross_references."""
    q = rubric.strip().upper()
    # 1) syntree exact
    cur.execute("SELECT id, search_path FROM syntree WHERE upper(search_path)=? LIMIT 1", (q,))
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
    # 3) syntree token search (split on " - ")
    for token in [t.strip() for t in q.split(" - ") if len(t.strip()) >= 4]:
        cur.execute(
            "SELECT id, search_path FROM syntree WHERE upper(search_path) LIKE ? ORDER BY LENGTH(search_path) ASC LIMIT 1",
            (f"%{token}%",),
        )
        row = cur.fetchone()
        if row:
            return int(row[0]), row[1], f"syntree_token:{token}"
    # 4) cross_references exact
    cur.execute("SELECT symptom_id, text FROM cross_references WHERE upper(text)=? LIMIT 1", (q,))
    row = cur.fetchone()
    if row:
        return int(row[0]), row[1], "xref_exact"
    # 5) cross_references LIKE shortest
    cur.execute(
        "SELECT symptom_id, text FROM cross_references WHERE upper(text) LIKE ? ORDER BY LENGTH(text) ASC LIMIT 1",
        (f"%{q}%",),
    )
    row = cur.fetchone()
    if row:
        return int(row[0]), row[1], "xref_like"
    return None, None, "not_found"


def map_rubrics_to_ids(rubrics: list[str]) -> dict[str, Any]:
    mapped = []
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        for r in rubrics:
            sid, matched, method = _lookup_rubric_in_db(cur, r)
            mapped.append({"rubric": r, "symptom_id": sid, "matched_text": matched, "method": method})
        return {"mapped": mapped, "db_path": DB_PATH, "table": "syntree", "text_col": "search_path"}
    finally:
        con.close()


# ── Endpoints ──

@router.get("/mcare", response_class=HTMLResponse)
def mcare_ui():
    tpl = env.get_template("mcare_ui.html")
    return tpl.render()


@router.post("/mcare/extract")
def mcare_extract(payload: dict[str, Any]):
    narrative = str(payload.get("narrative", "") or "")
    clinical = build_clinical_case(narrative, db_path=DB_PATH)
    return {"rubrics": clinical["rubrics"], "method": "clinical_extractor_v2", "mind_count": clinical["mind_count"]}


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
    case_type = str(payload.get("case_type", "auto") or "auto").lower()
    top_n = int(payload.get("top_n", 10) or 10)
    params = load_params(PARAMS_PATH)
    case_df = pd.DataFrame({"symptom_id": symptom_ids, "weight": [1] * len(symptom_ids)})
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


@router.post("/mcare/auto")
def mcare_auto(payload: dict[str, Any], explain: bool = False):
    """Clinical-grade auto pipeline: narrative → concepts → weighted rubrics → scored remedies.
    
    Args:
        explain: If True, include matched_concepts, cluster_flags, and top_5_weighted_rubrics in response
    """
    rubrics: list[str] = []
    try:
        narrative = str(payload.get("narrative", "") or "")
        top_n = int(payload.get("top_n", 10) or 10)
        case_type = str(payload.get("case_type", "auto") or "auto").lower()
        course = str(payload.get("course", "chronic") or "chronic").lower()

        # Clinical extraction pipeline (Layers A/B/C + differentiation)
        clinical = build_clinical_case(narrative, db_path=DB_PATH)
        rubrics = clinical["rubrics"]
        case_df = clinical["weighted_case_df"]
        details = clinical.get("rubric_details", [])

        if not rubrics:
            resp: dict[str, Any] = {"ok": False, "rubrics": [], "symptom_ids": [], "results": [],
                    "debug": {"matched_count": 0, "unmapped_rubrics": []},
                    "error": {"code": "NO_RUBRICS", "message": "No rubrics extracted from narrative"}}
            if explain:
                resp["matched_concepts"] = clinical.get("matched_concepts", {})
                resp["cluster_flags"] = clinical.get("cluster_flags", [])
                resp["top_5_weighted_rubrics"] = clinical.get("top_5_weighted_rubrics", [])
            return resp

        unmapped = [d["rubric"] for d in details if d.get("symptom_id") is None]
        matched_count = sum(1 for d in details if d.get("symptom_id") is not None)

        symptom_ids = case_df["symptom_id"].astype(int).tolist() if not case_df.empty else []

        if not symptom_ids:
            resp = {"ok": False, "rubrics": rubrics, "symptom_ids": [], "results": [],
                    "debug": {"matched_count": matched_count, "unmapped_rubrics": unmapped},
                    "error": {"code": "NO_SYMPTOM_IDS", "message": "No symptom_ids matched extracted rubrics"}}
            if explain:
                resp["matched_concepts"] = clinical.get("matched_concepts", {})
                resp["cluster_flags"] = clinical.get("cluster_flags", [])
                resp["top_5_weighted_rubrics"] = clinical.get("top_5_weighted_rubrics", [])
            return resp

        params = load_params(PARAMS_PATH)
        df = score_case(DB_PATH, case_df, {}, params, top_n, case_type, course)
        results = [
            {"remedy": str(r["remedy"]), "score": round(float(r["mcare_score"]), 6)}
            for _, r in df.head(top_n).iterrows()
        ]
        return {
            "ok": True,
            "rubrics": rubrics,
            "symptom_ids": symptom_ids,
            "results": results,
            "debug": {
                "matched_count": matched_count,
                "unmapped_rubrics": unmapped,
                "mind_count": clinical["mind_count"],
                "clusters_active": clinical["clusters_active"],
            },
            **({
                "matched_concepts": clinical.get("matched_concepts", {}),
                "cluster_flags": clinical.get("cluster_flags", []),
                "top_5_weighted_rubrics": clinical.get("top_5_weighted_rubrics", []),
            } if explain else {}),
            "error": None,
        }
    except Exception as exc:
        resp = {"ok": False, "rubrics": rubrics, "symptom_ids": [], "results": [],
                "debug": {"matched_count": 0, "unmapped_rubrics": []},
                "error": {"code": "AUTO_PIPELINE_FAILED", "message": str(exc)}}
        if explain:
            resp["matched_concepts"] = {}
            resp["cluster_flags"] = []
            resp["top_5_weighted_rubrics"] = []
        return resp


@router.post("/mcare/save")
def mcare_save(payload: dict[str, Any]):
    symptom_ids = [int(x) for x in (payload.get("symptom_ids") or [])]
    selected_remedy = str(payload.get("selected_remedy") or "").strip()
    if not selected_remedy:
        return {"ok": False, "error": "selected_remedy is required"}
    course = str(payload.get("course", "chronic") or "chronic").lower()
    case_type = str(payload.get("case_type", "auto") or "auto").lower()
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