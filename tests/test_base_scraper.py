# tests/test_base_scraper.py
"""
测试抽象基类和数据模型
"""

import pytest
from datetime import datetime
from core.base_scraper import (
    JobSource,
    ApplyStatus,
    JobInfo,
    ApplyResult,
)


class TestJobSource:
    """测试 JobSource 枚举"""

    def test_job_source_values(self):
        """测试枚举值"""
        assert JobSource.JOBSDB.value == "jobsdb"
        assert JobSource.INDEED.value == "indeed"
        assert JobSource.LINKEDIN.value == "linkedin"

    def test_job_source_from_string(self):
        """测试从字符串创建"""
        assert JobSource("jobsdb") == JobSource.JOBSDB
        assert JobSource("indeed") == JobSource.INDEED


class TestApplyStatus:
    """测试 ApplyStatus 枚举"""

    def test_apply_status_values(self):
        """测试枚举值"""
        assert ApplyStatus.PENDING.value == "pending"
        assert ApplyStatus.SUCCESS.value == "success"
        assert ApplyStatus.FAILED.value == "failed"
        assert ApplyStatus.SKIPPED.value == "skipped"
        assert ApplyStatus.ALREADY_APPLIED.value == "already_applied"
        assert ApplyStatus.BLOCKED.value == "blocked"


class TestJobInfo:
    """测试 JobInfo 数据模型"""

    def test_create_job_info(self):
        """测试创建 JobInfo"""
        job = JobInfo(
            source=JobSource.INDEED,
            job_id="test123",
            title="Software Engineer",
            company="Test Corp",
            location="Hong Kong",
            job_url="https://indeed.com/job/test123",
        )

        assert job.source == JobSource.INDEED
        assert job.job_id == "test123"
        assert job.title == "Software Engineer"
        assert job.company == "Test Corp"
        assert job.score == 0.0
        assert job.is_easy_apply == False

    def test_job_info_to_dict(self):
        """测试转换为字典"""
        job = JobInfo(
            source=JobSource.JOBSDB,
            job_id="job456",
            title="Data Scientist",
            company="AI Corp",
            location="Shenzhen",
            job_url="https://jobsdb.com/job/456",
            salary_range="30K-50K",
            is_easy_apply=True,
        )

        data = job.to_dict()

        assert data["source"] == "jobsdb"
        assert data["job_id"] == "job456"
        assert data["title"] == "Data Scientist"
        assert data["salary_range"] == "30K-50K"
        assert data["is_easy_apply"] == True

    def test_job_info_from_dict(self):
        """测试从字典创建"""
        data = {
            "source": "indeed",
            "job_id": "abc789",
            "title": "ML Engineer",
            "company": "Deep Learning Inc",
            "location": "Remote",
            "job_url": "https://indeed.com/abc789",
            "score": 85.5,
        }

        job = JobInfo.from_dict(data)

        assert job.source == JobSource.INDEED
        assert job.job_id == "abc789"
        assert job.score == 85.5


class TestApplyResult:
    """测试 ApplyResult 数据模型"""

    def test_create_apply_result(self):
        """测试创建 ApplyResult"""
        job = JobInfo(
            source=JobSource.INDEED,
            job_id="test123",
            title="Engineer",
            company="Corp",
            location="HK",
            job_url="https://test.com",
        )

        result = ApplyResult(
            job_info=job,
            status=ApplyStatus.SUCCESS,
            message="Applied successfully",
            applied_at=datetime.now(),
        )

        assert result.status == ApplyStatus.SUCCESS
        assert result.message == "Applied successfully"
        assert result.applied_at is not None

    def test_apply_result_to_dict(self):
        """测试转换为字典"""
        job = JobInfo(
            source=JobSource.JOBSDB,
            job_id="xyz",
            title="PM",
            company="Tech",
            location="SG",
            job_url="https://test.com",
        )

        result = ApplyResult(
            job_info=job,
            status=ApplyStatus.FAILED,
            message="Button not found",
        )

        data = result.to_dict()

        assert data["source"] == "jobsdb"
        assert data["status"] == "failed"
        assert data["message"] == "Button not found"


class TestPlatformRouter:
    """测试平台路由器"""

    def test_get_available_platforms(self):
        """测试获取支持的平台列表"""
        from core.platform_router import PlatformRouter

        platforms = PlatformRouter.get_available_platforms()

        assert "jobsdb" in platforms
        assert "indeed" in platforms

    def test_is_platform_supported(self):
        """测试平台支持检查"""
        from core.platform_router import PlatformRouter

        assert PlatformRouter.is_platform_supported("jobsdb") == True
        assert PlatformRouter.is_platform_supported("indeed") == True
        assert PlatformRouter.is_platform_supported("unknown") == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
