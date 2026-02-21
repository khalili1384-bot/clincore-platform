from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PatientDTO:
    id: UUID
    full_name: str
    created_at: datetime
