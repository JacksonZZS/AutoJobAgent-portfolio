# core/apply/auth_mixin.py
"""Authentication mixin for JobsDBApplyBot."""

import time
import logging

from core.interaction_manager import get_interaction_manager

logger = logging.getLogger(__name__)


class AuthMixin:
    """Handles login status checking and authentication flow."""

    def _is_logged_in(self) -> bool:
        """
        检查是否已登录（支持 Google SSO 等多种登录方式）
        """
        try:
            self._page.goto("https://hk.jobsdb.com/", wait_until="networkidle", timeout=30000)
            self._page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            logged_in_selectors = [
                '[data-automation="account-menu"]',
                'button[data-automation="user-account-menu"]',
                '[data-automation="user-menu"]',
                'a[href*="/profile"]',
                'a[href*="/account"]',
                'a[href*="logout"]',
                '[class*="user-menu"]',
                '[class*="account-menu"]',
            ]

            for selector in logged_in_selectors:
                element = self._page.query_selector(selector)
                if element:
                    logger.info(f"[User: {self.username}] 自动登录成功 (found element: {selector})")
                    return True

            signin_selectors = [
                'a[data-automation="login"]',
                'a[data-automation="signin-button"]',
                'button[data-automation="signin-button"]',
                'a[href*="/login"]',
                'a:has-text("Sign In")',
                'a:has-text("Log In")',
            ]

            signin_found = False
            for selector in signin_selectors:
                try:
                    element = self._page.query_selector(selector)
                    if element:
                        signin_found = True
                        break
                except:
                    continue

            if not signin_found:
                body = self._page.query_selector('body')
                if body:
                    logger.info("Assuming logged in (signin button not found)")
                    return True
            else:
                logger.info("Not logged in (found signin button)")
                return False

            return False

        except Exception as e:
            logger.warning(f"登录状态检测出错: {e}")
            return False

    def ensure_logged_in(self) -> bool:
        """
        确保已登录，支持 Cookie 复用和手动登录模式
        """
        logger.info("Checking login status...")

        if self._is_logged_in():
            return True

        if not self.username or not self.password:
            logger.warning("⚠️ 未配置账号密码，进入 [手动登录模式]")

            try:
                self._page.goto("https://hk.jobsdb.com/login", wait_until="domcontentloaded")
            except Exception as e:
                logger.warning(f"Failed to navigate to login page: {e}")

            interaction_mgr = get_interaction_manager()

            if hasattr(self, 'status_manager') and self.status_manager:
                self.status_manager.update(
                    status="waiting_user",
                    message="请在浏览器中手动登录 JobsDB",
                    step="manual_login_waiting"
                )

            print("\n" + "!"*60)
            print("🛑【需要手动登录】")
            print("请在弹出的 Chrome 浏览器中手动输入账号密码并完成登录。")
            print("⚠️ 注意：登录成功跳转回首页后，请在 Web 界面点击「继续」按钮...")
            print("!"*60 + "\n")

            success = interaction_mgr.wait_for_user_action(
                message="请完成 JobsDB 登录后点击继续",
                timeout=600
            )

            if not success:
                logger.error("Manual login timeout or cancelled")
                return False

            logger.info("✅ 用户确认已登录，继续执行任务...")
            return True

        logger.info("Attempting to login...")

        try:
            login_btn = self._page.query_selector(self.selectors["login_button"])
            if login_btn:
                login_btn.click()
                time.sleep(2)

            self._page.wait_for_selector(self.selectors["email_input"], timeout=10000)
            self._page.fill(self.selectors["email_input"], self.username)
            time.sleep(0.5)

            self._page.fill(self.selectors["password_input"], self.password)
            time.sleep(0.5)

            self._page.click(self.selectors["submit_login"])
            time.sleep(3)

            if self._check_captcha():
                self._wait_for_captcha_resolution()

            try:
                self._page.wait_for_selector(
                    self.selectors["logged_in_indicator"],
                    timeout=30000
                )
                logger.info("Login successful!")
                return True
            except:
                logger.error("Login failed - could not verify login status")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
