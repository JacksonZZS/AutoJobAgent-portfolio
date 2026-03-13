# core/indeed_bot.py
"""
Indeed 职位爬虫和投递机器人
支持 Indeed Easy Apply 一键投递
"""

import os
import re
import logging
import asyncio
import random
from urllib.parse import quote, urlencode
from typing import List, Optional, Dict, Any
from datetime import datetime

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

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

logger = logging.getLogger(__name__)

# Indeed 国家站点 URL 映射
INDEED_COUNTRY_URLS = {
    "us": "https://www.indeed.com",
    "hk": "https://hk.indeed.com",
    "uk": "https://uk.indeed.com",
    "ca": "https://ca.indeed.com",
    "au": "https://au.indeed.com",
    "sg": "https://sg.indeed.com",
}


def get_indeed_url(country: str) -> str:
    """根据国家代码获取 Indeed URL"""
    return INDEED_COUNTRY_URLS.get(country, "https://www.indeed.com")


class IndeedScraper(BaseJobScraper):
    """Indeed 职位爬虫"""

    SOURCE = JobSource.INDEED
    BASE_URL = "https://www.indeed.com"

    # Indeed 页面选择器
    SELECTORS = {
        "job_card": 'div.job_seen_beacon, div.jobsearch-ResultsList > div',
        "job_title": 'h2.jobTitle a, a[data-jk]',
        "company_name": '[data-testid="company-name"], span.companyName',
        "location": '[data-testid="text-location"], div.companyLocation',
        "salary": '[data-testid="attribute_snippet_testid"], div.salary-snippet-container',
        "job_type": '[data-testid="attribute_snippet_testid"]',
        "posted_date": 'span.date, span[data-testid="myJobsStateDate"]',
        "easy_apply_badge": '.iaLabel, span:has-text("Easily apply")',
        "jd_content": '#jobDescriptionText, div.jobsearch-jobDescriptionText',
        "next_page": 'a[data-testid="pagination-page-next"]',
    }

    def __init__(
        self,
        user_id: str,
        headless: bool = True,
        proxy: Optional[str] = None,
        country: str = "us",  # us, hk, uk, ca, au 等
    ):
        super().__init__(user_id, headless, proxy)
        self.country = country
        self.base_url = get_indeed_url(country)
        self.history = HistoryManager(user_id=user_id)

        # 🔴 使用已登录的 Indeed profile 目录（保持登录状态）
        from pathlib import Path
        BASE_DIR = Path(__file__).parent.parent
        self.profile_dir = BASE_DIR / "chrome_profile" / f"indeed_{country}"
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    async def search_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        page: int = 1,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[JobInfo]:
        """搜索 Indeed 职位"""
        if not self.context:
            await self.init_browser()

        jobs = []
        filters = filters or {}

        # 构建搜索 URL
        params = {
            "q": keyword,
            "start": (page - 1) * 10,  # Indeed 每页 10-15 个结果
        }
        if location:
            params["l"] = location
        if filters.get("job_type"):
            params["jt"] = filters["job_type"]  # fulltime, parttime, contract
        if filters.get("posted_days"):
            params["fromage"] = filters["posted_days"]  # 1, 3, 7, 14

        search_url = f"{self.base_url}/jobs?{urlencode(params)}"
        logger.info(f"Searching Indeed: {search_url}")

        try:
            await self.page.goto(search_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 4))

            # 等待职位卡片加载
            await self.page.wait_for_selector(
                self.SELECTORS["job_card"],
                timeout=10000
            )

            # 获取所有职位卡片
            job_cards = await self.page.query_selector_all(self.SELECTORS["job_card"])
            logger.info(f"Found {len(job_cards)} job cards on page {page}")

            for card in job_cards:
                try:
                    job = await self._parse_job_card(card)
                    if job and not self.history.is_processed(job.job_id):
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"Failed to parse job card: {e}")
                    continue

        except PlaywrightTimeout:
            logger.warning(f"Timeout loading Indeed search page {page}")
        except Exception as e:
            logger.error(f"Error searching Indeed: {e}")

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

            # 获取 job_id (Indeed 使用 data-jk 属性)
            job_id = await title_elem.get_attribute("data-jk")
            if not job_id:
                href = await title_elem.get_attribute("href")
                if href:
                    match = re.search(r'jk=([a-f0-9]+)', href)
                    job_id = match.group(1) if match else None
            if not job_id:
                job_id = generate_stable_id("indeed", title)

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

            # 检查是否支持 Easy Apply
            easy_apply_elem = await card.query_selector(self.SELECTORS["easy_apply_badge"])
            is_easy_apply = easy_apply_elem is not None

            # 构建职位 URL
            job_url = f"{self.base_url}/viewjob?jk={job_id}"

            return JobInfo(
                source=JobSource.INDEED,
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                job_url=job_url,
                salary_range=salary,
                is_easy_apply=is_easy_apply,
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

            # 等待 JD 加载
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


class IndeedApplyBot(BaseApplyBot):
    """Indeed 投递机器人"""

    SOURCE = JobSource.INDEED

    DEFAULT_SELECTORS = {
        # 登录相关
        "sign_in_button": 'a[href*="login"], button:has-text("Sign in")',
        "email_input": 'input[type="email"], input[name="__email"]',
        "password_input": 'input[type="password"]',
        "login_submit": 'button[type="submit"]',
        "logged_in_indicator": '[data-gnav-element-name="ProfileButton"]',

        # 投递相关
        "apply_button": '#indeedApplyButton, button[id*="apply"], button:has-text("Apply now")',
        "easy_apply_modal": '[id*="ia-container"], div[class*="ia-"]',
        "resume_upload": 'input[type="file"]',
        "continue_button": 'button:has-text("Continue"), button[type="submit"]',
        "submit_button": 'button:has-text("Submit"), button:has-text("Submit your application")',
        "success_indicator": 'div:has-text("Application submitted"), div:has-text("applied")',
        "already_applied": 'span:has-text("Applied"), div:has-text("You have already applied")',

        # 表单字段
        "phone_input": 'input[name*="phone"], input[type="tel"]',
        "name_input": 'input[name*="name"]',
        "experience_years": 'input[name*="experience"], select[name*="experience"]',
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
        country: str = "us",
    ):
        super().__init__(
            user_id=user_id,
            username=username or os.getenv("INDEED_EMAIL"),
            password=password or os.getenv("INDEED_PASSWORD"),
            headless=headless,
            llm_engine=llm_engine,
            cv_path=cv_path,
            status_manager=status_manager,
        )
        self.country = country
        self.base_url = get_indeed_url(country)
        self.history = HistoryManager(user_id=user_id)

    async def login(self) -> bool:
        """登录 Indeed"""
        if not self.context:
            await self.init_browser()

        # 先检查是否已登录
        try:
            await self.page.goto(self.base_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            logged_in = await self.page.query_selector(self.selectors["logged_in_indicator"])
            if logged_in:
                logger.info("Already logged in to Indeed")
                self.is_logged_in = True
                return True
        except Exception:
            pass

        if not self._username or not self._password:
            logger.warning("Indeed credentials not provided")
            return False

        try:
            # 点击登录按钮
            login_url = f"{self.base_url}/account/login"
            await self.page.goto(login_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # 填写邮箱
            await self.safe_fill(self.selectors["email_input"], self._username)
            await self.random_delay(0.5, 1)

            # 点击继续
            await self.safe_click(self.selectors["continue_button"])
            await asyncio.sleep(2)

            # 填写密码
            await self.safe_fill(self.selectors["password_input"], self._password)
            await self.random_delay(0.5, 1)

            # 提交登录
            await self.safe_click(self.selectors["login_submit"])
            await asyncio.sleep(3)

            # 检查登录状态
            logged_in = await self.page.query_selector(self.selectors["logged_in_indicator"])
            if logged_in:
                logger.info("Successfully logged in to Indeed")
                self.is_logged_in = True
                return True

            logger.warning("Indeed login failed - may need CAPTCHA verification")
            return False

        except Exception as e:
            logger.error(f"Indeed login error: {e}")
            return False

    async def check_already_applied(self, job: JobInfo) -> bool:
        """检查是否已投递"""
        # 先检查本地历史
        if self.history.is_processed(job.job_id):
            return True

        # 检查页面上的已投递标记
        try:
            await self.page.goto(job.job_url, wait_until="domcontentloaded")
            await asyncio.sleep(1)

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
        """投递 Indeed 职位"""
        if not self.context:
            await self.init_browser()

        # 检查是否已投递
        if await self.check_already_applied(job):
            return ApplyResult(
                job_info=job,
                status=ApplyStatus.ALREADY_APPLIED,
                message="Already applied to this job",
            )

        try:
            # 导航到职位页面
            await self.page.goto(job.job_url, wait_until="domcontentloaded")
            await self.random_delay(2, 3)

            # 点击 Apply 按钮
            apply_clicked = await self.safe_click(self.selectors["apply_button"], timeout=5000)
            if not apply_clicked:
                return ApplyResult(
                    job_info=job,
                    status=ApplyStatus.FAILED,
                    message="Could not find Apply button",
                )

            await self.random_delay(2, 3)

            # 处理 Easy Apply 流程
            result = await self._handle_easy_apply_flow(job, resume_path)
            return result

        except Exception as e:
            logger.error(f"Indeed apply error: {e}")
            return ApplyResult(
                job_info=job,
                status=ApplyStatus.FAILED,
                message=str(e),
            )

    async def _handle_easy_apply_flow(
        self,
        job: JobInfo,
        resume_path: str,
    ) -> ApplyResult:
        """处理 Indeed Easy Apply 流程"""
        max_steps = 10  # 最多处理 10 步表单

        for step in range(max_steps):
            logger.info(f"Indeed Easy Apply step {step + 1}")
            await asyncio.sleep(1)

            # 检查是否成功
            success = await self.page.query_selector(self.selectors["success_indicator"])
            if success:
                logger.info(f"Successfully applied to {job.title} at {job.company}")
                self.history.add_record({
                    "job_id": job.job_id,
                    "title": job.title,
                    "company": job.company,
                    "link": job.job_url,
                    "status": "applied",
                    "source": "indeed",
                })
                return ApplyResult(
                    job_info=job,
                    status=ApplyStatus.SUCCESS,
                    message="Application submitted successfully",
                    resume_path=resume_path,
                    applied_at=datetime.now(),
                )

            # 尝试上传简历
            file_input = await self.page.query_selector(self.selectors["resume_upload"])
            if file_input:
                try:
                    await file_input.set_input_files(resume_path)
                    logger.info("Resume uploaded")
                    await self.random_delay(1, 2)
                except Exception as e:
                    logger.warning(f"Resume upload failed: {e}")

            # 填写常见表单字段
            await self._fill_common_fields()

            # 点击继续/提交按钮
            submit_btn = await self.page.query_selector(self.selectors["submit_button"])
            continue_btn = await self.page.query_selector(self.selectors["continue_button"])

            if submit_btn:
                await submit_btn.click()
                await self.random_delay(2, 3)
            elif continue_btn:
                await continue_btn.click()
                await self.random_delay(1, 2)
            else:
                # 没有找到按钮，可能卡住了
                break

        # 最终检查
        success = await self.page.query_selector(self.selectors["success_indicator"])
        if success:
            return ApplyResult(
                job_info=job,
                status=ApplyStatus.SUCCESS,
                message="Application submitted",
                applied_at=datetime.now(),
            )

        return ApplyResult(
            job_info=job,
            status=ApplyStatus.FAILED,
            message="Easy Apply flow incomplete",
        )

    async def _fill_common_fields(self):
        """填写常见表单字段"""
        # 这里可以根据需要添加更多字段处理
        # 例如电话号码、工作经验年限等

        # 示例：填写电话号码
        phone_input = await self.page.query_selector(self.selectors["phone_input"])
        if phone_input:
            phone = os.getenv("USER_PHONE", "")
            if phone:
                await phone_input.fill(phone)


# 便捷函数
async def search_indeed_jobs(
    keyword: str,
    user_id: str,
    location: Optional[str] = None,
    country: str = "us",
    max_pages: int = 3,
    headless: bool = True,
) -> List[JobInfo]:
    """
    搜索 Indeed 职位（便捷函数）

    Args:
        keyword: 搜索关键词
        user_id: 用户 ID
        location: 工作地点
        country: 国家代码
        max_pages: 最大爬取页数
        headless: 是否无头模式

    Returns:
        职位列表
    """
    scraper = IndeedScraper(
        user_id=user_id,
        headless=headless,
        country=country,
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
