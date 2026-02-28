"""
Feedback API models and canonicalization helpers for v0.4.6.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── Canonicalization helpers ──────────────────────────────────────────────────

def canonical_json_dumps(data: Any) -> str:
    """Deterministic JSON serialization: sorted keys, compact separators."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def narrative_hash(narrative: str, locale: str | None = None) -> str:
    """
    Deterministic hash of a narrative for storage (never stores raw narrative).

    Normalization:
    - NFKC Unicode normalization (handles both fa and en)
    - Collapse whitespace to single spaces
    - Strip leading/trailing whitespace
    - Lowercase only for English (en); Persian kept as-is after NFKC
    """
    normalized = unicodedata.normalize("NFKC", narrative)
    # Collapse all whitespace sequences to single space
    normalized = " ".join(normalized.split())
    # Lowercase only for English locale
    if locale and locale.lower().startswith("en"):
        normalized = normalized.lower()
    # Include locale prefix to avoid cross-locale collisions
    prefix = f"locale:{locale or 'unknown'}:"
    payload = (prefix + normalized).encode("utf-8")
    return sha256_hex(payload)


# ── Pydantic models ───────────────────────────────────────────────────────────

VALID_OUTCOME_TYPES = {"agree", "disagree", "followup", "adverse", "unknown"}


class FeedbackIn(BaseModel):
    """Input model for POST /mcare/feedback."""

    request_id: Optional[str] = Field(default=None, max_length=128)
    locale: Optional[str] = Field(default=None, max_length=10)
    narrative: Optional[str] = Field(
        default=None,
        description="Only used for hashing; raw narrative is never stored.",
    )
    predicted_top1: str = Field(..., min_length=1, max_length=64)
    predicted_top3: list[str] = Field(..., min_length=1)
    chosen_remedy: str = Field(..., min_length=1, max_length=64)
    outcome_type: str = Field(..., min_length=1, max_length=32)
    outcome_score: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = Field(default=None, max_length=2048)
    case_id: Optional[uuid.UUID] = None
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)

    @field_validator("predicted_top3")
    @classmethod
    def cap_predicted_top3(cls, v: list[str]) -> list[str]:
        """Cap at 5 entries; ensure each is non-empty string."""
        capped = [str(s).strip() for s in v[:5] if str(s).strip()]
        if not capped:
            raise ValueError("predicted_top3 must contain at least one non-empty remedy")
        return capped

    @field_validator("outcome_type")
    @classmethod
    def validate_outcome_type(cls, v: str) -> str:
        if v not in VALID_OUTCOME_TYPES:
            raise ValueError(
                f"outcome_type must be one of: {', '.join(sorted(VALID_OUTCOME_TYPES))}"
            )
        return v


class FeedbackOut(BaseModel):
    """Response model for POST /mcare/feedback."""

    id: uuid.UUID
    created_at: datetime
    is_correct: bool  # chosen_remedy == predicted_top1


class FeedbackSummaryOut(BaseModel):
    """Response model for GET /mcare/feedback/summary."""

    total_count: int
    top1_accuracy: float  # fraction 0.0 - 1.0
    top3_coverage: float  # fraction 0.0 - 1.0
    outcome_counts: dict[str, int]
    top_mismatches: list[dict[str, Any]]  # [{predicted_top1, chosen_remedy, count}]
    days: int
