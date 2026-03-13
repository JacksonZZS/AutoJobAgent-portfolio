# core/apply_bot.py
"""
JobsDB 自动投递机器人
使用 Playwright 实现自动化投递功能

NOTE: Methods have been extracted into Mixin classes in core/apply/ package.
This file remains the canonical import path for backward compatibility.
"""

import os
import json
import logging
import time
import re
import hashlib
import base64
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from enum import Enum

from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from playwright.async_api import async_playwright
from jinja2 import Environment, FileSystemLoader
import asyncio

# Import HistoryManager for unified history tracking
from core.history_manager import HistoryManager
# Import InteractionManager for Web-based interaction control
from core.interaction_manager import get_interaction_manager
# Import StatusManager for real-time stats updates
from core.status_manager import get_status_manager

# Import Mixins
from core.apply.pdf_mixin import PDFGenerationMixin
from core.apply.browser_mixin import BrowserManagementMixin
from core.apply.dedup_mixin import DedupMixin
from core.apply.hud_mixin import HUDMixin
from core.apply.auth_mixin import AuthMixin
from core.apply.cover_letter_mixin import CoverLetterMixin

logger = logging.getLogger(__name__)

# 🔴 配置常量：AI 评分阈值
AI_SCORE_THRESHOLD = 25  # 只有评分 >= 70 的职位才启动浏览器投递

# 🔴 配置常量：搜索词自动切换阈值
EMPTY_PAGE_LIMIT = 2  # 连续 N 页低产出时，自动切换到下一个搜索词
LOW_YIELD_THRESHOLD = 3  # 新职位数量少于此值，视为"低产出页面"
HIGH_YIELD_THRESHOLD = 4  # 新职位数量达到此值，视为"高产出"，重置计数器


# Re-export models for backward compatibility
from core.models import ApplyStatus, ApplyJobInfo, ApplyResult


class JobsDBApplyBot(
    PDFGenerationMixin, BrowserManagementMixin, DedupMixin,
    HUDMixin, AuthMixin, CoverLetterMixin
):
    """JobsDB 自动投递机器人"""

    # 默认选择器配置
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

        # 其他
        "captcha_indicator": '[class*="captcha"], [id*="captcha"], iframe[src*="captcha"]',
        "modal_close": 'button[data-automation="modal-close"]',
    }

    def __init__(
        self,
        username: str = None,
        password: str = None,
        cookie_path: str = None,
        selectors: Dict[str, str] = None,
        llm_engine = None,
        headless: bool = False,
        cv_path: str = None,
        allow_manual_captcha: bool = True,
        captcha_timeout: int = 300,
        keywords: List[str] = None,
        limit: int = 100,
        status_manager = None,
        user_id: str = None  # 🔴 新增：用户 ID 参数
    ):
        """
        初始化投递机器人（支持多用户数据隔离）

        Args:
            username: JobsDB 账号（邮箱）
            password: JobsDB 密码
            cookie_path: Cookie 保存路径
            selectors: CSS 选择器配置
            llm_engine: LLM 引擎实例，用于生成 Cover Letter
            headless: 是否无头模式运行
            cv_path: 简历 PDF 文件路径
            allow_manual_captcha: 是否允许手动处理验证码（默认 True）
            captcha_timeout: 验证码处理超时时间（秒，默认 300）
            keywords: 搜索关键词列表
            limit: 目标成功投递数量
            status_manager: 状态管理器实例（用于实时进度同步）
            user_id: 用户 ID，用于多用户数据隔离
        """
        self.username = username or os.getenv("JOBSDB_USERNAME", "")
        self.password = password or os.getenv("JOBSDB_PASSWORD", "")
        self.user_id = user_id or "default"  # 🔴 保存 user_id

        # 🔴 注意：使用 persistent_context 后，不再需要 cookie_path
        # 浏览器会自动保存所有 Session 到 data/browser_profiles/{user_id}/
        # 保留 cookie_path 仅用于向后兼容，但实际不使用
        if cookie_path:
            self.cookie_path = Path(cookie_path)
        else:
            self.cookie_path = Path(f"data/sessions/cookies_{self.user_id}.json")

        self.selectors = {**self.DEFAULT_SELECTORS, **(selectors or {})}
        self.llm_engine = llm_engine
        self.headless = headless
        self.cv_path = cv_path
        self.allow_manual_captcha = allow_manual_captcha
        self.captcha_timeout = captcha_timeout
        self.status_manager = status_manager  # 状态管理器

        # 目标驱动参数
        self.keywords = keywords or ["Python Developer"]
        self.limit = limit
        self.success_count = 0

        # 🔴 新增：翻页记忆与关键词熔断机制
        self.exhausted_keywords: Set[str] = set()  # 已枯竭的关键词集合
        self.current_page_map: Dict[str, int] = {}  # 每个关键词的当前页码记忆

        # Playwright 相关
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # 🔴 职位去重相关 - 使用用户专属的 HistoryManager
        self.history_manager = HistoryManager(user_id=self.user_id)

        # 保留旧的 job_history 系统用于向后兼容，但主要使用 HistoryManager
        self.job_history_path = Path("data/job_history.json")
        self._processed_job_ids: Set[str] = set()

        # 注意：使用 persistent_context 后，不再需要手动创建 cookie 目录
        # 浏览器配置会自动保存到 data/browser_profiles/{user_id}/

        # 确保 job_history 目录存在并加载历史记录
        self.job_history_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_job_history()

        logger.info(f"JobsDBApplyBot initialized for user: {self.user_id}")
        logger.info(f"Browser profile: data/browser_profiles/{self.user_id}/")
        logger.info(f"Loaded {len(self._processed_job_ids)} processed job IDs from local history")
        logger.info(f"HistoryManager has {len(self.history_manager.history)} records")
        logger.info(f"Target: {self.limit} successful applications with keywords: {self.keywords}")


    # 🔴 以下 Cookie 函数已弃用（使用 persistent_context 后不再需要）
    # 保留代码仅用于参考，实际不会被调用

    def _load_cookies(self):
        """【已弃用】加载保存的 cookies - 使用 persistent_context 后不再需要"""
        logger.debug("_load_cookies() is deprecated when using persistent_context")
        # 注释掉实际代码，避免误用
        # if self.cookie_path.exists():
        #     try:
        #         with open(self.cookie_path, 'r') as f:
        #             cookies = json.load(f)
        #         self._context.add_cookies(cookies)
        #         logger.info(f"Loaded {len(cookies)} cookies from {self.cookie_path}")
        #     except Exception as e:
        #         logger.warning(f"Failed to load cookies: {e}")

    def _save_cookies(self):
        """【已弃用】保存 cookies - 使用 persistent_context 后不再需要"""
        logger.debug("_save_cookies() is deprecated when using persistent_context")
        # 注释掉实际代码，避免误用
        # try:
        #     cookies = self._context.cookies()
        #     with open(self.cookie_path, 'w') as f:
        #         json.dump(cookies, f, indent=2)
        #     try:
        #         os.chmod(self.cookie_path, 0o600)
        #         logger.info(f"Saved {len(cookies)} cookies to {self.cookie_path} with restricted permissions (600)")
        #     except Exception as perm_error:
        #         logger.warning(f"Cookies saved but failed to set permissions: {perm_error}")
        # except Exception as e:
        #     logger.warning(f"Failed to save cookies: {e}")


    def apply_to_job(
        self,
        job_info: ApplyJobInfo,
        candidate_profile: dict = None,
        cover_letter: str = None
    ) -> ApplyResult:
        """
        用户自主投递模式：仅生成定制化简历和求职信 PDF，不启动浏览器，不自动投递

        服务器职责：
        1. 生成个性化 CV/CL 物料
        2. 保存到用户专属目录
        3. 更新状态管理器，触发 Dashboard 物料中心显示

        用户职责：
        1. 在 Dashboard 物料中心下载物料
        2. 在自己的浏览器中登录 JobsDB
        3. 手动完成投递

        Args:
            job_info: 职位信息
            candidate_profile: 候选人信息（用于生成 Cover Letter）
            cover_letter: 预生成的 Cover Letter（可选）

        Returns:
            投递结果
        """
        logger.info(f"🤖 [用户自主投递模式] 准备生成物料: {job_info.title} at {job_info.company}")

        # 更新状态：开始生成文件
        if self.status_manager:
            self.status_manager.update(
                status="generating",  # TaskStatus.GENERATING
                message=f"正在为 {job_info.company} - {job_info.title} 生成简历",
                step="resume_generation",
                current_job={"title": job_info.title, "company": job_info.company}
            )

        try:
            # ========== 辅助函数：清理文件名 ==========
            def sanitize_filename(text: str, max_length: int = 50) -> str:
                """
                清理文件名，移除非法字符

                Args:
                    text: 原始文本
                    max_length: 最大长度

                Returns:
                    清理后的文件名
                """
                # 移除或替换非法字符（保留字母、数字、空格、连字符、下划线）
                cleaned = re.sub(r'[^\w\s\-]', '', text)
                # 将多个空格替换为单个下划线
                cleaned = re.sub(r'\s+', '_', cleaned)
                # 移除首尾的下划线和空格
                cleaned = cleaned.strip('_').strip()
                # 限制长度
                return cleaned[:max_length] if cleaned else "Unknown"

            # ========== 第一步：创建任务文件夹 ==========
            # 🔴 关键改动：使用 username 而不是 user_id 作为目录名
            from core.user_identity import get_username

            username = get_username(self.user_id)

            # 清理文件名，移除特殊字符
            # 公司名限制为 30 字符，职位名限制为 40 字符（确保总长度不超过 100）
            c_name = sanitize_filename(job_info.company, max_length=30)
            j_title = sanitize_filename(job_info.title, max_length=40)

            # 🔴 新格式：data/outputs/{username}/{c_name}_{j_title}
            job_folder = Path(f"data/outputs/{username}/{c_name}_{j_title}")
            job_folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"[User: {username}] 📁 创建任务文件夹: {job_folder}")

            # 🎯 HUD 更新：开始分析职位
            self._update_hud("🤖 AI 正在分析职位 & 生成简历...", status="processing")

            # ========== 第二步：生成定制化简历 PDF ==========
            generated_resume_path = None

            if candidate_profile and self.llm_engine:
                try:
                    # 🔴 使用用户真实姓名作为文件名
                    from core.user_identity import get_real_name

                    real_name = get_real_name(self.user_id)
                    # 清理姓名中的特殊字符
                    safe_name = sanitize_filename(real_name, max_length=30)

                    # 新的文件命名格式：{公司名}_{职位}.pdf
                    resume_filename = f"Resume_{c_name}_{j_title}.pdf"
                    resume_pdf_path = job_folder / resume_filename
                    logger.info(f"[User: {username}] 🤖 正在调用 LLM 生成定制化简历...")

                    generated_resume_path = self._generate_custom_resume_pdf(
                        candidate_profile=candidate_profile,
                        job_info=job_info,
                        output_path=str(resume_pdf_path)
                    )

                    logger.info(f"[User: {username}] ✅ 定制化简历已生成: {generated_resume_path}")
                except Exception as e:
                    logger.warning(f"[User: {username}] ⚠️ 生成定制化简历失败: {e}")
                    # 如果生成失败，使用原始简历
                    if self.cv_path and Path(self.cv_path).exists():
                        generated_resume_path = self.cv_path
                        logger.info(f"[User: {username}] 📂 使用原始简历: {generated_resume_path}")
            elif self.cv_path and Path(self.cv_path).exists():
                generated_resume_path = self.cv_path
                logger.info(f"[User: {username}] 📂 使用原始简历: {generated_resume_path}")

            # ========== 第三步：生成求职信 PDF ==========
            generated_cl_path = None

            if not cover_letter and candidate_profile:
                logger.info(f"[User: {username}] 📝 正在生成定制化求职信...")
                cover_letter = self.generate_cover_letter(candidate_profile, job_info)

            if cover_letter:
                try:
                    # 🔴 使用用户真实姓名作为文件名
                    from core.user_identity import get_real_name

                    real_name = get_real_name(self.user_id)
                    safe_name = sanitize_filename(real_name, max_length=30)

                    # 新的文件命名格式：{公司名}_{职位}.pdf
                    cl_filename = f"Cover_Letter_{c_name}_{j_title}.pdf"
                    cl_pdf_path = job_folder / cl_filename

                    generated_cl_path = self._generate_cover_letter_pdf(
                        cover_letter_text=cover_letter,
                        job_info=job_info,
                        output_path=str(cl_pdf_path)
                    )

                    logger.info(f"[User: {username}] ✅ 求职信 PDF 已生成: {generated_cl_path}")
                except Exception as e:
                    logger.warning(f"[User: {username}] ⚠️ 生成求职信 PDF 失败: {e}")
                    # 保存为 TXT 作为备份
                    try:
                        cl_txt_filename = f"Cover_Letter_{safe_name}_{c_name}_{j_title}.txt"
                        cl_txt_path = job_folder / cl_txt_filename
                        with open(cl_txt_path, 'w', encoding='utf-8') as f:
                            f.write(cover_letter)
                        generated_cl_path = str(cl_txt_path)
                        logger.info(f"📂 求职信已保存为 TXT: {generated_cl_path}")
                    except Exception as txt_error:
                        logger.error(f"❌ 保存求职信 TXT 失败: {txt_error}")

            if self.status_manager:
                self.status_manager.set_manual_review(
                    job_title=job_info.title,
                    company_name=job_info.company,
                    job_url=job_info.job_url,
                    resume_path=str(generated_resume_path) if generated_resume_path else "",
                    cl_path=str(generated_cl_path) if generated_cl_path else "",
                    score=job_info.score,
                    dimensions={}
                )
                logger.info("✅ 已更新 Dashboard 物料中心状态")

            # 🚀 [交互模式] 强制启动有头浏览器
            logger.info("🚀 [交互模式] 正在启动浏览器以进行辅助投递...")

            try:
                if not self._is_browser_ready():
                    # 直接使用 sync_playwright 启动浏览器（不依赖 browser_pool）
                    from core.user_identity import get_username
                    username = get_username(self.user_id)
                    user_data_dir = Path(f"data/browser_profiles/{username}")
                    user_data_dir.mkdir(parents=True, exist_ok=True)

                    # 清理 SingletonLock
                    singleton_lock = user_data_dir / "SingletonLock"
                    singleton_socket = user_data_dir / "SingletonSocket"
                    if singleton_lock.exists():
                        singleton_lock.unlink()
                    if singleton_socket.exists():
                        singleton_socket.unlink()

                    logger.info(f"[交互模式] 使用持久化配置: {user_data_dir}")

                    if self._playwright is None:
                        self._playwright = sync_playwright().start()

                    self._context = self._playwright.chromium.launch_persistent_context(
                        str(user_data_dir),
                        headless=False,
                        # channel='chrome',  # 🔴 移除！使用 Playwright 自带 Chromium，不影响系统 Chrome
                        devtools=False,
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
                        args=[
                            '--window-position=0,0',
                            '--disable-blink-features=AutomationControlled',
                            '--no-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-gpu',
                            '--disable-software-rasterizer'
                        ],
                        ignore_default_args=['--enable-automation']
                    )

                    # 注入反检测脚本
                    self._context.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                    """)

                    # 获取页面
                    if len(self._context.pages) > 0:
                        self._page = self._context.pages[0]
                    else:
                        self._page = self._context.new_page()

                    logger.info("✅ 浏览器已启动（有头模式）")

                self._page.goto(job_info.job_url)
            except Exception as browser_error:
                # 🔴 优雅处理：用户关闭浏览器是正常行为，不应报错
                error_msg = str(browser_error)
                if "Target page, context or browser has been closed" in error_msg or \
                   "has been closed" in error_msg or \
                   "Target closed" in error_msg:
                    logger.info("ℹ️ 浏览器已被用户关闭，跳过页面导航（这是正常行为）")
                else:
                    logger.warning(f"⚠️ 浏览器操作异常: {browser_error}")

            import shutil
            
            # 1. 同步简历
            if generated_resume_path and Path(generated_resume_path).exists():
                # 确保目标在 outputs/任务文件夹 下
                if str(job_folder) not in str(generated_resume_path):
                    target_resume = job_folder / f"Resume_{safe_name}.pdf"
                    shutil.copy(generated_resume_path, target_resume)
                    generated_resume_path = str(target_resume)
                    logger.info(f"📂 [同步] 简历已归档至: {target_resume.name}")

            # 2. 同步求职信 (注意变量名: cover_letter_path 或 generated_cl_path)
            # 假设你之前定义的是 cover_letter_path
            cl_source = locals().get('cover_letter_path') or locals().get('generated_cl_path')
            if cl_source and Path(cl_source).exists():
                if str(job_folder) not in str(cl_source):
                    target_cl = job_folder / f"Cover_Letter_{safe_name}.pdf"
                    shutil.copy(cl_source, target_cl)
                    generated_cl_path = str(target_cl) # 更新变量给 HUD 用
                    logger.info(f"📂 [同步] 求职信已归档至: {target_cl.name}")
            # =================================================================

            # 🎯 HUD 更新：文件生成完成
            self._update_hud("📂 文件已生成！请在浏览器中完成投递", status="info", resume_path=generated_resume_path, cl_path=generated_cl_path)

            logger.info(f"📦 [交互模式] 物料已生成，浏览器已打开职位页面")

            # 🔴 创建 UI 交互信号文件
            lock_dir = Path("data/locks")
            lock_dir.mkdir(parents=True, exist_ok=True)
            lock_file = lock_dir / f"user_interaction_{self.user_id}.lock"

            # 写入锁文件，包含职位信息
            lock_data = {
                "job_title": job_info.title,
                "company": job_info.company,
                "job_url": job_info.job_url,
                "resume_path": str(generated_resume_path) if generated_resume_path else "",
                "cl_path": str(generated_cl_path) if generated_cl_path else "",
                "created_at": datetime.now().isoformat()
            }

            with open(lock_file, 'w', encoding='utf-8') as f:
                json.dump(lock_data, f, indent=2, ensure_ascii=False)

            logger.info(f"🔒 [UI 信号] 已创建交互锁文件: {lock_file}")
            logger.info(f"⏸️ [UI 信号] 等待用户在 Dashboard 确认完成投递...")

            # 🔴 阻塞等待：直到 Dashboard 删除锁文件
            wait_count = 0  # 🔴 修复：初始化 wait_count 变量
            while lock_file.exists():
                time.sleep(1)
                wait_count += 1
                # 🔴 [修复] 删除 waiting_user 状态更新，避免覆盖 manual_review 状态
                # 已经通过 set_manual_review() 设置了正确的状态，不需要在循环中反复更新
                # 这会导致 manual_review_data 丢失，造成远程物料中心的按钮消失
                # if self.status_manager and wait_count % 2 == 0:
                #     self.status_manager.update(
                #         status="waiting_user",
                #         message=f"等待用户确认 ({wait_count}s)... 请在 Dashboard 下载简历并投递",
                #         step="human_interaction"
                #     )
            logger.info(f"✅ [UI 信号] 用户已确认完成投递，继续下一个职位")

            # 更新状态：等待用户操作
            # ========== 第五步：更新状态管理器，触发物料中心显示 ==========
            if self.status_manager:
                self.status_manager.set_manual_review(
                    score=0,  # 评分已在外部完成
                    dimensions=[],
                    job_url=job_info.job_url,
                    job_title=job_info.title,
                    company_name=job_info.company,
                    resume_path=str(generated_resume_path) if generated_resume_path else "",
                    cl_path=str(generated_cl_path) if generated_cl_path else "",
                    cl_text=cover_letter or ""
                )

            # ========== 第六步：记录物料生成成功 ==========
            logger.info(f"✅ [User: {username}] 物料生成完成，等待用户在 Dashboard 下载并投递")
            logger.info(f"   📋 职位: {job_info.title}")
            logger.info(f"   🏢 公司: {job_info.company}")
            logger.info(f"   🔗 链接: {job_info.job_url}")
            logger.info(f"   📁 文件夹: {job_folder}")

            if generated_resume_path:
                logger.info(f"   ✅ 定制化简历 PDF: {generated_resume_path}")
            if generated_cl_path:
                logger.info(f"   ✅ 求职信 PDF: {generated_cl_path}")

            # 🔴 [修复] 等待用户在 Dashboard 物料中心做出决策
            logger.info(f"[User: {username}] ⏳ 等待用户决策...")

            decision = self._wait_for_user_decision(timeout=600)

            # 根据用户决策返回不同的状态
            if decision == "APPLY":
                logger.info(f"[User: {username}] ✅ 用户确认投递")

                # 🔴 修复：保存到历史记录
                self.history_manager.add_job(
                    link=job_info.job_url,
                    title=job_info.title,
                    company=job_info.company,
                    status="success",
                    score=job_info.score,
                    reason="User confirmed apply via Dashboard",
                    resume_path=str(generated_resume_path) if generated_resume_path else None,
                    cl_path=str(generated_cl_path) if generated_cl_path else None
                )
                logger.info(f"[User: {username}] 📝 已保存到历史记录")

                return ApplyResult(
                    job_info=job_info,
                    status=ApplyStatus.SUCCESS,
                    message="User confirmed apply via Dashboard",
                    cover_letter=cover_letter or "",
                    applied_at=datetime.now()
                )
            elif decision in ["SKIP_PERMANENT", "SKIP_TEMPORARY"]:
                logger.info(f"[User: {username}] ⏭️ 用户跳过投递 ({decision})")
                return ApplyResult(
                    job_info=job_info,
                    status=ApplyStatus.SKIPPED,
                    message=f"User skipped via Dashboard ({decision})",
                    cover_letter=cover_letter or ""
                )
            else:
                # 超时或取消
                logger.warning(f"[User: {username}] ⏱️ 用户决策超时或取消")
                return ApplyResult(
                    job_info=job_info,
                    status=ApplyStatus.FAILED,
                    message="User decision timeout or cancelled",
                    cover_letter=cover_letter or ""
                )

        except Exception as e:
            logger.error(f"❌ 辅助投递流程出错: {e}")
            return ApplyResult(
                job_info=job_info,
                status=ApplyStatus.FAILED,
                message=str(e)
            )

    def _wait_for_user_decision(self, timeout: int = 600) -> Optional[str]:
        """
        等待用户在 Dashboard 中做出决策（用于半自动模式）

        Args:
            timeout: 超时时间（秒），默认 600 秒（10 分钟）

        Returns:
            "APPLY" | "SKIP_PERMANENT" | "SKIP_TEMPORARY" | None（超时）
        """
        import time

        start_time = time.time()
        logger.info(f"[User: {self.username}] Waiting for user decision (timeout: {timeout}s)...")

        while time.time() - start_time < timeout:
            # 检查状态管理器中的决策
            if self.status_manager:
                decision = self.status_manager.get_manual_decision()

                # 🔴 [修复] 识别所有三种决策类型
                if decision in ["APPLY", "SKIP", "SKIP_PERMANENT", "SKIP_TEMPORARY"]:
                    logger.info(f"[User: {self.username}] User decision received: {decision}")
                    # 清除决策状态
                    self.status_manager.clear_manual_review()
                    return decision

            # 每秒检查一次
            time.sleep(1)

        # 超时
        logger.warning(f"[User: {self.username}] User decision timeout after {timeout}s")
        return None

    def auto_apply_for_jobs(
        self,
        jobs: List[ApplyJobInfo],
        candidate_profile: dict = None,
        delay_between_jobs: float = 5.0,
        block_list: Optional[List[str]] = None,
        title_exclusions: Optional[List[str]] = None
    ) -> List[ApplyResult]:
        """
        批量处理职位投递

        Args:
            jobs: 待投递的职位列表
            candidate_profile: 候选人信息
            delay_between_jobs: 每次投递之间的延迟（秒）
            block_list: 公司黑名单列表
            title_exclusions: 职位标题排除词列表

        Returns:
            投递结果列表
        """
        results = []
        total = len(jobs)

        logger.info(f"Starting auto-apply for {total} jobs...")

        # 归一化过滤列表（转小写，去空格）
        def normalize_list(words: Optional[List[str]]) -> List[str]:
            if not words:
                return []
            return [w.strip().lower() for w in words if w.strip()]

        normalized_block_list = normalize_list(block_list)
        normalized_title_exclusions = normalize_list(title_exclusions)

        logger.info(f"Filter settings - Blocked companies: {normalized_block_list}")
        logger.info(f"Filter settings - Title exclusions: {normalized_title_exclusions}")

        for i, job in enumerate(jobs, 1):
            logger.info(f"Processing job {i}/{total}: {job.title} at {job.company}")

            # 提取职位 ID 并检查是否已处理
            job_id = self._extract_job_id(job.job_url)

            if self._is_job_processed(job_id, title=job.title, company=job.company):
                logger.debug(f"🚫 跳过 (历史已处理): {job.title} (ID: {job_id})")
                results.append(ApplyResult(
                    job_info=job,
                    status=ApplyStatus.SKIPPED,
                    message=f"Already processed in history (ID: {job_id})"
                ))
                continue

            # 检查公司黑名单
            company_lower = job.company.lower()
            if any(blocked in company_lower for blocked in normalized_block_list):
                logger.info(f"Skipped blocked company: {job.company}")
                results.append(ApplyResult(
                    job_info=job,
                    status=ApplyStatus.SKIPPED,
                    message=f"Blocked company: {job.company}"
                ))
                # 标记为已处理，避免下次再检查
                self._mark_job_processed(job_id)
                continue

            # 检查职位标题排除词
            title_lower = job.title.lower()
            matched_exclusion = None
            for exclusion in normalized_title_exclusions:
                if exclusion in title_lower:
                    matched_exclusion = exclusion
                    break

            if matched_exclusion:
                logger.info(f"Skipped title: {job.title} (Contains: {matched_exclusion})")
                results.append(ApplyResult(
                    job_info=job,
                    status=ApplyStatus.SKIPPED,
                    message=f"Title contains excluded word: {matched_exclusion}"
                ))
                # 标记为已处理，避免下次再检查
                self._mark_job_processed(job_id)
                continue

            try:
                result = self.apply_to_job(job, candidate_profile)
                results.append(result)

                # 无论投递成功与否，都标记为已处理
                self._mark_job_processed(job_id)

                # 记录结果
                if result.status == ApplyStatus.SUCCESS:
                    logger.info(f"✓ [{i}/{total}] Applied: {job.title}")
                elif result.status == ApplyStatus.ALREADY_APPLIED:
                    logger.info(f"○ [{i}/{total}] Already applied: {job.title}")
                elif result.status == ApplyStatus.SKIPPED:
                    logger.info(f"⊘ [{i}/{total}] Skipped: {job.title} - {result.message}")
                else:
                    logger.warning(f"✗ [{i}/{total}] Failed: {job.title} - {result.message}")

                # 延迟，避免被检测
                if i < total:
                    logger.debug(f"Waiting {delay_between_jobs}s before next application...")
                    time.sleep(delay_between_jobs)

            except Exception as e:
                logger.error(f"Error processing job {job.title}: {e}")
                # 即使出错也标记为已处理，避免重复尝试
                self._mark_job_processed(job_id)
                results.append(ApplyResult(
                    job_info=job,
                    status=ApplyStatus.FAILED,
                    message=str(e)
                ))

        # 汇总结果
        success_count = sum(1 for r in results if r.status == ApplyStatus.SUCCESS)
        already_count = sum(1 for r in results if r.status == ApplyStatus.ALREADY_APPLIED)
        skipped_count = sum(1 for r in results if r.status == ApplyStatus.SKIPPED)
        failed_count = sum(1 for r in results if r.status == ApplyStatus.FAILED)

        logger.info("=" * 50)
        logger.info(f"Auto-apply completed!")
        logger.info(f"  Success: {success_count}")
        logger.info(f"  Already applied: {already_count}")
        logger.info(f"  Skipped: {skipped_count}")
        logger.info(f"  Failed: {failed_count}")
        logger.info("=" * 50)

        return results


    def stream_apply_with_target(
        self,
        scraper_func,
        candidate_profile: dict = None,
        delay_between_jobs: float = 5.0,
        block_list: list = None,
        title_exclusions: list = None,
        page_size: int = 100
    ) -> list:
        """
        [完整修复版] 目标驱动流式投递
        包含：步进式翻页 + 列表级去重 + 完整投递业务逻辑
        """
        import time
        

        # --- 1. 初始化与归一化 ---
        # 确保每个关键词都有起始页
        for kw in self.keywords:
            if kw not in self.current_page_map:
                self.current_page_map[kw] = 1

        def normalize_list(words):
            return [w.strip().lower() for w in words if w and w.strip()] if words else []

        normalized_block_list = normalize_list(block_list)
        normalized_title_exclusions = normalize_list(title_exclusions)

        results = []
        low_yield_counters = {kw: 0 for kw in self.keywords} # 本地计数器

        logger.info("=" * 60)
        logger.info(f"🚀 启动步进式投递 (Full Logic)，目标: {self.limit}")
        logger.info("=" * 60)

        # --- 2. 外层循环：目标驱动 ---
        while self.success_count < self.limit:
            
            # 全局熔断
            if len(self.exhausted_keywords) == len(self.keywords):
                logger.warning("🛑 所有关键词均已枯竭。任务结束。")
                break

            processed_any_job_in_this_round = False

            # --- 3. 关键词轮询 ---
            for current_keyword in self.keywords:
                if current_keyword in self.exhausted_keywords: continue

                # 读取页码 (绝不回退)
                current_physical_page = self.current_page_map[current_keyword]
                logger.info(f"🔄 搜索关键词: '{current_keyword}' (第 {current_physical_page} 页)")

                try:
                    # [Step 1] 抓取
                    jobs_on_page = scraper_func(
                        keyword=current_keyword,
                        page=current_physical_page,
                        page_size=page_size
                    )
                    
                    if not jobs_on_page:
                        logger.warning(f"🛑 关键词 '{current_keyword}' 无数据，标记枯竭")
                        self.exhausted_keywords.add(current_keyword)
                        continue

                    # [Step 2] 列表级筛选 (去重 + 标题排除 + 黑名单)
                    # 在"抓取下来的那一刻"立即筛选，然后逐个AI评分
                    new_valid_jobs = []
                    for job in jobs_on_page:
                        job_url = job.get('link') or job.get('job_url', '')
                        job_id = self._extract_job_id(job_url)
                        job_title = job.get('title', 'N/A')
                        job_company = job.get('company', 'Unknown')

                        # 历史去重（同时检查 job_id 和 标题+公司）
                        if self._is_job_processed(job_id, title=job_title, company=job_company):
                            continue

                        # 标题排除（在抓取后立即筛选）
                        if any(ex in job_title.lower() for ex in normalized_title_exclusions):
                            logger.debug(f"   ⏭️ 标题排除: {job_title}")
                            continue

                        # 黑名单检查（在抓取后立即筛选）
                        if any(b in job_company.lower() for b in normalized_block_list):
                            logger.debug(f"   🗑️ 黑名单公司: {job_company}")
                            continue

                        new_valid_jobs.append(job)

                    # [Step 3] 实时低产出判定
                    count = len(new_valid_jobs)
                    if count < 2:
                        low_yield_counters[current_keyword] += 1
                        logger.warning(f"📉 第 {current_physical_page} 页低产出 ({count} 个). 连续: {low_yield_counters[current_keyword]}/2")
                    else:
                        low_yield_counters[current_keyword] = 0 # 重置
                        logger.info(f"⚡️ 第 {current_physical_page} 页发现 {count} 个新职位")

                    if low_yield_counters[current_keyword] >= 2:
                        logger.warning(f"🛑 关键词 '{current_keyword}' 连续低效，标记枯竭")
                        self.exhausted_keywords.add(current_keyword)
                    
                    # [Step 4] 更新进度 (无论如何都要 +1)
                    self.current_page_map[current_keyword] += 1

                    # [Step 5] 处理本页职位 (核心业务逻辑)
                    if new_valid_jobs:
                        logger.info(f"📦 开始处理本页 {len(new_valid_jobs)} 个职位...")
                        
                        for i, job in enumerate(new_valid_jobs, 1):
                            if self.success_count >= self.limit: break
                            
                            processed_any_job_in_this_round = True
                            
                            # --- 提取信息 ---
                            job_url = job.get('link') or job.get('job_url', '')
                            job_id = self._extract_job_id(job_url)
                            job_title = job.get('title', 'N/A')
                            job_company = job.get('company', 'Unknown')

                            # 再次防御性去重（同时检查 job_id 和 标题+公司）
                            if self._is_job_processed(job_id, title=job_title, company=job_company): continue
                            self._processed_job_ids.add(job_id)
                            self._processed_job_keys.add(self._generate_job_key(job_title, job_company))

                            # 构造对象
                            job_info = ApplyJobInfo(
                                job_id=job_id,
                                title=job_title,
                                company=job_company,
                                location=job.get('location', 'N/A'),
                                job_url=job_url,
                                jd_text=job.get('jd_content', '') # 注意：列表页可能没有JD，如果这里为空，需确保后续会抓取
                            )

                            # --- 黑名单检查 ---
                            if any(b in job_company.lower() for b in normalized_block_list):
                                logger.info(f"   🗑️ 跳过黑名单: {job_company}")
                                self._mark_job_processed(job_id, job_url, job_title, job_company, "skipped_blocked", "Blocked Company")
                                continue

                            # --- AI 评分逻辑 ---
                            if self.llm_engine and candidate_profile:
                                try:
                                    logger.info(f"   🤖 AI 评分中: {job_title}")
                                    # (此处省略 status_manager update 以节省篇幅，可按需添加)
                                    
                                    # 如果列表页没有 JD 文本，可能需要补充抓取
                                    if not job_info.jd_text and hasattr(self, '_fetch_job_details'):
                                        job_info.jd_text = self._fetch_job_details(job_url)

                                    match_res = self.llm_engine.check_match_score(
                                        resume_text=candidate_profile.get("resume_text", ""),
                                        jd_text=job_info.jd_text,
                                        resume_language=candidate_profile.get("resume_language", "en"),
                                        resume_en_summary=candidate_profile.get("resume_en_summary", "")
                                    )

                                    # 🔴 修复：验证 LLM 返回结果，避免 score 变成 0
                                    if match_res is None or not isinstance(match_res, dict):
                                        logger.warning(f"   ⚠️ AI 评分返回无效结果，跳过此职位")
                                        self._mark_job_processed(job_id, job_url, job_title, job_company, "error", "AI评分失败")
                                        continue

                                    score = match_res.get("score")

                                    # 🔴 修复：如果 score 为 None 或无效，跳过而不是显示 0%
                                    if score is None or not isinstance(score, (int, float)):
                                        logger.warning(f"   ⚠️ AI 评分返回无效分数: {score}，跳过此职位")
                                        self._mark_job_processed(job_id, job_url, job_title, job_company, "error", "AI评分无效")
                                        continue

                                    score = int(score)  # 确保是整数
                                    reason = match_res.get("reasoning", match_res.get("match_analysis", ""))
                                    
                                    # 阈值判定 (假设默认 70)
                                    threshold = getattr(self, 'ai_score_threshold', 25)
                                    
                                    if score < threshold:
                                        logger.warning(f"   ❌ 分数过低 ({score}/{threshold})，跳过")
                                        self._mark_job_processed(job_id, job_url, job_title, job_company, "skipped_low_score", reason)
                                        continue
                                    
                                    job_info.score = score
                                    
                                except Exception as e:
                                    logger.error(f"   ⚠️ AI 评分出错: {e}")
                                    continue

                            # --- 执行投递 ---
                            try:
                                logger.info(f"   🚀 正在投递: {job_title}")
                                result = self.apply_to_job(job_info, candidate_profile)
                                results.append(result)

                                if result.status == ApplyStatus.SUCCESS:
                                    self.success_count += 1
                                    logger.info(f"   ✅ 投递成功！({self.success_count}/{self.limit})")
                                    self._mark_job_processed(job_id, job_url, job_title, job_company, "success", "Applied")
                                    
                                    # 投递成功后的额外延迟
                                    time.sleep(delay_between_jobs)
                                else:
                                    logger.info(f"   ✗ 投递未完成: {result.message}")
                                    # 标记为 failed 或 skipped
                                    status_code = "failed" if result.status == ApplyStatus.FAILED else "skipped"
                                    self._mark_job_processed(job_id, job_url, job_title, job_company, status_code, result.message)

                            except Exception as e:
                                logger.error(f"   ❌ 投递过程异常: {e}")
                                self._mark_job_processed(job_id, job_url, job_title, job_company, "failed_exception", str(e))

                except Exception as e:
                    logger.error(f"❌ 页面处理异常: {e}")
                    # 出错也要往前走，防止卡死
                    self.current_page_map[current_keyword] += 1
                
                if self.success_count >= self.limit:
                    break

            # 轮询间隙
            if self.success_count < self.limit and not processed_any_job_in_this_round:
                logger.info("⏳ 本轮无有效产出，休息 3 秒...")
                time.sleep(3)

        return results


