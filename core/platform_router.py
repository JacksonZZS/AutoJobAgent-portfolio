# core/platform_router.py
"""
多平台路由器
统一管理 JobsDB, Indeed, LinkedIn 的爬虫和投递逻辑
"""

import logging
from typing import List, Optional, Dict, Any, Type
from enum import Enum

from core.base_scraper import (
    BaseJobScraper,
    BaseApplyBot,
    JobInfo,
    JobSource,
    ApplyResult,
)
from core.jobsdb_bot import JobsDBScraper, JobsDBApplyBotAdapter
from core.indeed_bot import IndeedScraper, IndeedApplyBot
from core.linkedin_bot import LinkedInScraper, LinkedInApplyBot

logger = logging.getLogger(__name__)


class PlatformRouter:
    """
    平台路由器
    根据平台类型自动选择对应的爬虫和投递机器人
    """

    # 平台 -> 爬虫类映射
    SCRAPER_MAP: Dict[JobSource, Type[BaseJobScraper]] = {
        JobSource.JOBSDB: JobsDBScraper,
        JobSource.INDEED: IndeedScraper,
        JobSource.LINKEDIN: LinkedInScraper,
    }

    # 平台 -> 投递机器人类映射
    APPLY_BOT_MAP: Dict[JobSource, Type[BaseApplyBot]] = {
        JobSource.JOBSDB: JobsDBApplyBotAdapter,
        JobSource.INDEED: IndeedApplyBot,
        JobSource.LINKEDIN: LinkedInApplyBot,
    }

    @classmethod
    def get_scraper(
        cls,
        platform: str,
        user_id: str,
        headless: bool = True,
        **kwargs
    ) -> BaseJobScraper:
        """
        获取指定平台的爬虫实例

        Args:
            platform: 平台名称 (jobsdb, indeed, linkedin)
            user_id: 用户 ID
            headless: 是否无头模式
            **kwargs: 其他参数

        Returns:
            对应平台的爬虫实例
        """
        try:
            source = JobSource(platform.lower())
        except ValueError:
            raise ValueError(f"Unsupported platform: {platform}. Supported: {[s.value for s in JobSource]}")

        scraper_class = cls.SCRAPER_MAP.get(source)
        if not scraper_class:
            raise NotImplementedError(f"Scraper for {platform} not implemented yet")

        return scraper_class(user_id=user_id, headless=headless, **kwargs)

    @classmethod
    def get_apply_bot(
        cls,
        platform: str,
        user_id: str,
        headless: bool = False,
        **kwargs
    ) -> BaseApplyBot:
        """
        获取指定平台的投递机器人实例

        Args:
            platform: 平台名称
            user_id: 用户 ID
            headless: 是否无头模式
            **kwargs: 其他参数（username, password, llm_engine 等）

        Returns:
            对应平台的投递机器人实例
        """
        try:
            source = JobSource(platform.lower())
        except ValueError:
            raise ValueError(f"Unsupported platform: {platform}")

        bot_class = cls.APPLY_BOT_MAP.get(source)
        if not bot_class:
            raise NotImplementedError(f"Apply bot for {platform} not implemented yet")

        return bot_class(user_id=user_id, headless=headless, **kwargs)

    @classmethod
    def get_available_platforms(cls) -> List[str]:
        """获取当前支持的平台列表"""
        return [source.value for source in cls.SCRAPER_MAP.keys()]

    @classmethod
    def is_platform_supported(cls, platform: str) -> bool:
        """检查平台是否支持"""
        try:
            source = JobSource(platform.lower())
            return source in cls.SCRAPER_MAP
        except ValueError:
            return False


async def search_jobs_multi_platform(
    keyword: str,
    user_id: str,
    platforms: List[str] = None,
    location: Optional[str] = None,
    max_pages: int = 3,
    headless: bool = True,
) -> Dict[str, List[JobInfo]]:
    """
    多平台职位搜索

    Args:
        keyword: 搜索关键词
        user_id: 用户 ID
        platforms: 平台列表，默认所有支持的平台
        location: 工作地点
        max_pages: 每个平台最大爬取页数
        headless: 是否无头模式

    Returns:
        {platform: [JobInfo, ...]} 格式的结果
    """
    import asyncio

    if platforms is None:
        platforms = PlatformRouter.get_available_platforms()

    results = {}

    for platform in platforms:
        if not PlatformRouter.is_platform_supported(platform):
            logger.warning(f"Platform {platform} not supported, skipping")
            continue

        try:
            scraper = PlatformRouter.get_scraper(platform, user_id, headless)
            platform_jobs = []

            for page in range(1, max_pages + 1):
                jobs = await scraper.search_jobs(keyword, location, page)
                platform_jobs.extend(jobs)

                if len(jobs) == 0:
                    break

                await asyncio.sleep(2)

            await scraper.close()
            results[platform] = platform_jobs
            logger.info(f"Platform {platform}: found {len(platform_jobs)} jobs")

        except Exception as e:
            logger.error(f"Error searching {platform}: {e}")
            results[platform] = []

    return results
