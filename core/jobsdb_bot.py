# core/jobsdb_bot.py
"""
JobsDB 职位爬虫和投递机器人
适配新的抽象基类架构，保持与原有 apply_bot.py 的兼容性
"""

import os
import re
import logging
import asyncio
import random
from urllib.parse import quote
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout, Error as PlaywrightError

from core.base_scraper import (
    BaseJobScraper,
    BaseApplyBot,
    JobInfo,
    JobSource,
    ApplyStatus,
    ApplyResult,
    generate_stable_id,
)
from core.history_manager import HistoryManager
from core.ultimate_stealth import UltimateStealthBrowser

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent


class JobsDBScraper(BaseJobScraper):
    """JobsDB 职位爬虫 (hk.jobsdb.com) - 使用反爬浏览器"""

    SOURCE = JobSource.JOBSDB
    BASE_URL = "https://hk.jobsdb.com"

    SELECTORS = {
        "job_card": "article",
        "job_title": '[data-automation="jobTitle"]',
        "company_name": '[data-automation="jobCardCompanyLink"], [data-automation="jobCompany"]',
        "location": '[data-automation="jobCardLocation"]',
        "salary": '[data-automation="jobSalary"]',
        "posted_date": '[data-automation="jobListingDate"]',
        "jd_content": '[data-automation="jobAdDetails"]',
        "next_page": '[data-automation="page-next"]',
    }

    def __init__(
        self,
        user_id: str,
        headless: bool = True,
        proxy: Optional[str] = None,
    ):
        super().__init__(user_id, headless, proxy)
        self.history = HistoryManager(user_id=user_id)
        self.stealth_browser: Optional[UltimateStealthBrowser] = None

    async def init_stealth_browser(self):
        """初始化反爬浏览器"""
        if self.stealth_browser:
            return

        profile_dir = BASE_DIR / "data" / "browser_profiles" / f"jobsdb_{self.user_id}"
        self.stealth_browser = UltimateStealthBrowser(
            headless=self.headless,
            proxy=self.proxy,
            profile_dir=profile_dir,
            country="hk",
        )
        self.page = await self.stealth_browser.start()
        logger.info(f"[JobsDB] Stealth browser initialized for user {self.user_id}")

    async def close(self):
        """关闭浏览器"""
        if self.stealth_browser:
            await self.stealth_browser.close()
            self.stealth_browser = None
        await super().close()

    async def search_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        page: int = 1,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[JobInfo]:
        """搜索 JobsDB 职位 (使用反爬浏览器)"""
        # 使用反爬浏览器
        if not self.stealth_browser:
            await self.init_stealth_browser()

        jobs = []
        encoded_keyword = quote(keyword)

        # 构建搜索 URL
        search_url = f"{self.BASE_URL}/jobs?keywords={encoded_keyword}&page={page}"
        if location:
            search_url += f"&where={quote(location)}"

        logger.info(f"[JobsDB] Searching: {search_url}")

        try:
            # 使用反爬浏览器访问
            success = await self.stealth_browser.human_goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            if not success:
                logger.error(f"[JobsDB] Failed to load page")
                return jobs

            # 等待 Cloudflare 验证
            cf_passed = await self.stealth_browser.wait_for_cloudflare(max_wait=30)
            if not cf_passed:
                logger.warning(f"[JobsDB] Cloudflare challenge not passed, trying anyway...")

            # 等待职位卡片加载
            try:
                await self.page.wait_for_selector(
                    self.SELECTORS["job_card"],
                    timeout=30000
                )
            except PlaywrightTimeout:
                logger.warning(f"[JobsDB] No job cards found on page {page}")
                return jobs

            # 获取所有职位卡片
            job_cards = await self.page.query_selector_all(self.SELECTORS["job_card"])
            logger.info(f"[JobsDB] Found {len(job_cards)} job cards on page {page}")

            for card in job_cards:
                try:
                    job = await self._parse_job_card(card)
                    if job and not self.history.is_duplicate(job.job_id):
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"[JobsDB] Failed to parse job card: {e}")
                    continue

        except PlaywrightError as e:
            if "closed" in str(e).lower():
                logger.error("[JobsDB] Browser was closed, stopping...")
                raise
            logger.error(f"[JobsDB] Playwright error: {e}")
        except Exception as e:
            logger.error(f"[JobsDB] Error searching: {e}")

        return jobs

    async def _parse_job_card(self, card) -> Optional[JobInfo]:
        """解析职位卡片"""
        try:
            # 获取职位标题和链接
            title_elem = await card.query_selector(self.SELECTORS["job_title"])
            if not title_elem:
                return None

            title = await title_elem.inner_text()
            title = title.strip()

            # 获取链接和 job_id
            href = await title_elem.get_attribute("href")
            job_id = None
            if href:
                # 从 URL 提取 job_id
                match = re.search(r'/job/(\d+)', href)
                if match:
                    job_id = match.group(1)
            if not job_id:
                job_id = generate_stable_id("jobsdb", title)

            job_url = f"{self.BASE_URL}{href}" if href and not href.startswith("http") else href

            # 获取公司名称
            company_elem = await card.query_selector(self.SELECTORS["company_name"])
            company = await company_elem.inner_text() if company_elem else "Unknown Company"
            company = company.strip()

            # 获取地点
            location_elem = await card.query_selector(self.SELECTORS["location"])
            location = await location_elem.inner_text() if location_elem else ""
            location = location.strip()

            # 获取薪资
            salary_elem = await card.query_selector(self.SELECTORS["salary"])
            salary = await salary_elem.inner_text() if salary_elem else None

            return JobInfo(
                source=JobSource.JOBSDB,
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                job_url=job_url,
                salary_range=salary,
                is_easy_apply=True,  # JobsDB 都支持在线投递
            )

        except Exception as e:
            logger.warning(f"Error parsing job card: {e}")
            return None

    async def get_job_details(self, job_url: str) -> str:
        """获取职位详情 (JD)"""
        if not self.context:
            await self.init_browser()

        try:
            await self.page.goto(job_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1, 2))

            jd_elem = await self.page.wait_for_selector(
                self.SELECTORS["jd_content"],
                timeout=10000
            )

            if jd_elem:
                jd_text = await jd_elem.inner_text()
                return jd_text.strip()

        except Exception as e:
            logger.warning(f"Failed to get job details: {e}")

        return ""


class JobsDBApplyBotAdapter(BaseApplyBot):
    """
    JobsDB 投递机器人适配器
    将原有的 JobsDBApplyBot 适配到新的抽象基类
    """

    SOURCE = JobSource.JOBSDB

    DEFAULT_SELECTORS = {
        # 登录相关
        "login_button": 'a[data-automation="login"]',
        "email_input": 'input[data-automation="login-email"]',
        "password_input": 'input[data-automation="login-password"]',
        "submit_login": 'button[data-automation="login-submit"]',
        "logged_in_indicator": '[data-automation="account-menu"]',

        # 投递相关
        "apply_button": 'a[data-automation="job-detail-apply"]',
        "quick_apply_button": 'button[data-automation="quick-apply-button"]',
        "upload_cv_input": 'input[type="file"][accept*="pdf"]',
        "cover_letter_textarea": 'textarea[data-automation="cover-letter-input"]',
        "submit_application": 'button[data-automation="submit-application"]',
        "application_success": '[data-automation="application-success"]',
        "already_applied": '[data-automation="already-applied"]',
    }

    def __init__(
        self,
        user_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = False,
        llm_engine=None,
        cv_path: Optional[str] = None,
        status_manager=None,
    ):
        super().__init__(
            user_id=user_id,
            username=username or os.getenv("JOBSDB_USERNAME"),
            password=password or os.getenv("JOBSDB_PASSWORD"),
            headless=headless,
            llm_engine=llm_engine,
            cv_path=cv_path,
            status_manager=status_manager,
        )
        self.history = HistoryManager(user_id=user_id)

    async def login(self) -> bool:
        """登录 JobsDB"""
        if not self.context:
            await self.init_browser()

        # 检查是否已登录
        try:
            await self.page.goto(f"https://hk.jobsdb.com", wait_until="domcontentloaded")
            await asyncio.sleep(2)

            logged_in = await self.page.query_selector(self.selectors["logged_in_indicator"])
            if logged_in:
                logger.info("Already logged in to JobsDB")
                self.is_logged_in = True
                return True
        except Exception:
            pass

        if not self._username or not self._password:
            logger.warning("JobsDB credentials not provided")
            return False

        try:
            # 点击登录按钮
            await self.safe_click(self.selectors["login_button"])
            await asyncio.sleep(2)

            # 填写表单
            await self.safe_fill(self.selectors["email_input"], self._username)
            await self.random_delay(0.5, 1)
            await self.safe_fill(self.selectors["password_input"], self._password)
            await self.random_delay(0.5, 1)

            # 提交
            await self.safe_click(self.selectors["submit_login"])
            await asyncio.sleep(3)

            # 检查登录状态
            logged_in = await self.page.query_selector(self.selectors["logged_in_indicator"])
            if logged_in:
                logger.info("Successfully logged in to JobsDB")
                self.is_logged_in = True
                return True

            return False

        except Exception as e:
            logger.error(f"JobsDB login error: {e}")
            return False

    async def check_already_applied(self, job: JobInfo) -> bool:
        """检查是否已投递"""
        if self.history.is_duplicate(job.job_id):
            return True

        try:
            already_applied = await self.page.query_selector(self.selectors["already_applied"])
            return already_applied is not None
        except Exception:
            return False

    async def apply(
        self,
        job: JobInfo,
        resume_path: str,
        cover_letter_path: Optional[str] = None,
    ) -> ApplyResult:
        """投递 JobsDB 职位"""
        if not self.context:
            await self.init_browser()

        if await self.check_already_applied(job):
            return ApplyResult(
                job_info=job,
                status=ApplyStatus.ALREADY_APPLIED,
                message="Already applied to this job",
            )

        try:
            await self.page.goto(job.job_url, wait_until="domcontentloaded")
            await self.random_delay(2, 3)

            # 点击 Apply 按钮
            apply_clicked = await self.safe_click(self.selectors["apply_button"], timeout=5000)
            if not apply_clicked:
                apply_clicked = await self.safe_click(self.selectors["quick_apply_button"], timeout=3000)

            if not apply_clicked:
                return ApplyResult(
                    job_info=job,
                    status=ApplyStatus.FAILED,
                    message="Could not find Apply button",
                )

            await self.random_delay(2, 3)

            # 上传简历
            file_input = await self.page.query_selector(self.selectors["upload_cv_input"])
            if file_input:
                await file_input.set_input_files(resume_path)
                await self.random_delay(1, 2)

            # 填写 Cover Letter
            if cover_letter_path:
                try:
                    with open(cover_letter_path, 'r') as f:
                        cl_text = f.read()
                    await self.safe_fill(self.selectors["cover_letter_textarea"], cl_text)
                except Exception:
                    pass

            # 提交申请
            await self.safe_click(self.selectors["submit_application"])
            await self.random_delay(2, 3)

            # 检查结果
            success = await self.page.query_selector(self.selectors["application_success"])
            if success:
                self.history.add_record({
                    "job_id": job.job_id,
                    "title": job.title,
                    "company": job.company,
                    "link": job.job_url,
                    "status": "applied",
                    "source": "jobsdb",
                })
                return ApplyResult(
                    job_info=job,
                    status=ApplyStatus.SUCCESS,
                    message="Application submitted successfully",
                    resume_path=resume_path,
                    cover_letter_path=cover_letter_path,
                    applied_at=datetime.now(),
                )

            return ApplyResult(
                job_info=job,
                status=ApplyStatus.FAILED,
                message="Application submission uncertain",
            )

        except Exception as e:
            logger.error(f"JobsDB apply error: {e}")
            return ApplyResult(
                job_info=job,
                status=ApplyStatus.FAILED,
                message=str(e),
            )


# 便捷函数
async def search_jobsdb_jobs(
    keyword: str,
    user_id: str,
    location: Optional[str] = None,
    max_pages: int = 3,
    headless: bool = True,
) -> List[JobInfo]:
    """
    搜索 JobsDB 职位（便捷函数）
    """
    scraper = JobsDBScraper(
        user_id=user_id,
        headless=headless,
    )

    all_jobs = []
    try:
        for page in range(1, max_pages + 1):
            jobs = await scraper.search_jobs(keyword, location, page)
            all_jobs.extend(jobs)
            logger.info(f"Page {page}: found {len(jobs)} jobs, total: {len(all_jobs)}")

            if len(jobs) == 0:
                break

            await asyncio.sleep(random.uniform(2, 4))
    finally:
        await scraper.close()

    return all_jobs
