"""
浏览器并发控制模块 - SaaS 级别的资源管理
全局限制最多 2 个并发浏览器实例，支持多用户隔离
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from pathlib import Path
from playwright.async_api import BrowserContext, async_playwright

from core.user_agents import get_random_user_agent, get_random_viewport

logger = logging.getLogger(__name__)

# 🔴 全局资源控制：最大并发浏览器实例 = 2
_BROWSER_SEMAPHORE = asyncio.Semaphore(2)
_CURRENT_BROWSER_COUNT = 0
_BROWSER_COUNT_LOCK = asyncio.Lock()


async def get_current_browser_count() -> int:
    """获取当前活跃的浏览器实例数量"""
    async with _BROWSER_COUNT_LOCK:
        return _CURRENT_BROWSER_COUNT


async def _increment_browser_count():
    """增加浏览器计数"""
    global _CURRENT_BROWSER_COUNT
    async with _BROWSER_COUNT_LOCK:
        _CURRENT_BROWSER_COUNT += 1
        logger.info(f"Browser instance started. Current count: {_CURRENT_BROWSER_COUNT}/2")


async def _decrement_browser_count():
    """减少浏览器计数"""
    global _CURRENT_BROWSER_COUNT
    async with _BROWSER_COUNT_LOCK:
        _CURRENT_BROWSER_COUNT = max(0, _CURRENT_BROWSER_COUNT - 1)
        logger.info(f"Browser instance closed. Current count: {_CURRENT_BROWSER_COUNT}/2")


@asynccontextmanager
async def acquire_browser_context(
    user_id: str,
    headless: bool = True,
    user_data_root: Optional[Path] = None,
    use_master_profile: bool = False,
    **launch_kwargs
) -> AsyncIterator[BrowserContext]:
    """
    统一入口：限制浏览器实例并发，并负责自动关闭 context

    Args:
        user_id: 用户 ID，用于数据隔离
        headless: 是否无头模式（默认 True，生产环境强制 True）
        user_data_root: 用户数据根目录（默认为 data/browser_profiles）
        use_master_profile: 是否使用 Master Profile（用于共享搜索能力，绕过 Cloudflare）
        **launch_kwargs: 其他启动参数

    Yields:
        BrowserContext: Playwright 浏览器上下文

    Usage:
        # 用户专属 Profile（用于投递）
        async with acquire_browser_context(user_id="user123") as ctx:
            page = await ctx.new_page()
            await page.goto("https://example.com")

        # Master Profile（用于搜索/抓取）
        async with acquire_browser_context(user_id="user123", use_master_profile=True) as ctx:
            page = await ctx.new_page()
            await page.goto("https://jobsdb.com")
    """
    # 等待获取浏览器配额（如果超过 2 个并发，会在此处排队）
    logger.info(f"[User: {user_id}] Requesting browser context (waiting for slot)...")
    await _BROWSER_SEMAPHORE.acquire()

    ctx = None
    playwright = None

    try:
        await _increment_browser_count()

        # 🔴 Master Profile 策略：搜索/抓取任务使用共享配置
        if use_master_profile:
            if user_data_root is None:
                user_data_root = Path(__file__).parent.parent / "data" / "browser_profiles"

            user_data_dir = user_data_root / "master"
            user_data_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"[BrowserPool] 🛡️ Using MASTER profile for shared search capability")
            logger.info(f"[BrowserPool] Master profile path: {user_data_dir}")
        else:
            # 🔴 用户专属 Profile：投递任务使用独立配置
            user_id = str(user_id)

            from core.user_identity import get_username
            username = get_username(user_id)

            if not username or username == user_id:
                raise RuntimeError(f"FATAL: Cannot resolve username for user_id={user_id}. Aborting to prevent login state pollution.")

            if user_data_root is None:
                user_data_root = Path(__file__).parent.parent / "data" / "browser_profiles"

            user_data_dir = user_data_root / username
            user_data_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"[BrowserPool] 👤 Using USER profile for user: {username}")
            logger.info(f"[BrowserPool] User profile path: {user_data_dir}")

        # 🔴 清理锁文件：防止 SingletonLock 冲突
        singleton_lock = user_data_dir / "SingletonLock"
        singleton_socket = user_data_dir / "SingletonSocket"

        if singleton_lock.exists():
            singleton_lock.unlink()
        if singleton_socket.exists():
            singleton_socket.unlink()

        logger.info(f"CLEANUP: Removed browser singleton lock")
        logger.info(f"EXECUTION: Hardcoded Headless Mode Active")

        # 启动 Playwright
        playwright = await async_playwright().start()

        # 🔴 构建 args 列表 - 使用 Chrome New Headless 模式
        browser_args = [
            '--headless=new',  # 🔴 新版无头模式，更难被检测
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--remote-debugging-port=0',
            '--disable-gpu',
            '--disable-software-rasterizer',
            '--disable-extensions'
        ]

        browser_args = [arg for arg in browser_args if 'no-headless' not in arg.lower()]

        # 使用随机 User-Agent 和视口
        random_ua = get_random_user_agent()
        random_viewport = get_random_viewport()

        logger.info(f"[BrowserPool] Using random UA: {random_ua[:50]}...")

        # 🔴 使用 launch_persistent_context 实现会话持久化
        ctx = await playwright.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=False,  # 🔴 禁用 Playwright 的旧版无头逻辑，改用 --headless=new
            devtools=False,
            viewport=random_viewport,
            user_agent=random_ua,
            args=browser_args,
            **launch_kwargs
        )

        # 🔴 注入反检测脚本
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        logger.info(f"[User: {user_id}] Browser context acquired successfully")
        yield ctx

    except Exception as e:
        logger.error(f"[User: {user_id}] Failed to launch browser context: {e}", exc_info=True)
        raise

    finally:
        # 确保资源释放
        if ctx is not None:
            try:
                await ctx.close()
                logger.debug(f"[User: {user_id}] Browser context closed")
            except Exception as e:
                logger.warning(f"[User: {user_id}] Failed to close context: {e}")

        if playwright is not None:
            try:
                await playwright.stop()
                logger.debug(f"[User: {user_id}] Playwright stopped")
            except Exception as e:
                logger.warning(f"[User: {user_id}] Failed to stop playwright: {e}")

        await _decrement_browser_count()
        _BROWSER_SEMAPHORE.release()
        logger.info(f"[User: {user_id}] Browser slot released")


async def get_browser_pool_status() -> dict:
    """
    获取浏览器池状态（用于监控和诊断）

    Returns:
        {
            "max_instances": 2,
            "current_instances": 1,
            "available_slots": 1,
            "queue_length": 0  # 等待中的请求数量（近似值）
        }
    """
    current_count = await get_current_browser_count()

    # 注意：Semaphore 没有直接获取等待队列长度的 API
    # 这里通过 _value 属性近似估算可用槽位
    available = _BROWSER_SEMAPHORE._value

    return {
        "max_instances": 2,
        "current_instances": current_count,
        "available_slots": max(0, 2 - current_count),
        "queue_length": max(0, current_count - available)  # 近似值
    }


# 🔴 清理 SingletonLock 的辅助函数（向后兼容）
def cleanup_singleton_lock(user_data_dir: Path):
    """
    清理 Chromium 的 SingletonLock 文件
    在启动浏览器前调用，避免遗留的锁文件导致启动失败

    Args:
        user_data_dir: 用户数据目录
    """
    try:
        lock_file = user_data_dir / 'SingletonLock'
        if lock_file.exists():
            try:
                lock_file.unlink()
                logger.info(f"Deleted SingletonLock file: {lock_file}")
            except Exception as e:
                logger.warning(f"Failed to delete SingletonLock: {e}")

        socket_file = user_data_dir / 'SingletonSocket'
        if socket_file.exists():
            try:
                socket_file.unlink()
                logger.info(f"Deleted SingletonSocket file: {socket_file}")
            except Exception as e:
                logger.warning(f"Failed to delete SingletonSocket: {e}")

    except Exception as e:
        logger.warning(f"Error during singleton lock cleanup: {e}")
