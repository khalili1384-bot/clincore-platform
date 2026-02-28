from __future__ import annotations

import json
import logging
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from clincore.mcare_engine.mcare_sqlite_engine_v6_1 import score_case, load_params
from clincore.mcare_engine.case_logger import log_case, LOG_PATH
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


# ── Feedback Table Schema ──
_FEEDBACK_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS clinical_feedback (
    id TEXT PRIMARY KEY,
    case_hash TEXT NOT NULL,
    suggested_top1 TEXT,
    chosen_remedy TEXT NOT NULL,
    chosen_rank INTEGER,
    confidence INTEGER,
    tenant_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
_FEEDBACK_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_clinical_feedback_tenant_time
ON clinical_feedback(tenant_id, created_at)
"""


def _ensure_feedback_table(db_path: str) -> None:
    """Ensure clinical_feedback table exists in SQLite."""
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(_FEEDBACK_TABLE_SQL)
        cur.execute(_FEEDBACK_INDEX_SQL)
        con.commit()
    finally:
        con.close()


def _find_case_info(case_hash: str) -> dict[str, Any] | None:
    """Find case info from case_logs.jsonl by case_hash (which is case_id in logs)."""
    if not LOG_PATH.exists():
        return None
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("case_id") == case_hash:
                        ranking = entry.get("ranking_snapshot", [])
                        suggested_top1 = ranking[0]["remedy"] if ranking else None
                        return {
                            "suggested_top1": suggested_top1,
                            "ranking": ranking,
                        }
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return None


@router.post("/mcare/feedback")
def mcare_feedback(payload: dict[str, Any]):
    """Record physician feedback on remedy selection.

    Body:
        case_hash: str - The case_id from /mcare/save response
        chosen_remedy: str - The remedy selected by physician
        confidence: int (1-5) - Physician confidence level
        tenant_id: str (optional) - Defaults to 'default'

    Returns:
        {ok: true} on success
    """
    try:
        case_hash = str(payload.get("case_hash", "")).strip()
        chosen_remedy = str(payload.get("chosen_remedy", "")).strip()
        confidence = payload.get("confidence")
        tenant_id = str(payload.get("tenant_id", "default")).strip()

        if not case_hash:
            return {"ok": False, "error": "case_hash is required"}
        if not chosen_remedy:
            return {"ok": False, "error": "chosen_remedy is required"}

        # Validate confidence is 1-5 if provided
        if confidence is not None:
            try:
                confidence = int(confidence)
                if confidence < 1 or confidence > 5:
                    return {"ok": False, "error": "confidence must be between 1 and 5"}
            except (ValueError, TypeError):
                return {"ok": False, "error": "confidence must be an integer 1-5"}

        # Ensure feedback table exists
        _ensure_feedback_table(DB_PATH)

        # Lookup case info from logs to find suggested_top1 and compute chosen_rank
        case_info = _find_case_info(case_hash)
        suggested_top1 = None
        chosen_rank = None

        if case_info:
            suggested_top1 = case_info.get("suggested_top1")
            ranking = case_info.get("ranking", [])
            # Find rank of chosen_remedy
            for i, r in enumerate(ranking):
                if r.get("remedy") == chosen_remedy:
                    chosen_rank = i + 1  # 1-based rank
                    break

        # Insert feedback record
        con = sqlite3.connect(DB_PATH)
        try:
            cur = con.cursor()
            feedback_id = str(uuid.uuid4())
            cur.execute(
                """INSERT INTO clinical_feedback
                    (id, case_hash, suggested_top1, chosen_remedy, chosen_rank, confidence, tenant_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (feedback_id, case_hash, suggested_top1, chosen_remedy, chosen_rank, confidence, tenant_id)
            )
            con.commit()
            _log.info("Feedback recorded: case_hash=%s, chosen=%s, rank=%s", case_hash, chosen_remedy, chosen_rank)
        finally:
            con.close()

        return {"ok": True, "feedback_id": feedback_id}
    except Exception as exc:
        _log.error("Feedback recording failed: %s", exc)
        return {"ok": False, "error": str(exc)}