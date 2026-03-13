# core/models.py
"""
Shared data models for AutoJobAgent.
Extracted from apply_bot.py for reuse across modules.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ApplyStatus(Enum):
    """投递状态枚举"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ALREADY_APPLIED = "already_applied"


@dataclass
class ApplyJobInfo:
    """职位申请信息"""
    job_id: str
    title: str
    company: str
    location: str
    job_url: str
    jd_text: str = ""
    score: float = 0.0
    match_analysis: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApplyResult:
    """投递结果"""
    job_info: ApplyJobInfo
    status: ApplyStatus
    message: str = ""
    cover_letter: str = ""
    applied_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "job_id": self.job_info.job_id,
            "title": self.job_info.title,
            "company": self.job_info.company,
            "status": self.status.value,
            "message": self.message,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None
        }
