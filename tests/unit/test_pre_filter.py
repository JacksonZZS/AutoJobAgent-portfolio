# tests/unit/test_pre_filter.py
"""Unit tests for pre_filter_job function."""
import pytest
from core.llm.pre_filter import pre_filter_job


class TestPreFilterJob:
    """Test the hardcoded pre-filter logic."""

    def test_empty_jd_passes(self):
        result = pre_filter_job("")
        assert result["pass"] is True
        assert result["filter_type"] is None

    def test_none_jd_passes(self):
        result = pre_filter_job(None)
        assert result["pass"] is True

    def test_normal_jd_passes(self):
        jd = "We are looking for a Data Analyst with Python and SQL skills."
        result = pre_filter_job(jd)
        assert result["pass"] is True

    def test_phd_required_blocked(self):
        jd = "PhD required in Computer Science with 5 years research experience."
        result = pre_filter_job(jd)
        assert result["pass"] is False
        assert result["filter_type"] == "education"

    def test_masters_required_blocked(self):
        jd = "Master's degree required in Data Science or related field."
        result = pre_filter_job(jd)
        assert result["pass"] is False
        assert result["filter_type"] == "education"

    def test_japanese_required_blocked(self):
        jd = "Japanese required for daily communication with Tokyo office."
        result = pre_filter_job(jd)
        assert result["pass"] is False
        assert result["filter_type"] == "language"

    def test_korean_required_blocked(self):
        jd = "Korean required. Must be fluent in Korean for client meetings."
        result = pre_filter_job(jd)
        assert result["pass"] is False
        assert result["filter_type"] == "language"

    def test_5_years_experience_blocked(self):
        jd = "Minimum 5+ years of experience in software development."
        result = pre_filter_job(jd)
        assert result["pass"] is False
        assert result["filter_type"] == "experience"

    def test_senior_engineer_blocked(self):
        jd = "Looking for a Senior Engineer to lead our backend team."
        result = pre_filter_job(jd)
        assert result["pass"] is False
        assert result["filter_type"] == "experience"

    def test_case_insensitive(self):
        jd = "PHD REQUIRED in machine learning."
        result = pre_filter_job(jd)
        assert result["pass"] is False
        assert result["filter_type"] == "education"

    def test_chinese_education_blocked(self):
        jd = "要求博士学历，有深度学习研究经验。"
        result = pre_filter_job(jd)
        assert result["pass"] is False
        assert result["filter_type"] == "education"
