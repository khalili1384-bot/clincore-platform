from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PatientCreateIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=250)


class PatientOut(BaseModel):
    id: UUID
    full_name: str
    created_at: datetime
