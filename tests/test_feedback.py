"""
Tests for clinical feedback logging.
"""
import json
import sqlite3
import uuid
from pathlib import Path

import pytest

from clincore.mcare_engine.ui.router import (
    _ensure_feedback_table,
    _find_case_info,
    mcare_feedback,
)
from clincore.mcare_engine.case_logger import LOG_PATH


# Test helpers
class TestFeedbackInsert:
    """Test feedback insert functionality."""

    def test_ensure_feedback_table_creates_table(self, tmp_path):
        """Test that _ensure_feedback_table creates the table and index."""
        db_path = str(tmp_path / "test.db")
        _ensure_feedback_table(db_path)

        # Verify table exists
        con = sqlite3.connect(db_path)
        try:
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clinical_feedback'")
            assert cur.fetchone() is not None

            # Verify index exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_clinical_feedback_tenant_time'")
            assert cur.fetchone() is not None
        finally:
            con.close()

    def test_feedback_insert_success(self, tmp_path, monkeypatch):
        """Test successful feedback insertion."""
        # Create temp DB
        db_path = str(tmp_path / "test.db")
        _ensure_feedback_table(db_path)

        # Mock LOG_PATH to a temp file
        log_file = tmp_path / "case_logs.jsonl"
        monkeypatch.setattr("clincore.mcare_engine.ui.router.LOG_PATH", log_file)
        monkeypatch.setattr("clincore.mcare_engine.case_logger.LOG_PATH", log_file)

        # Create a fake case log entry
        case_hash = str(uuid.uuid4())
        log_entry = {
            "case_id": case_hash,
            "ranking_snapshot": [
                {"remedy": "nux-v", "mcare_score": 0.85},
                {"remedy": "ars", "mcare_score": 0.75},
            ]
        }
        log_file.write_text(json.dumps(log_entry) + "\n")

        # Also need to mock DB_PATH
        monkeypatch.setattr("clincore.mcare_engine.ui.router.DB_PATH", db_path)

        # Call feedback endpoint
        payload = {
            "case_hash": case_hash,
            "chosen_remedy": "ars",
            "confidence": 4,
            "tenant_id": "test-tenant"
        }
        result = mcare_feedback(payload)

        assert result["ok"] is True
        assert "feedback_id" in result

        # Verify record in DB
        con = sqlite3.connect(db_path)
        try:
            cur = con.cursor()
            cur.execute("SELECT case_hash, suggested_top1, chosen_remedy, chosen_rank, confidence, tenant_id FROM clinical_feedback")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == case_hash
            assert row[1] == "nux-v"  # suggested_top1
            assert row[2] == "ars"  # chosen_remedy
            assert row[3] == 2  # chosen_rank (1-based)
            assert row[4] == 4  # confidence
            assert row[5] == "test-tenant"
        finally:
            con.close()

    def test_feedback_missing_case_hash(self):
        """Test feedback fails when case_hash is missing."""
        payload = {
            "chosen_remedy": "nux-v",
            "confidence": 3
        }
        result = mcare_feedback(payload)
        assert result["ok"] is False
        assert "case_hash" in result["error"]

    def test_feedback_missing_chosen_remedy(self):
        """Test feedback fails when chosen_remedy is missing."""
        payload = {
            "case_hash": str(uuid.uuid4()),
            "confidence": 3
        }
        result = mcare_feedback(payload)
        assert result["ok"] is False
        assert "chosen_remedy" in result["error"]

    def test_feedback_invalid_confidence(self):
        """Test feedback fails with invalid confidence value."""
        payload = {
            "case_hash": str(uuid.uuid4()),
            "chosen_remedy": "nux-v",
            "confidence": 6  # Out of range
        }
        result = mcare_feedback(payload)
        assert result["ok"] is False
        assert "confidence" in result["error"]

    def test_feedback_no_case_in_logs(self, tmp_path, monkeypatch):
        """Test feedback works even when case not found in logs."""
        db_path = str(tmp_path / "test.db")
        _ensure_feedback_table(db_path)

        log_file = tmp_path / "case_logs.jsonl"
        monkeypatch.setattr("clincore.mcare_engine.ui.router.LOG_PATH", log_file)
        monkeypatch.setattr("clincore.mcare_engine.ui.router.DB_PATH", db_path)

        # No log entries - case not found
        payload = {
            "case_hash": str(uuid.uuid4()),
            "chosen_remedy": "nux-v",
            "confidence": 3
        }
        result = mcare_feedback(payload)

        assert result["ok"] is True
        assert "feedback_id" in result


class TestTenantIsolation:
    """Test tenant isolation for feedback."""

    def test_tenant_isolation(self, tmp_path, monkeypatch):
        """Test that feedback is isolated by tenant_id."""
        db_path = str(tmp_path / "test.db")
        _ensure_feedback_table(db_path)
        monkeypatch.setattr("clincore.mcare_engine.ui.router.DB_PATH", db_path)

        log_file = tmp_path / "case_logs.jsonl"
        monkeypatch.setattr("clincore.mcare_engine.ui.router.LOG_PATH", log_file)

        # Insert feedback for tenant_a
        case_hash_a = str(uuid.uuid4())
        log_file.write_text(json.dumps({
            "case_id": case_hash_a,
            "ranking_snapshot": [{"remedy": "nux-v", "mcare_score": 0.85}]
        }) + "\n")

        mcare_feedback({
            "case_hash": case_hash_a,
            "chosen_remedy": "nux-v",
            "tenant_id": "tenant_a"
        })

        # Insert feedback for tenant_b
        case_hash_b = str(uuid.uuid4())
        with open(log_file, "a") as f:
            f.write(json.dumps({
                "case_id": case_hash_b,
                "ranking_snapshot": [{"remedy": "ars", "mcare_score": 0.75}]
            }) + "\n")

        mcare_feedback({
            "case_hash": case_hash_b,
            "chosen_remedy": "ars",
            "tenant_id": "tenant_b"
        })

        # Query feedback by tenant using the index
        con = sqlite3.connect(db_path)
        try:
            cur = con.cursor()

            # Get tenant_a feedback
            cur.execute("SELECT case_hash, tenant_id FROM clinical_feedback WHERE tenant_id = 'tenant_a'")
            rows_a = cur.fetchall()
            assert len(rows_a) == 1
            assert rows_a[0][1] == "tenant_a"

            # Get tenant_b feedback
            cur.execute("SELECT case_hash, tenant_id FROM clinical_feedback WHERE tenant_id = 'tenant_b'")
            rows_b = cur.fetchall()
            assert len(rows_b) == 1
            assert rows_b[0][1] == "tenant_b"

            # Verify different case_hashes
            assert rows_a[0][0] != rows_b[0][0]
        finally:
            con.close()

    def test_default_tenant(self, tmp_path, monkeypatch):
        """Test that default tenant_id is 'default'."""
        db_path = str(tmp_path / "test.db")
        _ensure_feedback_table(db_path)
        monkeypatch.setattr("clincore.mcare_engine.ui.router.DB_PATH", db_path)

        log_file = tmp_path / "case_logs.jsonl"
        monkeypatch.setattr("clincore.mcare_engine.ui.router.LOG_PATH", log_file)

        case_hash = str(uuid.uuid4())
        log_file.write_text(json.dumps({
            "case_id": case_hash,
            "ranking_snapshot": [{"remedy": "nux-v", "mcare_score": 0.85}]
        }) + "\n")

        # No tenant_id provided - should default to 'default'
        mcare_feedback({
            "case_hash": case_hash,
            "chosen_remedy": "nux-v"
        })

        con = sqlite3.connect(db_path)
        try:
            cur = con.cursor()
            cur.execute("SELECT tenant_id FROM clinical_feedback WHERE case_hash = ?", (case_hash,))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "default"
        finally:
            con.close()
