#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCARE SQLite Engine v6.1 (Mind-centric, clinician-safe)

- Works with Synthesis-like SQLite DBs (tables: syntree, symptom_remedies, remedies)
- Uses clinician-provided rubric tags CSV (rubric_tags_MIND_v1.csv) for accurate bucket assignment
- Provides: auto case-type detection, SSRP boost, Golden Rule (chronic), freq normalization, coverage factor with threshold

Windows-friendly: tolerant CSV decoding (utf-8-sig / cp1256) + auto-fix malformed case CSVs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


# ----------------------------
# Data models
# ----------------------------

BUCKETS = ("MIND_CORE", "MENTAL_MOD", "PHYSICAL_MOD", "GENERALS", "LOCAL", "UNKNOWN")


@dataclass(frozen=True)
class Tag:
    symptom_id: int
    path: str
    layer_type: str  # expected: one of BUCKETS or similar
    flag_ailments_from: int = 0
    flag_delusions: int = 0


@dataclass(frozen=True)
class Params:
    # scoring weights (sum ~ 1.0 per mode)
    weights_by_mode: Dict[str, Dict[str, float]]

    # grade multiplier map
    grade_mult: Dict[int, float]

    # special multipliers
    ailments_from_mult: float
    delusion_mult: float

    # SSRP parameters (applies to any rubric meeting conditions)
    ssrp_mult: float
    ssrp_max_remedies: int
    ssrp_min_grade: int

    # frequency normalization
    freq_alpha: float

    # coverage factor
    coverage_beta: float
    coverage_min_hit_ratio: float  # only apply coverage bonus if rubrics_hit/total >= this

    # Golden Rule (chronic)
    golden_rule_enabled: bool
    golden_rule_only_chronic: bool
    golden_rule_topk: int
    golden_rule_min_mind_grade: int
    golden_rule_penalty: float  # multiply score by this for failing remedies inside topK

    # case type detection
    mind_dominant_min_mind_rubrics: int
    mind_dominant_min_strong_mind: int
    mind_dominant_strong_grade: int
    constitution_max_mind_rubrics: int


# ----------------------------
# Utilities: decoding + reading CSV
# ----------------------------

def _read_text_best_effort(path: str) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1256", "windows-1256", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    # last resort
    return data.decode("latin-1", errors="replace")


def read_case_csv(case_csv: str) -> pd.DataFrame:
    """
    Accepts:
      A) Proper CSV: symptom_id,weight
      B) 1-column CSV/TSV: symptom_id (weight defaults to 1.0)
      C) Malformed PowerShell-style lines:
           symptom_id
           weight
           123
           1
           456
           1.5
    """
    text = _read_text_best_effort(case_csv).strip().replace("\r\n", "\n").replace("\r", "\n")
    if not text:
        raise ValueError("case file is empty")

    # First try pandas normal parse with comma
    for sep in [",", "\t", ";"]:
        try:
            df = pd.read_csv(pd.io.common.StringIO(text), sep=sep)
            if "symptom_id" in df.columns:
                if "weight" not in df.columns:
                    df["weight"] = 1.0
                df = df[["symptom_id", "weight"]].copy()
                df["symptom_id"] = df["symptom_id"].astype(int)
                df["weight"] = df["weight"].astype(float)
                return df
        except Exception:
            pass

    # Fallback: line-based pairing
    lines = [ln.strip() for ln in text.split("\n") if ln.strip() != ""]
    # remove headers if present
    if len(lines) >= 2 and lines[0].lower().startswith("symptom") and lines[1].lower().startswith("weight"):
        lines = lines[2:]
    if not lines:
        raise ValueError("case file has no data rows")

    if len(lines) % 2 != 0:
        # assume weights missing -> all 1.0
        try:
            sids = [int(x) for x in lines]
            return pd.DataFrame({"symptom_id": sids, "weight": [1.0] * len(sids)})
        except Exception:
            raise ValueError("case file malformed: odd number of lines and cannot parse symptom_id list")

    sids: List[int] = []
    wts: List[float] = []
    for i in range(0, len(lines), 2):
        sid = lines[i]
        wt = lines[i + 1]
        try:
            sids.append(int(str(sid).replace(",", "").strip()))
            wts.append(float(str(wt).replace(",", ".").strip()))
        except Exception:
            raise ValueError(f"case file malformed around lines {i+1}-{i+2}: {sid!r}, {wt!r}")

    return pd.DataFrame({"symptom_id": sids, "weight": wts})


def load_tags(tags_csv: str) -> Dict[int, Tag]:
    """
    Expected columns (your rubric_tags_MIND_v1.csv):
      symptom_id, path, layer_type, flag_ailments_from, flag_delusions
    """
    text = _read_text_best_effort(tags_csv)
    df = pd.read_csv(pd.io.common.StringIO(text))
    required = {"symptom_id", "path", "layer_type"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"tags csv must contain columns at least: {sorted(required)}")

    for col in ("flag_ailments_from", "flag_delusions"):
        if col not in df.columns:
            df[col] = 0

    out: Dict[int, Tag] = {}
    for row in df.itertuples(index=False):
        sid = int(getattr(row, "symptom_id"))
        out[sid] = Tag(
            symptom_id=sid,
            path=str(getattr(row, "path")),
            layer_type=str(getattr(row, "layer_type")).upper(),
            flag_ailments_from=int(getattr(row, "flag_ailments_from")),
            flag_delusions=int(getattr(row, "flag_delusions")),
        )
    return out


# ----------------------------
# SQLite schema helpers
# ----------------------------

def _table_columns(con: sqlite3.Connection, table: str) -> List[str]:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info('{table}')")
    rows = cur.fetchall()
    return [str(r[1]) for r in rows]  # name


def detect_symptom_remedies_cols(con: sqlite3.Connection) -> Tuple[str, str]:
    cols = set(c.lower() for c in _table_columns(con, "symptom_remedies"))
    remedy_candidates = ["remedy", "remedy_abbreviation", "remedyabbr", "abbr", "short", "rem"]
    degree_candidates = ["degree", "grade", "deg", "value", "weight"]

    remedy_col = next((c for c in remedy_candidates if c in cols), None)
    degree_col = next((c for c in degree_candidates if c in cols), None)

    if not remedy_col:
        raise RuntimeError("Could not detect remedy column in symptom_remedies table.")
    if not degree_col:
        raise RuntimeError("Could not detect degree/grade column in symptom_remedies table.")

    return remedy_col, degree_col


def detect_syntree_parent_col(con: sqlite3.Connection) -> Optional[str]:
    cols = [c for c in _table_columns(con, "syntree")]
    lower = {c.lower(): c for c in cols}
    for cand in ("parent_id", "parent", "pid", "parentid"):
        if cand in lower:
            return lower[cand]
    return None


def build_syntree_path(con: sqlite3.Connection, node_id: int) -> str:
    """
    Best-effort path builder: uses parent_id if available; otherwise returns item only.
    """
    cur = con.cursor()
    parent_col = detect_syntree_parent_col(con)
    if not parent_col:
        cur.execute("SELECT item FROM syntree WHERE id=?", (node_id,))
        r = cur.fetchone()
        return str(r[0]) if r else str(node_id)

    parts: List[str] = []
    current = node_id
    guard = 0
    while current and guard < 50:
        cur.execute(f"SELECT item,{parent_col} FROM syntree WHERE id=?", (current,))
        row = cur.fetchone()
        if not row:
            break
        parts.append(str(row[0]))
        current = row[1]
        guard += 1
    parts.reverse()
    return " > ".join(parts) if parts else str(node_id)


def fallback_bucket_from_path(path: str) -> str:
    p = path.upper()
    if p.startswith("MIND"):
        # if it's a modality-ish rubric inside mind, tags should handle it; fallback keeps it as mind core
        return "MIND_CORE"
    # If user didn't tag non-mind, we keep conservative split:
    # - GENERALS if "GENERALS" appears
    # - LOCAL otherwise
    if "GENERALS" in p:
        return "GENERALS"
    return "LOCAL"


# ----------------------------
# Cached stats (freq normalization)
# ----------------------------

def _cache_path_for_db(db_path: str) -> Path:
    dbp = Path(db_path)
    return dbp.with_suffix(dbp.suffix + ".mcare_cache.json")


def _median(values: List[int]) -> float:
    if not values:
        return 1.0
    v = sorted(values)
    n = len(v)
    mid = n // 2
    if n % 2 == 1:
        return float(v[mid])
    return (v[mid - 1] + v[mid]) / 2.0


def get_cached_stats(db_path: str, con: sqlite3.Connection) -> Tuple[float, Dict[str, int]]:
    """
    Returns:
      median_freq (float): median of remedy frequency in symptom_remedies
      freq_map (dict): remedy -> count appearances
    """
    cache_path = _cache_path_for_db(db_path)
    remedy_col, _degree_col = detect_symptom_remedies_cols(con)

    cache_key = {
        "db": str(Path(db_path).name),
        "remedy_col": remedy_col,
        "version": 1,
    }

    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("key") == cache_key and "median_freq" in cached and "freq_map" in cached:
                return float(cached["median_freq"]), {str(k): int(v) for k, v in cached["freq_map"].items()}
        except Exception:
            pass

    cur = con.cursor()
    cur.execute(f"SELECT {remedy_col} AS remedy, COUNT(*) AS n FROM symptom_remedies GROUP BY {remedy_col}")
    freq_map: Dict[str, int] = {}
    freqs: List[int] = []
    for remedy, n in cur.fetchall():
        if remedy is None:
            continue
        rr = str(remedy)
        nn = int(n)
        freq_map[rr] = nn
        freqs.append(nn)

    median_freq = _median(freqs)

    try:
        cache_path.write_text(
            json.dumps({"key": cache_key, "median_freq": median_freq, "freq_map": freq_map}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    return median_freq, freq_map


# ----------------------------
# Case-type detection
# ----------------------------

def detect_case_type(
    con: sqlite3.Connection,
    case_df: pd.DataFrame,
    tags: Dict[int, Tag],
    params: Params,
    remedy_col: str,
    degree_col: str,
) -> str:
    """
    Conservative auto-detection:
      - MIND_DOMINANT if mind rubrics >= threshold OR strong mind rubrics >= threshold
      - CONSTITUTION if mind rubrics <= threshold
      - else MIXED
    Uses tags for bucket detection.
    """
    symptom_ids = [int(x) for x in case_df["symptom_id"].tolist()]
    total = len(symptom_ids)
    if total == 0:
        return "MIXED"

    mind_count = 0
    strong_mind = 0

    # Get max degree per symptom for speed (one query per symptom id)
    cur = con.cursor()
    for sid in symptom_ids:
        tag = tags.get(sid)
        if not tag:
            continue
        b = tag.layer_type.upper()
        if b not in ("MIND_CORE", "MENTAL_MOD"):
            continue
        mind_count += 1
        cur.execute(
            f"SELECT MAX({degree_col}) FROM symptom_remedies WHERE symptom_id=?",
            (sid,),
        )
        mx = cur.fetchone()[0]
        if mx is not None and int(mx) >= int(params.mind_dominant_strong_grade):
            strong_mind += 1

    if mind_count >= params.mind_dominant_min_mind_rubrics or strong_mind >= params.mind_dominant_min_strong_mind:
        return "MIND_DOMINANT"
    if mind_count <= params.constitution_max_mind_rubrics:
        return "CONSTITUTION"
    return "MIXED"


# ----------------------------
# Scoring
# ----------------------------

def _bucket_for_symptom(con: sqlite3.Connection, sid: int, tags: Dict[int, Tag]) -> Tuple[str, Optional[Tag], str]:
    tag = tags.get(sid)
    if tag:
        b = tag.layer_type.upper()
        if b not in BUCKETS:
            b = "UNKNOWN"
        return b, tag, tag.path
    # fallback from syntree path
    p = build_syntree_path(con, sid)
    return fallback_bucket_from_path(p), None, p


def score_case(
    db_path: str,
    case_df: pd.DataFrame,
    tags: Dict[int, Tag],
    params: Params,
    top_n: int,
    case_type: str,
    course: str,
) -> pd.DataFrame:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    remedy_col, degree_col = detect_symptom_remedies_cols(con)

    # determine case_type
    case_type = case_type.upper()
    if case_type == "AUTO":
        case_type = detect_case_type(con, case_df, tags, params, remedy_col, degree_col)

    mode = case_type.lower()
    if mode not in params.weights_by_mode:
        raise ValueError(f"Unknown case_type/mode: {case_type}. Choose: auto, mind_dominant, constitution, mixed")

    weights = params.weights_by_mode[mode]

    symptom_ids = case_df["symptom_id"].astype(int).tolist()
    weights_map = {int(sid): float(w) for sid, w in zip(case_df["symptom_id"], case_df["weight"])}

    # stats
    median_freq, freq_map = get_cached_stats(db_path, con)

    # rubric sizes (for SSRP)
    qmarks = ",".join(["?"] * len(symptom_ids))
    cur = con.cursor()
    cur.execute(
        f"SELECT symptom_id, COUNT(*) AS n FROM symptom_remedies WHERE symptom_id IN ({qmarks}) GROUP BY symptom_id",
        tuple(symptom_ids),
    )
    rubric_size_map = {int(r["symptom_id"]): int(r["n"]) for r in cur.fetchall()}

    # Gather remedy rows for all symptoms
    cur.execute(
        f"""
        SELECT symptom_id, {remedy_col} AS remedy, {degree_col} AS degree
        FROM symptom_remedies
        WHERE symptom_id IN ({qmarks})
        """,
        tuple(symptom_ids),
    )
    rows = cur.fetchall()
    if not rows:
        # no matches in DB
        return pd.DataFrame(columns=["remedy", "mcare_score", "raw_score", "freq"])

    # Accumulators
    per_remedy_bucket = {}  # remedy -> bucket -> score
    per_remedy_raw = {}     # remedy -> raw
    per_remedy_hits = {}    # remedy -> set(symptom_id)
    per_remedy_mind_strong = {}  # remedy -> int
    per_remedy_paths = {}   # remedy -> list[str] (debug)

    total_case = len(symptom_ids)

    for r in rows:
        sid = int(r["symptom_id"])
        remedy = str(r["remedy"])
        degree = int(r["degree"]) if r["degree"] is not None else 0
        if degree <= 0:
            continue

        w_case = float(weights_map.get(sid, 1.0))
        gmult = float(params.grade_mult.get(degree, 1.0))

        bucket, tag, path = _bucket_for_symptom(con, sid, tags)

        # bucket weight (unknown -> non_mind supportive)
        bw = float(weights.get(bucket, weights.get("GENERALS", 0.0)))

        # special multipliers (only from tags; safe)
        mult = 1.0
        if tag:
            if int(tag.flag_ailments_from) == 1:
                mult *= float(params.ailments_from_mult)
            if int(tag.flag_delusions) == 1:
                mult *= float(params.delusion_mult)

        # SSRP (small rubric boost)
        size = int(rubric_size_map.get(sid, 10**9))
        if size <= int(params.ssrp_max_remedies) and degree >= int(params.ssrp_min_grade):
            mult *= float(params.ssrp_mult)

        contrib_raw = gmult * w_case
        contrib_weighted = contrib_raw * bw * mult

        per_remedy_raw[remedy] = per_remedy_raw.get(remedy, 0.0) + contrib_raw
        per_remedy_bucket.setdefault(remedy, {})
        per_remedy_bucket[remedy][bucket] = per_remedy_bucket[remedy].get(bucket, 0.0) + contrib_weighted
        per_remedy_hits.setdefault(remedy, set()).add(sid)

        # mind strong hits (for Golden Rule & report)
        if bucket in ("MIND_CORE", "MENTAL_MOD") and degree >= int(params.golden_rule_min_mind_grade):
            per_remedy_mind_strong[remedy] = per_remedy_mind_strong.get(remedy, 0) + 1

    # Build output table
    out_rows = []
    for remedy, bucket_scores in per_remedy_bucket.items():
        raw = float(per_remedy_raw.get(remedy, 0.0))
        hits = len(per_remedy_hits.get(remedy, set()))
        coverage = hits / total_case if total_case else 0.0

        # weighted sum across buckets (already includes bucket weight)
        weighted = float(sum(bucket_scores.values()))

        # coverage factor with threshold (avoid polycrest bias)
        if coverage >= float(params.coverage_min_hit_ratio):
            # scale only the "excess" coverage above threshold
            denom = max(1e-9, 1.0 - float(params.coverage_min_hit_ratio))
            excess = (coverage - float(params.coverage_min_hit_ratio)) / denom
            coverage_factor = 1.0 + float(params.coverage_beta) * max(0.0, min(1.0, excess))
        else:
            coverage_factor = 1.0

        freq = int(freq_map.get(remedy, 0))
        # avoid zero division
        freq_norm = (freq / max(1.0, float(median_freq))) if freq > 0 else 1.0
        freq_factor = freq_norm ** float(params.freq_alpha) if freq_norm > 0 else 1.0

        mcare_score = (weighted * coverage_factor) / max(1e-9, freq_factor)

        # Flatten bucket columns
        row = {
            "remedy": remedy,
            "mcare_score": mcare_score,
            "raw_score": raw,
            "freq": freq,
            "rubrics_hit": hits,
            "coverage": coverage,
            "coverage_factor": coverage_factor,
            "mind_strong_hits": int(per_remedy_mind_strong.get(remedy, 0)),
            "case_type_used": case_type,
            "course": course.lower(),
        }
        for b in BUCKETS:
            if b == "UNKNOWN":
                continue
            row[b.lower()] = float(bucket_scores.get(b, 0.0))
        out_rows.append(row)

    df = pd.DataFrame(out_rows)

    # Pre-sort
    df = df.sort_values("mcare_score", ascending=False).reset_index(drop=True)

    # Golden Rule (chronic only if enabled)
    if params.golden_rule_enabled:
        if (not params.golden_rule_only_chronic) or (course.lower() == "chronic"):
            k = int(params.golden_rule_topk)
            k = max(1, min(k, len(df)))
            top = df.iloc[:k].copy()
            rest = df.iloc[k:].copy()

            # apply penalty only to topK failing remedies (no global re-rank)
            ok_mask = top["mind_strong_hits"].astype(int) >= 1
            top.loc[~ok_mask, "mcare_score"] = top.loc[~ok_mask, "mcare_score"] * float(params.golden_rule_penalty)

            df = pd.concat([top, rest], ignore_index=True).sort_values("mcare_score", ascending=False).reset_index(drop=True)

    # Return top_n
    top_n = int(top_n)
    if top_n > 0:
        df = df.head(top_n).copy()

    con.close()
    return df


# ----------------------------
# Config loading
# ----------------------------

def load_params(config_path: str) -> Params:
    cfg = json.loads(_read_text_best_effort(config_path))

    weights_by_mode = cfg["weights_by_mode"]
    grade_mult = {int(k): float(v) for k, v in cfg["grade_mult"].items()}

    return Params(
        weights_by_mode=weights_by_mode,
        grade_mult=grade_mult,
        ailments_from_mult=float(cfg.get("ailments_from_mult", 1.8)),
        delusion_mult=float(cfg.get("delusion_mult", 1.6)),
        ssrp_mult=float(cfg.get("ssrp_mult", 1.2)),
        ssrp_max_remedies=int(cfg.get("ssrp_max_remedies", 15)),
        ssrp_min_grade=int(cfg.get("ssrp_min_grade", 2)),
        freq_alpha=float(cfg.get("freq_alpha", 0.25)),
        coverage_beta=float(cfg.get("coverage_beta", 0.3)),
        coverage_min_hit_ratio=float(cfg.get("coverage_min_hit_ratio", 0.6)),
        golden_rule_enabled=bool(cfg.get("golden_rule_enabled", True)),
        golden_rule_only_chronic=bool(cfg.get("golden_rule_only_chronic", True)),
        golden_rule_topk=int(cfg.get("golden_rule_topk", 5)),
        golden_rule_min_mind_grade=int(cfg.get("golden_rule_min_mind_grade", 3)),
        golden_rule_penalty=float(cfg.get("golden_rule_penalty", 0.85)),
        mind_dominant_min_mind_rubrics=int(cfg.get("mind_dominant_min_mind_rubrics", 5)),
        mind_dominant_min_strong_mind=int(cfg.get("mind_dominant_min_strong_mind", 1)),
        mind_dominant_strong_grade=int(cfg.get("mind_dominant_strong_grade", 4)),
        constitution_max_mind_rubrics=int(cfg.get("constitution_max_mind_rubrics", 2)),
    )


# ----------------------------
# CLI
# ----------------------------

def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="MCARE SQLite Engine v6.1 (mind-centric)")
    ap.add_argument("--db", required=True, help="Path to synthesis-like SQLite DB (e.g., synthesis.135.db)")
    ap.add_argument("--case", required=True, help="Case CSV: symptom_id,weight")
    ap.add_argument("--tags", default=None, help="Tags CSV (recommended): rubric_tags_MIND_v1.csv")
    ap.add_argument("--strict_tags", action="store_true", help="If set, HALT when --tags is missing/not found.")
    ap.add_argument("--config", required=True, help="Config JSON (e.g., mcare_config_v6_1.json)")
    ap.add_argument("--case_type", default="auto", help="auto | mind_dominant | constitution | mixed")
    ap.add_argument("--course", default="chronic", help="chronic | acute")
    ap.add_argument("--top", type=int, default=30, help="Top N remedies to output")
    ap.add_argument("--out", default="output", help="Output folder")

    args = ap.parse_args(argv)

    # IO
    if not Path(args.db).exists():
        raise SystemExit(f"[ERROR] DB not found: {args.db}")

    case_df = read_case_csv(args.case)

    tags: Dict[int, Tag] = {}
    if args.tags and Path(args.tags).exists():
        tags = load_tags(args.tags)
    else:
        msg = f"[WARN] tags file not found: {args.tags}  (continuing without tags)"
        if args.strict_tags:
            raise SystemExit("[ERROR] --strict_tags is set but tags file is missing. Provide rubric_tags_MIND_v1.csv.")
        print(msg)

    params = load_params(args.config)

    df = score_case(
        db_path=args.db,
        case_df=case_df,
        tags=tags,
        params=params,
        top_n=args.top,
        case_type=args.case_type,
        course=args.course,
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "result.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    # Pretty print
    if df.empty:
        print("\n[INFO] No remedies found for given symptom_ids.\n")
        print(f"Saved to: {out_path}")
        return

    cols_show = ["remedy", "mcare_score", "raw_score", "freq", "rubrics_hit", "coverage", "mind_strong_hits"]
    print("\n=== TOP RESULTS ===\n")
    print(df[cols_show].to_string(index=False))
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
