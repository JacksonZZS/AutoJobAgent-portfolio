"""
毒丸检测器
检测招聘网站的反爬/风控/验证码等
参考 web-scraping skill 的 Poison Pill Detection
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class PoisonPillType(Enum):
    """毒丸类型"""
    NONE = 'none'
    CAPTCHA = 'captcha'
    LOGIN_REQUIRED = 'login_required'
    RATE_LIMIT = 'rate_limit'
    CLOUDFLARE = 'cloudflare'
    ACCOUNT_BLOCKED = 'account_blocked'
    IP_BLOCKED = 'ip_blocked'
    REGION_BLOCKED = 'region_blocked'


@dataclass
class PoisonPillResult:
    """检测结果"""
    detected: bool
    type: PoisonPillType
    confidence: float
    message: str


# Indeed 专用检测模式
INDEED_PATTERNS = {
    PoisonPillType.CAPTCHA: [
        'verify you are human',
        'captcha',
        'robot verification',
        'prove you\'re not a robot',
        'security check',
        'unusual traffic',
    ],
    PoisonPillType.LOGIN_REQUIRED: [
        'sign in',
        'log in to continue',
        'create an account',
        'sign in to apply',
    ],
    PoisonPillType.RATE_LIMIT: [
        'too many requests',
        'rate limit',
        'slow down',
        'try again later',
    ],
    PoisonPillType.CLOUDFLARE: [
        'checking your browser',
        'cloudflare',
        'ddos protection',
        'please wait',
        'ray id',
    ],
    PoisonPillType.ACCOUNT_BLOCKED: [
        'account suspended',
        'account blocked',
        'access denied',
        'your account has been',
    ],
}

# LinkedIn 专用检测模式
LINKEDIN_PATTERNS = {
    PoisonPillType.CAPTCHA: [
        'security verification',
        'let\'s do a quick security check',
        'verify your identity',
        'captcha',
    ],
    PoisonPillType.LOGIN_REQUIRED: [
        'sign in',
        'join now',
        'log in or sign up',
        'see who you know',
    ],
    PoisonPillType.RATE_LIMIT: [
        'you\'ve reached the limit',
        'too many requests',
        'please try again',
    ],
    PoisonPillType.ACCOUNT_BLOCKED: [
        'account restricted',
        'your account has been restricted',
        'temporarily restricted',
    ],
    PoisonPillType.REGION_BLOCKED: [
        'not available in your location',
        'region not supported',
    ],
}

# JobsDB 专用检测模式
JOBSDB_PATTERNS = {
    PoisonPillType.CAPTCHA: [
        '验证码',
        'captcha',
        'verify',
    ],
    PoisonPillType.LOGIN_REQUIRED: [
        '请登录',
        'sign in',
        'log in',
    ],
    PoisonPillType.RATE_LIMIT: [
        '请求过于频繁',
        'too many requests',
    ],
    PoisonPillType.CLOUDFLARE: [
        'checking your browser',
        'cloudflare',
    ],
}

# CSS 选择器检测
POISON_SELECTORS = {
    PoisonPillType.CAPTCHA: [
        '[class*="captcha"]',
        '[class*="recaptcha"]',
        '#captcha',
        'iframe[src*="captcha"]',
        'iframe[src*="recaptcha"]',
        '[class*="challenge"]',
    ],
    PoisonPillType.CLOUDFLARE: [
        '#cf-wrapper',
        '.cf-browser-verification',
        '[class*="cloudflare"]',
    ],
    PoisonPillType.LOGIN_REQUIRED: [
        '[class*="login-modal"]',
        '[class*="signin-modal"]',
        '[class*="auth-wall"]',
    ],
}


class PoisonPillDetector:
    """毒丸检测器"""

    def __init__(self, platform: str = 'indeed'):
        """
        初始化检测器

        Args:
            platform: 平台名称 (indeed, linkedin, jobsdb)
        """
        self.platform = platform.lower()
        self.patterns = self._get_patterns()

    def _get_patterns(self) -> dict:
        """获取平台专用检测模式"""
        if self.platform == 'linkedin':
            return LINKEDIN_PATTERNS
        elif self.platform == 'jobsdb':
            return JOBSDB_PATTERNS
        else:  # 默认 indeed
            return INDEED_PATTERNS

    async def detect(self, page: Page) -> PoisonPillResult:
        """
        检测页面是否包含毒丸

        Args:
            page: Playwright Page 对象

        Returns:
            PoisonPillResult: 检测结果
        """
        try:
            # 获取页面文本
            page_text = await page.evaluate('() => document.body?.innerText || ""')
            page_text_lower = page_text.lower()

            # 1. 检查 CSS 选择器
            for pill_type, selectors in POISON_SELECTORS.items():
                for selector in selectors:
                    try:
                        is_visible = await page.locator(selector).first.is_visible(timeout=1000)
                        if is_visible:
                            logger.warning(f"[PoisonDetector] Detected {pill_type.value} via selector: {selector}")
                            return PoisonPillResult(
                                detected=True,
                                type=pill_type,
                                confidence=0.9,
                                message=f"Detected element: {selector}"
                            )
                    except Exception:
                        pass

            # 2. 检查页面文本关键词
            for pill_type, patterns in self.patterns.items():
                for pattern in patterns:
                    if pattern.lower() in page_text_lower:
                        logger.warning(f"[PoisonDetector] Detected {pill_type.value} via pattern: {pattern}")
                        return PoisonPillResult(
                            detected=True,
                            type=pill_type,
                            confidence=0.7,
                            message=f"Detected pattern: {pattern}"
                        )

            # 3. 检查页面内容异常
            if len(page_text) < 100:
                logger.warning("[PoisonDetector] Page content suspiciously short")
                return PoisonPillResult(
                    detected=True,
                    type=PoisonPillType.CLOUDFLARE,
                    confidence=0.5,
                    message="Page content too short, might be blocked"
                )

            # 4. 检查 HTTP 状态（通过 URL 判断）
            current_url = page.url.lower()
            if 'captcha' in current_url or 'challenge' in current_url:
                return PoisonPillResult(
                    detected=True,
                    type=PoisonPillType.CAPTCHA,
                    confidence=0.9,
                    message=f"Captcha URL detected: {current_url}"
                )

            return PoisonPillResult(
                detected=False,
                type=PoisonPillType.NONE,
                confidence=0,
                message="No poison pill detected"
            )

        except Exception as e:
            logger.error(f"[PoisonDetector] Error during detection: {e}")
            return PoisonPillResult(
                detected=False,
                type=PoisonPillType.NONE,
                confidence=0,
                message=f"Detection error: {e}"
            )

    async def quick_check(self, page: Page) -> bool:
        """
        快速检测（只检查关键选择器）

        Args:
            page: Playwright Page 对象

        Returns:
            bool: 是否检测到毒丸
        """
        critical_selectors = [
            '[class*="captcha"]',
            '[class*="recaptcha"]',
            '#cf-wrapper',
            '[class*="cloudflare"]',
            '[class*="challenge"]',
        ]

        for selector in critical_selectors:
            try:
                is_visible = await page.locator(selector).first.is_visible(timeout=500)
                if is_visible:
                    return True
            except Exception:
                pass

        return False


# 便捷函数
async def detect_poison(page: Page, platform: str = 'indeed') -> PoisonPillResult:
    """
    便捷函数：检测页面毒丸

    Args:
        page: Playwright Page 对象
        platform: 平台名称

    Returns:
        PoisonPillResult: 检测结果
    """
    detector = PoisonPillDetector(platform)
    return await detector.detect(page)


async def is_blocked(page: Page, platform: str = 'indeed') -> bool:
    """
    便捷函数：快速检测是否被封锁

    Args:
        page: Playwright Page 对象
        platform: 平台名称

    Returns:
        bool: 是否被封锁
    """
    detector = PoisonPillDetector(platform)
    return await detector.quick_check(page)
