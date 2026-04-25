# src/clincore/api/schemas.py
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, conint, confloat


class ScoreRequest(BaseModel):
    symptom_ids: List[conint(strict=True)] = Field(..., min_length=1, description="List of symptom IDs")
    top_n: conint(strict=True, ge=1, le=50) = Field(5, description="Number of top remedies to return")


class ResultItem(BaseModel):
    remedy_id: str
    score: confloat(ge=0)


class ScoreResponse(BaseModel):
    results: List[ResultItem]
    request_id: str
    case_type_used: Optional[str] = None
