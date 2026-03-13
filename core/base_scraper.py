# core/base_scraper.py
"""
抽象基类：多平台职位爬虫和投递机器人
支持 JobsDB, Indeed, LinkedIn 等平台
"""

import os
import re
import logging
import asyncio
import random
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from core.user_agents import get_random_user_agent, get_random_viewport
from core.poison_detector import detect_poison, is_blocked, PoisonPillType

logger = logging.getLogger(__name__)

# 正则表达式：验证 user_id 格式，防止路径遍历攻击
USER_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

def validate_user_id(user_id: str) -> str:
    """
    验证 user_id 格式，防止路径遍历攻击

    Args:
        user_id: 用户 ID

    Returns:
        验证后的 user_id

    Raises:
        ValueError: 如果 user_id 格式无效
    """
    if not user_id:
        raise ValueError("user_id is required")
    if not USER_ID_PATTERN.match(user_id):
        raise ValueError(f"Invalid user_id format: {user_id}. Only alphanumeric, underscore and hyphen allowed.")
    return user_id


def generate_stable_id(prefix: str, value: str) -> str:
    """
    生成稳定的 ID（跨 Python 会话一致）

    Args:
        prefix: ID 前缀
        value: 用于生成 hash 的值

    Returns:
        格式为 "{prefix}_{hash[:12]}" 的稳定 ID
    """
    hash_value = hashlib.md5(value.encode()).hexdigest()[:12]
    return f"{prefix}_{hash_value}"

BASE_DIR = Path(__file__).parent.parent

# 默认浏览器配置（已弃用，使用 get_random_user_agent() 代替）
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'


def get_browser_user_agent() -> str:
    """获取浏览器 User-Agent（随机）"""
    return get_random_user_agent()

# 反检测脚本
ANTI_DETECT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
    });
    window.chrome = { runtime: {} };
"""


class BrowserMixin:
    """
    浏览器操作混入类
    提供通用的浏览器初始化、关闭、工具方法
    """

    async def init_browser(self) -> BrowserContext:
        """初始化浏览器上下文"""
        self._cleanup_locks()

        playwright = await async_playwright().start()

        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
        ]

        if self.headless:
            browser_args.append('--headless=new')

        # 使用随机 User-Agent 和视口
        random_ua = get_random_user_agent()
        random_viewport = get_random_viewport()

        launch_options = {
            "channel": "chrome",
            "headless": False,  # 使用 --headless=new 参数代替
            "args": browser_args,
            "viewport": random_viewport,
            "user_agent": random_ua,
            "ignore_https_errors": True,
        }

        logger.info(f"[BrowserMixin] Using random UA: {random_ua[:50]}...")

        if hasattr(self, 'proxy') and self.proxy:
            launch_options["proxy"] = {"server": self.proxy}

        self.context = await playwright.chromium.launch_persistent_context(
            str(self.profile_dir),
            **launch_options
        )

        # 注入反检测脚本
        await self.context.add_init_script(ANTI_DETECT_SCRIPT)

        # 确保只有一个页面
        while len(self.context.pages) > 1:
            await self.context.pages[-1].close()
        self.page = self.context.pages[0]

        return self.context

    async def close(self):
        """关闭浏览器"""
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                logger.warning(f"Error closing browser context: {e}")
            finally:
                self.context = None
                self.page = None

    def _cleanup_locks(self):
        """清理浏览器锁文件"""
        for lock_file in ["SingletonLock", "SingletonSocket"]:
            lock_path = self.profile_dir / lock_file
            if lock_path.exists():
                try:
                    lock_path.unlink()
                except Exception as e:
                    logger.debug(f"Failed to remove lock file {lock_file}: {e}")

    async def random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """随机延迟，模拟人类行为"""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def safe_click(self, selector: str, timeout: int = 5000) -> bool:
        """安全点击元素"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.click(selector)
            return True
        except Exception as e:
            logger.warning(f"Failed to click {selector}: {e}")
            return False

    async def safe_fill(self, selector: str, value: str, timeout: int = 5000) -> bool:
        """安全填充表单"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.fill(selector, value)
            return True
        except Exception as e:
            logger.warning(f"Failed to fill {selector}: {e}")
            return False


class JobSource(Enum):
    """职位来源平台"""
    JOBSDB = "jobsdb"
    INDEED = "indeed"
    LINKEDIN = "linkedin"


class ApplyStatus(Enum):
    """投递状态枚举"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ALREADY_APPLIED = "already_applied"
    BLOCKED = "blocked"  # 被平台限制


@dataclass
class JobInfo:
    """
    统一职位信息模型
    所有平台的职位数据都转换为这个格式
    """
    source: JobSource
    job_id: str
    title: str
    company: str
    location: str
    job_url: str
    jd_text: str = ""
    score: float = 0.0
    match_analysis: Dict[str, Any] = field(default_factory=dict)
    posted_date: Optional[datetime] = None
    salary_range: Optional[str] = None
    job_type: Optional[str] = None  # full-time, part-time, contract
    is_easy_apply: bool = False  # 是否支持一键投递
    raw_data: Dict[str, Any] = field(default_factory=dict)  # 原始数据

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "source": self.source.value,
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "job_url": self.job_url,
            "jd_text": self.jd_text,
            "score": self.score,
            "match_analysis": self.match_analysis,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "salary_range": self.salary_range,
            "job_type": self.job_type,
            "is_easy_apply": self.is_easy_apply,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JobInfo":
        """从字典创建"""
        source = JobSource(data.get("source", "jobsdb"))
        posted_date = None
        if data.get("posted_date"):
            posted_date = datetime.fromisoformat(data["posted_date"])

        return cls(
            source=source,
            job_id=data["job_id"],
            title=data["title"],
            company=data["company"],
            location=data.get("location", ""),
            job_url=data["job_url"],
            jd_text=data.get("jd_text", ""),
            score=data.get("score", 0.0),
            match_analysis=data.get("match_analysis", {}),
            posted_date=posted_date,
            salary_range=data.get("salary_range"),
            job_type=data.get("job_type"),
            is_easy_apply=data.get("is_easy_apply", False),
        )


@dataclass
class ApplyResult:
    """投递结果"""
    job_info: JobInfo
    status: ApplyStatus
    message: str = ""
    cover_letter_path: Optional[str] = None
    resume_path: Optional[str] = None
    applied_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "source": self.job_info.source.value,
            "job_id": self.job_info.job_id,
            "title": self.job_info.title,
            "company": self.job_info.company,
            "status": self.status.value,
            "message": self.message,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }


class BaseJobScraper(BrowserMixin, ABC):
    """
    职位爬虫抽象基类
    所有平台的爬虫都继承这个类
    """

    # 子类必须设置
    SOURCE: JobSource = None
    BASE_URL: str = ""

    def __init__(
        self,
        user_id: str,
        headless: bool = True,
        proxy: Optional[str] = None,
    ):
        """
        初始化爬虫

        Args:
            user_id: 用户 ID，用于数据隔离
            headless: 是否无头模式
            proxy: 代理服务器地址
        """
        self.user_id = validate_user_id(user_id)
        self.headless = headless
        self.proxy = proxy
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # 浏览器配置目录
        self.profile_dir = BASE_DIR / "data" / "browser_profiles" / self.SOURCE.value / user_id
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def search_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        page: int = 1,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[JobInfo]:
        """
        搜索职位

        Args:
            keyword: 搜索关键词
            location: 工作地点
            page: 页码
            filters: 过滤条件 (job_type, salary_range, posted_date 等)

        Returns:
            职位列表
        """
        pass

    @abstractmethod
    async def get_job_details(self, job_url: str) -> str:
        """
        获取职位详情 (JD)

        Args:
            job_url: 职位详情页 URL

        Returns:
            职位描述文本
        """
        pass


class BaseApplyBot(BrowserMixin, ABC):
    """
    投递机器人抽象基类
    所有平台的投递逻辑都继承这个类
    """

    # 子类必须设置
    SOURCE: JobSource = None

    # 默认配置
    DEFAULT_SELECTORS: Dict[str, str] = {}

    def __init__(
        self,
        user_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = False,
        llm_engine = None,
        cv_path: Optional[str] = None,
        status_manager = None,
    ):
        """
        初始化投递机器人

        Args:
            user_id: 用户 ID
            username: 平台账号
            password: 平台密码
            headless: 是否无头模式
            llm_engine: LLM 引擎实例
            cv_path: 简历 PDF 路径
            status_manager: 状态管理器
        """
        self.user_id = validate_user_id(user_id)
        # 凭证标记为私有属性
        self._username = username
        self._password = password
        self.headless = headless
        self.llm_engine = llm_engine
        self.cv_path = cv_path
        self.status_manager = status_manager

        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_logged_in: bool = False

        # 浏览器配置目录
        self.profile_dir = BASE_DIR / "data" / "browser_profiles" / self.SOURCE.value / user_id
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        # 选择器配置
        self.selectors = self.DEFAULT_SELECTORS.copy()

    @abstractmethod
    async def login(self) -> bool:
        """
        登录平台

        Returns:
            是否登录成功
        """
        pass

    @abstractmethod
    async def apply(
        self,
        job: JobInfo,
        resume_path: str,
        cover_letter_path: Optional[str] = None,
    ) -> ApplyResult:
        """
        投递职位

        Args:
            job: 职位信息
            resume_path: 简历文件路径
            cover_letter_path: 求职信文件路径

        Returns:
            投递结果
        """
        pass

    @abstractmethod
    async def check_already_applied(self, job: JobInfo) -> bool:
        """
        检查是否已投递

        Args:
            job: 职位信息

        Returns:
            是否已投递
        """
        pass
