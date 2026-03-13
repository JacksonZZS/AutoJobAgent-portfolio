# tests/unit/test_dedup.py
"""Unit tests for job deduplication logic."""
import pytest
from core.apply.dedup_mixin import DedupMixin


class TestDedupMixin:
    """Test dedup utility methods (standalone, no bot instance needed)."""

    def setup_method(self):
        """Create a minimal mixin instance for testing."""
        self.mixin = DedupMixin()

    def test_extract_job_id_from_jobsdb_url(self):
        url = "https://hk.jobsdb.com/job/12345678"
        result = self.mixin._extract_job_id(url)
        assert result == "12345678"

    def test_extract_job_id_from_url_with_params(self):
        url = "https://hk.jobsdb.com/job/12345678?ref=abc"
        result = self.mixin._extract_job_id(url)
        assert result == "12345678"

    def test_extract_job_id_fallback_to_digits(self):
        url = "https://example.com/position/87654321/apply"
        result = self.mixin._extract_job_id(url)
        assert result == "87654321"

    def test_extract_job_id_hash_fallback(self):
        url = "https://example.com/no-digits-here"
        result = self.mixin._extract_job_id(url)
        assert len(result) == 16  # MD5 hash truncated to 16

    def test_extract_job_id_empty(self):
        result = self.mixin._extract_job_id("")
        assert result == ""

    def test_generate_job_key_basic(self):
        key1 = self.mixin._generate_job_key("Data Analyst", "Acme Corp")
        key2 = self.mixin._generate_job_key("Data Analyst", "Acme Corp")
        assert key1 == key2

    def test_generate_job_key_case_insensitive(self):
        key1 = self.mixin._generate_job_key("Data Analyst", "ACME CORP")
        key2 = self.mixin._generate_job_key("data analyst", "acme corp")
        assert key1 == key2

    def test_generate_job_key_different_jobs(self):
        key1 = self.mixin._generate_job_key("Data Analyst", "Acme Corp")
        key2 = self.mixin._generate_job_key("Software Engineer", "Acme Corp")
        assert key1 != key2

    def test_generate_job_key_strips_whitespace(self):
        key1 = self.mixin._generate_job_key("  Data Analyst  ", "  Acme Corp  ")
        key2 = self.mixin._generate_job_key("Data Analyst", "Acme Corp")
        assert key1 == key2
