# tests/unit/test_models.py
"""Unit tests for shared data models."""
import pytest
from datetime import datetime
from core.models import ApplyStatus, ApplyJobInfo, ApplyResult


class TestApplyStatus:
    """Test ApplyStatus enum."""

    def test_values(self):
        assert ApplyStatus.PENDING.value == "pending"
        assert ApplyStatus.SUCCESS.value == "success"
        assert ApplyStatus.FAILED.value == "failed"
        assert ApplyStatus.SKIPPED.value == "skipped"
        assert ApplyStatus.ALREADY_APPLIED.value == "already_applied"

    def test_from_string(self):
        assert ApplyStatus("success") == ApplyStatus.SUCCESS
        assert ApplyStatus("failed") == ApplyStatus.FAILED


class TestApplyJobInfo:
    """Test ApplyJobInfo dataclass."""

    def test_required_fields(self):
        info = ApplyJobInfo(
            job_id="12345678",
            title="Data Analyst",
            company="Acme Corp",
            location="Hong Kong",
            job_url="https://example.com/job/12345678"
        )
        assert info.job_id == "12345678"
        assert info.title == "Data Analyst"
        assert info.company == "Acme Corp"

    def test_default_values(self):
        info = ApplyJobInfo(
            job_id="1", title="Dev", company="Co",
            location="HK", job_url="https://example.com"
        )
        assert info.jd_text == ""
        assert info.score == 0.0
        assert info.match_analysis == {}

    def test_custom_values(self):
        info = ApplyJobInfo(
            job_id="1", title="Dev", company="Co",
            location="HK", job_url="https://example.com",
            jd_text="Job description here",
            score=85.5,
            match_analysis={"skills": ["Python"]}
        )
        assert info.jd_text == "Job description here"
        assert info.score == 85.5
        assert info.match_analysis["skills"] == ["Python"]


class TestApplyResult:
    """Test ApplyResult dataclass."""

    def test_to_dict(self):
        info = ApplyJobInfo(
            job_id="123", title="Dev", company="Co",
            location="HK", job_url="https://example.com"
        )
        now = datetime.now()
        result = ApplyResult(
            job_info=info,
            status=ApplyStatus.SUCCESS,
            message="Applied successfully",
            applied_at=now
        )
        d = result.to_dict()
        assert d["job_id"] == "123"
        assert d["title"] == "Dev"
        assert d["company"] == "Co"
        assert d["status"] == "success"
        assert d["message"] == "Applied successfully"
        assert d["applied_at"] == now.isoformat()

    def test_to_dict_without_applied_at(self):
        info = ApplyJobInfo(
            job_id="1", title="Dev", company="Co",
            location="HK", job_url="https://example.com"
        )
        result = ApplyResult(
            job_info=info,
            status=ApplyStatus.SKIPPED,
            message="Low score"
        )
        d = result.to_dict()
        assert d["applied_at"] is None
        assert d["status"] == "skipped"
