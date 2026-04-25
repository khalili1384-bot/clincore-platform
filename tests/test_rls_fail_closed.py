from __future__ import annotations
import pytest

pytestmark = pytest.mark.skip(reason="orphan: requires app.core.shared.db which does not exist in clincore")
