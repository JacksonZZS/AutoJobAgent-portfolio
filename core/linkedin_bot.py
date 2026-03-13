# core/linkedin_bot.py
"""
LinkedIn 职位爬虫和投递机器人
支持 LinkedIn Easy Apply 一键投递
使用 StealthBrowser 绕过反爬检测
"""

import os
import re
import logging
import asyncio
import random
from urllib.parse import quote, urlencode
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

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
from core.stealth_browser import StealthBrowser
from core.history_manager import HistoryManager
from core.rate_limiter import get_rate_limiter, get_circuit_breaker, retry_async

logger = logging.getLogger(__name__)

# 全局限制器
_linkedin_limiter = get_rate_limiter("linkedin")
_linkedin_breaker = get_circuit_breaker("linkedin")

# LinkedIn URL
LINKEDIN_BASE_URL = "https://www.linkedin.com"
LINKEDIN_JOBS_URL = "https://www.linkedin.com/jobs"


class LinkedInScraper:
    """LinkedIn 职位爬虫 - 使用 StealthBrowser 绕过反爬检测"""

    SOURCE = JobSource.LINKEDIN
    BASE_URL = LINKEDIN_BASE_URL

    # LinkedIn 页面选择器 - 2024/2025 更新版 (基于 data 属性和结构，更稳定)
    SELECTORS = {
        # 搜索结果页 - 优先使用 data 属性
        "job_card": '[data-occludable-job-id], .scaffold-layout__list-item, .jobs-search-results__list-item, .job-card-container',
        "job_title": '.artdeco-entity-lockup__title a, .job-card-list__title, a[href*="/jobs/view/"] span, .job-card-container__link',
        "company_name": '.artdeco-entity-lockup__subtitle span, .job-card-container__primary-description, .job-card-container__company-name',
        "location": '.artdeco-entity-lockup__caption span, .job-card-container__metadata-wrapper li, .job-card-container__metadata-item',
        "salary": '.job-card-container__metadata-item--salary, .salary-main-rail__salary-info',
        "posted_date": 'time, .job-card-container__footer-job-state, .job-card-container__listed-time',
        "easy_apply_badge": '.job-card-container__footer-item--easy-apply, [data-is-easy-apply="true"], .jobs-apply-button--easy-apply',

        # 职位详情页
        "jd_content": '.jobs-description__content, .jobs-box__html-content, #job-details, .jobs-description',
        "job_title_detail": '.jobs-unified-top-card__job-title, .t-24.job-details-jobs-unified-top-card__job-title',
        "company_detail": '.jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__company-name',

        # 分页和容器
        "next_page": 'button[aria-label="Next"], .artdeco-pagination__button--next',
        "page_list": '.artdeco-pagination__pages li',
        "job_list_container": '.scaffold-layout__list-container, .jobs-search-results-list',
    }

    def __init__(
        self,
        user_id: str,
        headless: bool = False,
        proxy: Optional[str] = None,
    ):
        self.user_id = user_id
        self.headless = headless
        self.proxy = proxy
        self.history = HistoryManager(user_id=user_id)

        # 使用独立的 LinkedIn profile 目录
        profile_dir = Path(__file__).parent.parent / "chrome_profile" / "linkedin"
        profile_dir.mkdir(parents=True, exist_ok=True)

        # 使用 StealthBrowser
        self.browser = StealthBrowser(
            headless=headless,
            proxy=proxy,
            profile_dir=profile_dir,
        )
        self.page = None

    async def init_browser(self):
        """初始化隐身浏览器"""
        self.page = await self.browser.start()
        return self.page

    async def close(self):
        """关闭浏览器"""
        await self.browser.close()

    async def search_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        page: int = 1,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[JobInfo]:
        """搜索 LinkedIn 职位"""
        # 速率限制检查
        if not _linkedin_breaker.can_execute():
            logger.warning("LinkedIn circuit breaker is OPEN, skipping request")
            return []

        if not await _linkedin_limiter.acquire():
            logger.warning("LinkedIn rate limit exceeded")
            return []

        if not self.page:
            await self.init_browser()

        jobs = []
        filters = filters or {}

        # 构建搜索 URL
        params = {
            "keywords": keyword,
            "start": (page - 1) * 25,  # LinkedIn 每页 25 个结果
        }
        if location:
            params["location"] = location

        # Easy Apply 过滤
        if filters.get("easy_apply_only"):
            params["f_AL"] = "true"

        # 时间过滤: 24小时=r86400, 1周=r604800, 1月=r2592000
        if filters.get("posted_days"):
            days = filters["posted_days"]
            if days <= 1:
                params["f_TPR"] = "r86400"
            elif days <= 7:
                params["f_TPR"] = "r604800"
            else:
                params["f_TPR"] = "r2592000"

        # 工作类型: F=全职, P=兼职, C=合同, T=临时, I=实习
        if filters.get("job_type"):
            job_type_map = {
                "fulltime": "F",
                "parttime": "P",
                "contract": "C",
                "internship": "I",
            }
            params["f_JT"] = job_type_map.get(filters["job_type"], "F")

        search_url = f"{LINKEDIN_JOBS_URL}/search/?{urlencode(params)}"
        logger.info(f"Searching LinkedIn: {search_url}")

        try:
            # 导航到搜索页
            await self.browser.goto(search_url, wait_until="domcontentloaded")
            _linkedin_breaker.record_success()

            # 等待页面加载
            await asyncio.sleep(random.uniform(2, 4))

            # 检查是否需要登录
            if await self._check_login_required():
                logger.warning("LinkedIn requires login to view jobs")
                return []

            # 等待职位卡片加载
            try:
                await self.page.wait_for_selector(
                    self.SELECTORS["job_card"],
                    timeout=15000
                )
            except PlaywrightTimeout:
                logger.warning("No job cards found or timeout")
                return []

            # 滚动加载更多职位
            await self._scroll_to_load_jobs()

            # 获取所有职位卡片
            job_cards = await self.page.query_selector_all(self.SELECTORS["job_card"])
            logger.info(f"Found {len(job_cards)} job cards on page {page}")

            for card in job_cards:
                try:
                    job = await self._parse_job_card(card)
                    if job and not self.history.is_duplicate(job.job_id):
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"Failed to parse job card: {e}")
                    continue

        except PlaywrightTimeout:
            _linkedin_breaker.record_failure()
            logger.warning(f"Timeout loading LinkedIn search page {page}")
        except Exception as e:
            _linkedin_breaker.record_failure()
            logger.error(f"Error searching LinkedIn: {e}")

        return jobs

    async def _check_login_required(self) -> bool:
        """检查是否需要登录"""
        # 检查登录提示
        login_wall = await self.page.query_selector('.authwall-join-form, [data-tracking-control-name="auth_wall"]')
        if login_wall:
            return True

        # 检查 URL 是否被重定向到登录页
        current_url = self.page.url
        if "/login" in current_url or "/authwall" in current_url:
            return True

        return False

    async def _scroll_to_load_jobs(self):
        """滚动页面加载更多职位 - 增强版懒加载处理"""
        # LinkedIn 使用虚拟滚动，需要多次滚动并等待内容渲染
        for i in range(5):
            # 滚动到列表容器底部
            await self.page.evaluate('''() => {
                const container = document.querySelector('.jobs-search-results-list, .scaffold-layout__list-container');
                if (container) {
                    container.scrollTop += container.clientHeight * 0.8;
                } else {
                    window.scrollBy(0, window.innerHeight * 0.8);
                }
            }''')
            await asyncio.sleep(random.uniform(1.0, 1.5))

            # 检查是否有新内容加载
            await self.page.evaluate('''() => {
                // 触发可能的懒加载
                window.dispatchEvent(new Event('scroll'));
            }''')
            await asyncio.sleep(random.uniform(0.3, 0.5))

    async def _parse_job_card(self, card) -> Optional[JobInfo]:
        """解析职位卡片"""
        try:
            # 获取 job_id - 尝试多种属性
            job_id = await card.get_attribute("data-occludable-job-id")
            if not job_id:
                job_id = await card.get_attribute("data-job-id")
            if not job_id:
                # 尝试从链接提取
                link_elem = await card.query_selector("a[href*='/jobs/view/']")
                if link_elem:
                    href = await link_elem.get_attribute("href")
                    match = re.search(r'/jobs/view/(\d+)', href)
                    job_id = match.group(1) if match else None

            if not job_id:
                return None

            # 获取职位标题
            title_elem = await card.query_selector(self.SELECTORS["job_title"])
            if not title_elem:
                return None
            title = await title_elem.inner_text()
            title = title.strip()

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
            job_url = f"{LINKEDIN_BASE_URL}/jobs/view/{job_id}"

            return JobInfo(
                source=JobSource.LINKEDIN,
                job_id=str(job_id),
                title=title,
                company=company,
                location=location,
                job_url=job_url,
                salary_range=salary,
                is_easy_apply=is_easy_apply,
            )

        except Exception as e:
            logger.warning(f"Error parsing LinkedIn job card: {e}")
            return None

    async def get_job_details(self, job_url: str) -> str:
        """获取职位详情 (JD)"""
        if not self.page:
            await self.init_browser()

        try:
            await self.page.goto(job_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 3))

            # 等待 JD 加载
            jd_elem = await self.page.wait_for_selector(
                self.SELECTORS["jd_content"],
                timeout=10000
            )

            if jd_elem:
                jd_text = await jd_elem.inner_text()
                return jd_text.strip()

        except Exception as e:
            logger.warning(f"Failed to get LinkedIn job details: {e}")

        return ""


class LinkedInApplyBot(BaseApplyBot):
    """LinkedIn 投递机器人 - 支持 Easy Apply"""

    SOURCE = JobSource.LINKEDIN

    DEFAULT_SELECTORS = {
        # 登录相关
        "sign_in_button": 'a[href*="login"], .nav__button-secondary',
        "email_input": 'input#username, input[name="session_key"]',
        "password_input": 'input#password, input[name="session_password"]',
        "login_submit": 'button[type="submit"], button[data-litms-control-urn*="login-submit"]',
        "logged_in_indicator": '.global-nav__me, .feed-identity-module',

        # 投递相关
        "apply_button": '.jobs-apply-button, button[data-control-name="jobdetails_topcard_inapply"]',
        "easy_apply_modal": '.jobs-easy-apply-modal, .artdeco-modal',
        "resume_upload": 'input[type="file"], input[name="file"]',
        "continue_button": 'button[aria-label="Continue to next step"], button[data-easy-apply-next-button]',
        "review_button": 'button[aria-label="Review your application"]',
        "submit_button": 'button[aria-label="Submit application"], button[data-control-name="submit_unify"]',
        "done_button": 'button[aria-label="Done"], button[aria-label="Dismiss"]',
        "success_indicator": '.artdeco-inline-feedback--success, [data-test-modal-id="post-apply-modal"]',
        "already_applied": '.artdeco-inline-feedback, span:has-text("Applied")',

        # 表单字段
        "phone_input": 'input[name*="phone"], input[id*="phone"]',
        "additional_questions": '.jobs-easy-apply-form-section__grouping',
        "text_input": 'input[type="text"]:not([readonly])',
        "select_input": 'select',
        "radio_input": 'input[type="radio"]',
        "checkbox_input": 'input[type="checkbox"]',
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
            username=username or os.getenv("LINKEDIN_EMAIL"),
            password=password or os.getenv("LINKEDIN_PASSWORD"),
            headless=headless,
            llm_engine=llm_engine,
            cv_path=cv_path,
            status_manager=status_manager,
        )
        self.history = HistoryManager(user_id=user_id)

        # 使用独立的 LinkedIn profile
        self.profile_dir = Path(__file__).parent.parent / "chrome_profile" / "linkedin"
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    async def init_browser(self):
        """初始化浏览器"""
        self.browser = StealthBrowser(
            headless=self.headless,
            profile_dir=self.profile_dir,
        )
        self.page = await self.browser.start()
        self.context = self.browser.context
        return self.page

    async def close(self):
        """关闭浏览器"""
        if hasattr(self, 'browser'):
            await self.browser.close()

    async def login(self) -> bool:
        """登录 LinkedIn"""
        if not self.context:
            await self.init_browser()

        # 先检查是否已登录
        try:
            await self.page.goto(LINKEDIN_BASE_URL, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            logged_in = await self.page.query_selector(self.selectors["logged_in_indicator"])
            if logged_in:
                logger.info("Already logged in to LinkedIn")
                self.is_logged_in = True
                return True
        except Exception:
            pass

        if not self._username or not self._password:
            logger.warning("LinkedIn credentials not provided")
            return False

        try:
            # 导航到登录页
            login_url = f"{LINKEDIN_BASE_URL}/login"
            await self.page.goto(login_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # 填写邮箱
            await self.safe_fill(self.selectors["email_input"], self._username)
            await self.random_delay(0.5, 1)

            # 填写密码
            await self.safe_fill(self.selectors["password_input"], self._password)
            await self.random_delay(0.5, 1)

            # 提交登录
            await self.safe_click(self.selectors["login_submit"])
            await asyncio.sleep(3)

            # 检查登录状态
            logged_in = await self.page.query_selector(self.selectors["logged_in_indicator"])
            if logged_in:
                logger.info("Successfully logged in to LinkedIn")
                self.is_logged_in = True
                return True

            # 检查是否有验证码或安全检查
            security_check = await self.page.query_selector('[data-test="challenge"]')
            if security_check:
                logger.warning("LinkedIn security challenge detected - manual verification required")
                # 等待用户手动验证
                await asyncio.sleep(30)
                return await self._check_login_status()

            logger.warning("LinkedIn login failed")
            return False

        except Exception as e:
            logger.error(f"LinkedIn login error: {e}")
            return False

    async def _check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            await self.page.goto(LINKEDIN_BASE_URL, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            logged_in = await self.page.query_selector(self.selectors["logged_in_indicator"])
            self.is_logged_in = logged_in is not None
            return self.is_logged_in
        except Exception:
            return False

    async def check_already_applied(self, job: JobInfo) -> bool:
        """检查是否已投递"""
        # 先检查本地历史
        if self.history.is_duplicate(job.job_id):
            return True

        # 检查页面上的已投递标记
        try:
            await self.page.goto(job.job_url, wait_until="domcontentloaded")
            await asyncio.sleep(1)

            already_applied = await self.page.query_selector(self.selectors["already_applied"])
            if already_applied:
                text = await already_applied.inner_text()
                if "Applied" in text:
                    return True
            return False
        except Exception:
            return False

    async def apply(
        self,
        job: JobInfo,
        resume_path: str,
        cover_letter_path: Optional[str] = None,
    ) -> ApplyResult:
        """投递 LinkedIn 职位"""
        if not self.context:
            await self.init_browser()

        # 确保已登录
        if not self.is_logged_in:
            login_success = await self.login()
            if not login_success:
                return ApplyResult(
                    job_info=job,
                    status=ApplyStatus.FAILED,
                    message="Not logged in to LinkedIn",
                )

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

            # 检查是否是 Easy Apply
            apply_button = await self.page.query_selector(self.selectors["apply_button"])
            if not apply_button:
                return ApplyResult(
                    job_info=job,
                    status=ApplyStatus.FAILED,
                    message="Could not find Apply button - may require external application",
                )

            # 检查按钮文本
            button_text = await apply_button.inner_text()
            if "Easy Apply" not in button_text and "申请" not in button_text:
                return ApplyResult(
                    job_info=job,
                    status=ApplyStatus.SKIPPED,
                    message="Not an Easy Apply job - requires external application",
                )

            # 点击 Apply 按钮
            await apply_button.click()
            await self.random_delay(2, 3)

            # 处理 Easy Apply 流程
            result = await self._handle_easy_apply_flow(job, resume_path)
            return result

        except Exception as e:
            logger.error(f"LinkedIn apply error: {e}")
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
        """处理 LinkedIn Easy Apply 流程"""
        max_steps = 10

        for step in range(max_steps):
            logger.info(f"LinkedIn Easy Apply step {step + 1}")
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
                    "source": "linkedin",
                })

                # 关闭成功对话框
                done_btn = await self.page.query_selector(self.selectors["done_button"])
                if done_btn:
                    await done_btn.click()

                return ApplyResult(
                    job_info=job,
                    status=ApplyStatus.SUCCESS,
                    message="Application submitted successfully",
                    resume_path=resume_path,
                    applied_at=datetime.now(),
                )

            # 检查是否有模态框
            modal = await self.page.query_selector(self.selectors["easy_apply_modal"])
            if not modal:
                logger.warning("Easy Apply modal not found")
                break

            # 尝试上传简历
            file_input = await self.page.query_selector(self.selectors["resume_upload"])
            if file_input:
                try:
                    await file_input.set_input_files(resume_path)
                    logger.info("Resume uploaded")
                    await self.random_delay(1, 2)
                except Exception as e:
                    logger.warning(f"Resume upload failed: {e}")

            # 填写表单字段
            await self._fill_form_fields()

            # 点击下一步/提交按钮
            submit_btn = await self.page.query_selector(self.selectors["submit_button"])
            review_btn = await self.page.query_selector(self.selectors["review_button"])
            continue_btn = await self.page.query_selector(self.selectors["continue_button"])

            if submit_btn:
                await submit_btn.click()
                await self.random_delay(2, 3)
            elif review_btn:
                await review_btn.click()
                await self.random_delay(1, 2)
            elif continue_btn:
                await continue_btn.click()
                await self.random_delay(1, 2)
            else:
                # 没有找到按钮，可能卡住了
                logger.warning("No navigation button found")
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
            message="Easy Apply flow incomplete - may require manual review",
        )

    async def _fill_form_fields(self):
        """填写表单字段"""
        try:
            # 填写电话号码
            phone_input = await self.page.query_selector(self.selectors["phone_input"])
            if phone_input:
                phone = os.getenv("USER_PHONE", "")
                if phone:
                    current_value = await phone_input.input_value()
                    if not current_value:
                        await phone_input.fill(phone)

            # 处理单选按钮 (通常选第一个选项)
            radio_groups = await self.page.query_selector_all('fieldset')
            for group in radio_groups:
                radios = await group.query_selector_all(self.selectors["radio_input"])
                if radios and len(radios) > 0:
                    first_radio = radios[0]
                    is_checked = await first_radio.is_checked()
                    if not is_checked:
                        await first_radio.click()

            # 处理下拉选择 (通常选第一个非空选项)
            selects = await self.page.query_selector_all(self.selectors["select_input"])
            for select in selects:
                options = await select.query_selector_all("option")
                if len(options) > 1:
                    # 选择第一个有值的选项
                    await select.select_option(index=1)

        except Exception as e:
            logger.warning(f"Error filling form fields: {e}")


# 便捷函数
async def search_linkedin_jobs(
    keyword: str,
    user_id: str,
    location: Optional[str] = None,
    max_pages: int = 3,
    headless: bool = True,
    easy_apply_only: bool = True,
) -> List[JobInfo]:
    """
    搜索 LinkedIn 职位（便捷函数）

    Args:
        keyword: 搜索关键词
        user_id: 用户 ID
        location: 工作地点
        max_pages: 最大爬取页数
        headless: 是否无头模式
        easy_apply_only: 只搜索 Easy Apply 职位

    Returns:
        职位列表
    """
    scraper = LinkedInScraper(
        user_id=user_id,
        headless=headless,
    )

    all_jobs = []
    filters = {"easy_apply_only": easy_apply_only}

    try:
        for page in range(1, max_pages + 1):
            jobs = await scraper.search_jobs(keyword, location, page, filters)
            all_jobs.extend(jobs)
            logger.info(f"Page {page}: found {len(jobs)} jobs, total: {len(all_jobs)}")

            if len(jobs) == 0:
                break

            await asyncio.sleep(random.uniform(2, 4))
    finally:
        await scraper.close()

    return all_jobs
