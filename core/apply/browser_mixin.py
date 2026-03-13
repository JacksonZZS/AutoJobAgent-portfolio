# core/apply/browser_mixin.py
"""Browser management mixin for JobsDBApplyBot."""

import time
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class BrowserManagementMixin:
    """Handles browser lifecycle: start, close, singleton lock cleanup."""

    @property
    def page(self):
        """获取当前页面对象"""
        return self._page

    def _is_browser_ready(self) -> bool:
        """
        检查浏览器是否已启动且可用

        Returns:
            True 表示浏览器已启动且页面可用，False 表示需要启动
        """
        try:
            if self._page is None:
                return False
            if self._page.is_closed():
                return False
            return True
        except Exception:
            return False

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()

    def _cleanup_singleton_lock(self, user_data_dir: Path):
        """清理 Chromium 的 SingletonLock 文件"""
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

    def _is_singleton_lock_error(self, error_msg: str) -> bool:
        """检查是否为 SingletonLock 相关错误"""
        error_keywords = [
            'SingletonLock',
            'already in use',
            'profile is in use',
            'cannot create profile',
            'user data directory is already in use'
        ]
        error_msg_lower = str(error_msg).lower()
        return any(keyword.lower() in error_msg_lower for keyword in error_keywords)

    def start(self):
        """启动浏览器（使用持久化上下文，带重试机制）"""
        max_retries = 3
        retry_delay = 2

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Starting browser with persistent context (attempt {attempt}/{max_retries})...")

                user_id = str(self.user_id)

                from core.user_identity import get_username
                username = get_username(user_id)

                if not username or username == user_id:
                    raise RuntimeError(f"FATAL: Cannot resolve username for user_id={user_id}. Aborting to prevent login state pollution.")

                user_data_dir = Path(f"data/browser_profiles/{username}")
                user_data_dir.mkdir(parents=True, exist_ok=True)

                singleton_lock = user_data_dir / "SingletonLock"
                singleton_socket = user_data_dir / "SingletonSocket"

                if singleton_lock.exists():
                    singleton_lock.unlink()
                if singleton_socket.exists():
                    singleton_socket.unlink()

                logger.info(f"CLEANUP: Removed browser singleton lock")
                logger.info(f"EXECUTION: Chrome New Headless Mode Active")
                logger.info(f"[User: {username}] Using persistent browser profile: {user_data_dir}")

                if self._playwright is None:
                    self._playwright = sync_playwright().start()

                self._context = self._playwright.chromium.launch_persistent_context(
                    str(user_data_dir),
                    headless=False,
                    devtools=False,
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--remote-debugging-port=0',
                        '--disable-gpu',
                        '--disable-software-rasterizer',
                        '--disable-extensions',
                        '--start-maximized'
                    ]
                )

                self._context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)

                if len(self._context.pages) > 0:
                    self._page = self._context.pages[0]
                else:
                    self._page = self._context.new_page()

                logger.info("✅ Browser started with persistent session (login state will be remembered)")
                return

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Browser start failed (attempt {attempt}/{max_retries}): {error_msg}")

                if self._is_singleton_lock_error(error_msg):
                    if attempt < max_retries:
                        logger.warning(f"Detected SingletonLock error, waiting {retry_delay}s before retry...")
                        try:
                            self.close()
                        except:
                            pass
                        time.sleep(retry_delay)
                        continue
                    else:
                        logger.error(f"Max retries ({max_retries}) reached, SingletonLock error persists")
                        raise RuntimeError(f"Browser start failed: SingletonLock error after {max_retries} retries") from e
                else:
                    logger.error("Non-SingletonLock error encountered, stopping retries")
                    logger.exception("Failed to start browser, cleaning up resources")
                    self.close()
                    raise

    def close(self):
        """关闭浏览器（持久化上下文会自动保存状态）"""
        logger.info("Closing browser...")
        if self._page and not self._page.is_closed():
            try:
                self._page.close()
            except Exception as e:
                logger.warning(f"Failed to close page: {e}")
        if self._context:
            try:
                self._context.close()
            except Exception as e:
                logger.warning(f"Failed to close context: {e}")
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.warning(f"Failed to stop playwright: {e}")
        logger.info("✅ Browser closed (session persisted)")
