# core/health_checker.py
"""
Indeed 健康检测 + 自动切换模块
自动检测 Indeed 可访问性，智能切换爬虫策略
"""

import asyncio
import logging
import time
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class IndeedStatus(Enum):
    """Indeed 状态"""
    HEALTHY = "healthy"           # 正常可用
    CAPTCHA = "captcha"           # 需要验证码
    BLOCKED = "blocked"           # 被封锁
    TIMEOUT = "timeout"           # 超时
    UNKNOWN = "unknown"           # 未知错误


class ScraperType(Enum):
    """爬虫类型"""
    PLAYWRIGHT = "playwright"     # Playwright (core/indeed_bot.py)
    DRISSION = "drission"         # DrissionPage (backend/scraper/indeed_stealth.py)


@dataclass
class HealthCheckResult:
    """健康检测结果"""
    status: IndeedStatus
    scraper_type: ScraperType
    message: str
    check_time: float
    can_proceed: bool


class IndeedHealthChecker:
    """
    Indeed 健康检测器

    功能：
    1. 快速检测 Indeed 可访问性
    2. 自动切换爬虫策略
    3. 缓存检测结果（避免频繁检测）
    """

    # 检测 URL
    TEST_URL = "https://www.indeed.com/jobs?q=test&l=remote"

    # 缓存时间（秒）
    CACHE_TTL = 300  # 5 分钟

    # CAPTCHA 关键词
    CAPTCHA_INDICATORS = [
        "captcha",
        "recaptcha",
        "verify you're human",
        "i'm not a robot",
        "security check",
        "please verify",
    ]

    # 封锁关键词
    BLOCKED_INDICATORS = [
        "access denied",
        "blocked",
        "forbidden",
        "too many requests",
        "rate limit",
    ]

    def __init__(self):
        self._cache: Optional[HealthCheckResult] = None
        self._cache_time: float = 0
        self._current_scraper: ScraperType = ScraperType.PLAYWRIGHT
        self._fallback_count: int = 0

    @property
    def current_scraper(self) -> ScraperType:
        """当前使用的爬虫类型"""
        return self._current_scraper

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self._cache:
            return False
        return (time.time() - self._cache_time) < self.CACHE_TTL

    def invalidate_cache(self):
        """强制刷新缓存"""
        self._cache = None
        self._cache_time = 0

    async def quick_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """
        快速健康检测（使用 curl）

        Args:
            timeout: 超时时间（秒）

        Returns:
            检测结果
        """
        # 检查缓存
        if self._is_cache_valid():
            logger.info(f"[HealthCheck] Using cached result: {self._cache.status.value}")
            return self._cache

        start_time = time.time()

        try:
            # 使用 asyncio 运行 curl
            process = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", "--max-time", str(int(timeout)),
                "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                self.TEST_URL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout + 2
            )

            content = stdout.decode("utf-8", errors="ignore").lower()
            check_time = time.time() - start_time

            # 分析结果
            result = self._analyze_response(content, check_time)

            # 缓存结果
            self._cache = result
            self._cache_time = time.time()

            logger.info(f"[HealthCheck] Indeed status: {result.status.value} ({check_time:.2f}s)")
            return result

        except asyncio.TimeoutError:
            result = HealthCheckResult(
                status=IndeedStatus.TIMEOUT,
                scraper_type=self._current_scraper,
                message="Indeed health check timed out",
                check_time=timeout,
                can_proceed=False,
            )
            self._cache = result
            self._cache_time = time.time()
            return result

        except Exception as e:
            logger.error(f"[HealthCheck] Error: {e}")
            return HealthCheckResult(
                status=IndeedStatus.UNKNOWN,
                scraper_type=self._current_scraper,
                message=str(e),
                check_time=time.time() - start_time,
                can_proceed=False,
            )

    def _analyze_response(self, content: str, check_time: float) -> HealthCheckResult:
        """分析响应内容"""

        # 检查是否有 CAPTCHA
        for indicator in self.CAPTCHA_INDICATORS:
            if indicator in content:
                return HealthCheckResult(
                    status=IndeedStatus.CAPTCHA,
                    scraper_type=self._current_scraper,
                    message=f"CAPTCHA detected: {indicator}",
                    check_time=check_time,
                    can_proceed=False,
                )

        # 检查是否被封锁
        for indicator in self.BLOCKED_INDICATORS:
            if indicator in content:
                return HealthCheckResult(
                    status=IndeedStatus.BLOCKED,
                    scraper_type=self._current_scraper,
                    message=f"Blocked: {indicator}",
                    check_time=check_time,
                    can_proceed=False,
                )

        # 检查是否有正常内容
        if "job_seen_beacon" in content or "jobsearch" in content or "jobtitle" in content:
            return HealthCheckResult(
                status=IndeedStatus.HEALTHY,
                scraper_type=self._current_scraper,
                message="Indeed is accessible",
                check_time=check_time,
                can_proceed=True,
            )

        # 内容太短或空白
        if len(content) < 1000:
            return HealthCheckResult(
                status=IndeedStatus.BLOCKED,
                scraper_type=self._current_scraper,
                message="Empty or blocked response",
                check_time=check_time,
                can_proceed=False,
            )

        # 有内容但不确定
        return HealthCheckResult(
            status=IndeedStatus.HEALTHY,
            scraper_type=self._current_scraper,
            message="Indeed seems accessible (unverified)",
            check_time=check_time,
            can_proceed=True,
        )

    def switch_scraper(self) -> ScraperType:
        """
        切换爬虫策略

        Returns:
            新的爬虫类型
        """
        self._fallback_count += 1

        if self._current_scraper == ScraperType.PLAYWRIGHT:
            self._current_scraper = ScraperType.DRISSION
            logger.info("[HealthCheck] Switched to DrissionPage scraper")
        else:
            self._current_scraper = ScraperType.PLAYWRIGHT
            logger.info("[HealthCheck] Switched to Playwright scraper")

        # 切换后清除缓存
        self.invalidate_cache()

        return self._current_scraper

    def reset(self):
        """重置状态"""
        self._current_scraper = ScraperType.PLAYWRIGHT
        self._fallback_count = 0
        self.invalidate_cache()


# 全局单例
_health_checker: Optional[IndeedHealthChecker] = None


def get_health_checker() -> IndeedHealthChecker:
    """获取全局健康检测器"""
    global _health_checker
    if _health_checker is None:
        _health_checker = IndeedHealthChecker()
    return _health_checker


async def check_indeed_health(force: bool = False) -> HealthCheckResult:
    """
    检测 Indeed 健康状态（便捷函数）

    Args:
        force: 是否强制刷新（忽略缓存）

    Returns:
        检测结果
    """
    checker = get_health_checker()
    if force:
        checker.invalidate_cache()
    return await checker.quick_check()


async def smart_search_indeed(
    keyword: str,
    user_id: str,
    location: Optional[str] = None,
    country: str = "us",
    max_pages: int = 3,
    headless: bool = True,
    max_retries: int = 2,
) -> list:
    """
    智能搜索 Indeed（自动检测 + 自动切换）

    Args:
        keyword: 搜索关键词
        user_id: 用户 ID
        location: 工作地点
        country: 国家代码
        max_pages: 最大页数
        headless: 是否无头模式
        max_retries: 最大重试次数

    Returns:
        职位列表
    """
    checker = get_health_checker()

    for attempt in range(max_retries + 1):
        # 1. 健康检测
        health = await checker.quick_check()

        if not health.can_proceed:
            logger.warning(f"[SmartSearch] Indeed not accessible: {health.message}")

            if attempt < max_retries:
                # 切换爬虫策略
                checker.switch_scraper()
                logger.info(f"[SmartSearch] Retry {attempt + 1}/{max_retries} with {checker.current_scraper.value}")
                await asyncio.sleep(2)  # 等待 2 秒再重试
                continue
            else:
                logger.error("[SmartSearch] All retries exhausted")
                return []

        # 2. 根据当前策略选择爬虫
        try:
            if checker.current_scraper == ScraperType.PLAYWRIGHT:
                jobs = await _search_with_playwright(
                    keyword, user_id, location, country, max_pages, headless
                )
            else:
                jobs = await _search_with_drission(
                    keyword, user_id, location, country, max_pages, headless
                )

            if jobs:
                logger.info(f"[SmartSearch] Found {len(jobs)} jobs with {checker.current_scraper.value}")
                return jobs

            # 没找到结果，尝试切换
            if attempt < max_retries:
                checker.switch_scraper()
                continue

        except Exception as e:
            logger.error(f"[SmartSearch] Error with {checker.current_scraper.value}: {e}")
            if attempt < max_retries:
                checker.switch_scraper()
                continue

    return []


async def _search_with_playwright(
    keyword: str,
    user_id: str,
    location: Optional[str],
    country: str,
    max_pages: int,
    headless: bool,
) -> list:
    """使用 Playwright 搜索"""
    from core.indeed_bot import search_indeed_jobs
    return await search_indeed_jobs(
        keyword=keyword,
        user_id=user_id,
        location=location,
        country=country,
        max_pages=max_pages,
        headless=headless,
    )


async def _search_with_drission(
    keyword: str,
    user_id: str,
    location: Optional[str],
    country: str,
    max_pages: int,
    headless: bool,
) -> list:
    """使用 DrissionPage 搜索"""
    from backend.scraper.indeed_stealth import IndeedStealthScraper
    from core.base_scraper import JobInfo, JobSource

    # DrissionPage 是同步的，需要在线程中运行
    def sync_search():
        scraper = IndeedStealthScraper(headless=headless)
        try:
            raw_jobs = scraper.search_jobs(
                keyword=keyword,
                location=location or "United States",
                max_results=max_pages * 15,
            )

            # 转换为 JobInfo 格式
            jobs = []
            for raw in raw_jobs:
                job = JobInfo(
                    source=JobSource.INDEED,
                    job_id=raw.get("url", "").split("jk=")[-1][:16] if raw.get("url") else f"indeed_{hash(raw.get('title', ''))}",
                    title=raw.get("title", ""),
                    company=raw.get("company", ""),
                    location=raw.get("location", ""),
                    job_url=raw.get("url", ""),
                    salary_range=raw.get("salary"),
                )
                jobs.append(job)
            return jobs
        finally:
            scraper.close()

    # 在线程池中运行同步代码
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sync_search)
