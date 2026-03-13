# backend/api/v1/platforms.py
"""
多平台管理 API
支持 JobsDB, Indeed, LinkedIn 的统一管理
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

from backend.api.v1.auth import get_current_user
from backend.models.schemas import UserInfo

router = APIRouter(prefix="/platforms", tags=["Platform Management"])


class PlatformType(str, Enum):
    JOBSDB = "jobsdb"
    INDEED = "indeed"
    LINKEDIN = "linkedin"


class PlatformInfo(BaseModel):
    """平台信息"""
    name: str
    display_name: str
    is_available: bool
    description: str
    supported_countries: List[str]


class SearchRequest(BaseModel):
    """搜索请求"""
    keyword: str
    platforms: List[PlatformType] = [PlatformType.JOBSDB]
    location: Optional[str] = None
    max_pages: int = 3
    filters: Optional[Dict[str, Any]] = None


class JobResult(BaseModel):
    """职位结果"""
    source: str
    job_id: str
    title: str
    company: str
    location: str
    job_url: str
    salary_range: Optional[str] = None
    is_easy_apply: bool = False
    score: float = 0.0


class SearchResponse(BaseModel):
    """搜索响应"""
    total_jobs: int
    jobs_by_platform: Dict[str, List[JobResult]]


class ApplyRequest(BaseModel):
    """投递请求"""
    platform: PlatformType
    job_id: str
    job_url: str
    resume_path: str
    cover_letter_path: Optional[str] = None


class ApplyResponse(BaseModel):
    """投递响应"""
    success: bool
    status: str
    message: str


# ============================================================
# API 端点
# ============================================================

@router.get("/", response_model=List[PlatformInfo])
async def list_platforms():
    """获取支持的平台列表"""
    return [
        PlatformInfo(
            name="jobsdb",
            display_name="JobsDB",
            is_available=True,
            description="香港最大的求职平台",
            supported_countries=["HK"],
        ),
        PlatformInfo(
            name="indeed",
            display_name="Indeed",
            is_available=True,
            description="全球最大的求职搜索引擎",
            supported_countries=["US", "UK", "CA", "AU", "HK", "SG"],
        ),
        PlatformInfo(
            name="linkedin",
            display_name="LinkedIn",
            is_available=False,  # 待实现
            description="职业社交平台",
            supported_countries=["Global"],
        ),
    ]


@router.post("/search", response_model=SearchResponse)
async def search_jobs(
    request: SearchRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    多平台职位搜索
    """
    from core.platform_router import PlatformRouter
    import asyncio

    user_id = str(current_user.id)
    results = {}
    total = 0

    for platform in request.platforms:
        if not PlatformRouter.is_platform_supported(platform.value):
            continue

        try:
            scraper = PlatformRouter.get_scraper(
                platform.value,
                user_id,
                headless=True
            )

            platform_jobs = []
            for page in range(1, request.max_pages + 1):
                jobs = await scraper.search_jobs(
                    request.keyword,
                    request.location,
                    page,
                    request.filters
                )
                platform_jobs.extend(jobs)
                if len(jobs) == 0:
                    break
                await asyncio.sleep(1)

            await scraper.close()

            results[platform.value] = [
                JobResult(
                    source=job.source.value,
                    job_id=job.job_id,
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    job_url=job.job_url,
                    salary_range=job.salary_range,
                    is_easy_apply=job.is_easy_apply,
                    score=job.score,
                )
                for job in platform_jobs
            ]
            total += len(platform_jobs)

        except Exception as e:
            results[platform.value] = []

    return SearchResponse(
        total_jobs=total,
        jobs_by_platform=results
    )


@router.post("/apply", response_model=ApplyResponse)
async def apply_job(
    request: ApplyRequest,
    background_tasks: BackgroundTasks,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    投递职位
    """
    from core.platform_router import PlatformRouter
    from core.base_scraper import JobInfo, JobSource

    user_id = str(current_user.id)

    if not PlatformRouter.is_platform_supported(request.platform.value):
        raise HTTPException(
            status_code=400,
            detail=f"Platform {request.platform.value} not supported"
        )

    try:
        bot = PlatformRouter.get_apply_bot(
            request.platform.value,
            user_id,
            headless=False
        )

        job = JobInfo(
            source=JobSource(request.platform.value),
            job_id=request.job_id,
            title="",
            company="",
            location="",
            job_url=request.job_url,
        )

        result = await bot.apply(job, request.resume_path, request.cover_letter_path)
        await bot.close()

        return ApplyResponse(
            success=result.status.value == "success",
            status=result.status.value,
            message=result.message
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_platform_stats(
    current_user: UserInfo = Depends(get_current_user)
):
    """获取各平台投递统计"""
    from core.history_manager import HistoryManager

    user_id = str(current_user.id)
    history = HistoryManager(user_id=user_id)

    stats = {
        "jobsdb": {"applied": 0, "success": 0, "failed": 0},
        "indeed": {"applied": 0, "success": 0, "failed": 0},
        "linkedin": {"applied": 0, "success": 0, "failed": 0},
    }

    for record in history.history:
        source = record.get("source", "jobsdb")
        status = record.get("status", "")

        if source in stats:
            stats[source]["applied"] += 1
            if status == "applied":
                stats[source]["success"] += 1
            elif status == "failed":
                stats[source]["failed"] += 1

    return stats
