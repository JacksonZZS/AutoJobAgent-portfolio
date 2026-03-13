# core/stealth_browser.py
"""
终极反爬浏览器 - 绕过 Cloudflare、Indeed、LinkedIn 等
综合多种反检测技术
"""

import os
import random
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)

# ============================================================
# 1. 随机 User-Agent 池（真实浏览器指纹）
# ============================================================
USER_AGENTS = [
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# ============================================================
# 2. 随机视口尺寸（真实屏幕分辨率）
# ============================================================
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 2560, "height": 1440},
    {"width": 1680, "height": 1050},
]

# ============================================================
# 3. 终极反检测脚本
# ============================================================
STEALTH_SCRIPT = """
// ========== 核心反检测 ==========

// 1. 隐藏 webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true
});

// 2. 删除 Playwright/Puppeteer 痕迹
delete window.__playwright;
delete window.__puppeteer;
delete window.__selenium;
delete window.__nightmare;

// 3. 模拟真实 Chrome
window.chrome = {
    runtime: {
        id: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
        connect: function() {},
        sendMessage: function() {},
        onMessage: { addListener: function() {} }
    },
    loadTimes: function() {
        return {
            commitLoadTime: Date.now() / 1000,
            connectionInfo: 'http/1.1',
            finishDocumentLoadTime: Date.now() / 1000 + 0.1,
            finishLoadTime: Date.now() / 1000 + 0.2,
            firstPaintAfterLoadTime: 0,
            firstPaintTime: Date.now() / 1000 + 0.05,
            navigationType: 'Other',
            npnNegotiatedProtocol: 'http/1.1',
            requestTime: Date.now() / 1000 - 0.5,
            startLoadTime: Date.now() / 1000 - 0.3,
            wasAlternateProtocolAvailable: false,
            wasFetchedViaSpdy: false,
            wasNpnNegotiated: false
        };
    },
    csi: function() {
        return {
            startE: Date.now(),
            onloadT: Date.now() + 100,
            pageT: 500,
            tran: 15
        };
    },
    app: {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
    }
};

// 4. 模拟真实插件
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
        ];
        plugins.item = idx => plugins[idx];
        plugins.namedItem = name => plugins.find(p => p.name === name);
        plugins.refresh = () => {};
        return plugins;
    },
    configurable: true
});

// 5. 模拟 mimeTypes
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => {
        const mimes = [
            { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
            { type: 'application/x-nacl', suffixes: '', description: 'Native Client Executable' }
        ];
        mimes.item = idx => mimes[idx];
        mimes.namedItem = type => mimes.find(m => m.type === type);
        return mimes;
    },
    configurable: true
});

// 6. 语言设置
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en', 'zh-CN', 'zh-TW'],
    configurable: true
});

Object.defineProperty(navigator, 'language', {
    get: () => 'en-US',
    configurable: true
});

// 7. 硬件信息
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8,
    configurable: true
});

Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8,
    configurable: true
});

Object.defineProperty(navigator, 'maxTouchPoints', {
    get: () => 0,
    configurable: true
});

// 8. 网络信息
Object.defineProperty(navigator, 'connection', {
    get: () => ({
        effectiveType: '4g',
        rtt: 50,
        downlink: 10,
        saveData: false,
        type: 'wifi'
    }),
    configurable: true
});

// 9. 权限 API
const originalQuery = window.navigator.permissions?.query;
if (originalQuery) {
    window.navigator.permissions.query = (parameters) => {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: 'prompt', onchange: null });
        }
        return originalQuery.call(navigator.permissions, parameters);
    };
}

// 10. WebGL 指纹混淆
const getParameterProxy = new Proxy(WebGLRenderingContext.prototype.getParameter, {
    apply: function(target, thisArg, args) {
        if (args[0] === 37445) return 'Intel Inc.';
        if (args[0] === 37446) return 'Intel Iris Pro OpenGL Engine';
        if (args[0] === 7937) return 'WebKit WebGL';
        if (args[0] === 7938) return 'WebGL 1.0 (OpenGL ES 2.0 Chromium)';
        return Reflect.apply(target, thisArg, args);
    }
});
WebGLRenderingContext.prototype.getParameter = getParameterProxy;

// WebGL2 同样处理
if (typeof WebGL2RenderingContext !== 'undefined') {
    const getParameter2Proxy = new Proxy(WebGL2RenderingContext.prototype.getParameter, {
        apply: function(target, thisArg, args) {
            if (args[0] === 37445) return 'Intel Inc.';
            if (args[0] === 37446) return 'Intel Iris Pro OpenGL Engine';
            return Reflect.apply(target, thisArg, args);
        }
    });
    WebGL2RenderingContext.prototype.getParameter = getParameter2Proxy;
}

// 11. Canvas 指纹轻微噪声
const originalGetContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(type, attributes) {
    const context = originalGetContext.call(this, type, attributes);
    if (type === '2d' && context) {
        const originalFillText = context.fillText.bind(context);
        context.fillText = function(text, x, y, maxWidth) {
            // 添加微小偏移
            const offsetX = (Math.random() - 0.5) * 0.1;
            const offsetY = (Math.random() - 0.5) * 0.1;
            return originalFillText(text, x + offsetX, y + offsetY, maxWidth);
        };
    }
    return context;
};

// 12. 隐藏自动化标志
Object.defineProperty(document, 'hidden', {
    get: () => false,
    configurable: true
});

Object.defineProperty(document, 'visibilityState', {
    get: () => 'visible',
    configurable: true
});

// 13. 修复 iframe contentWindow
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get: function() {
        return window;
    }
});

// 14. 时区一致性
Date.prototype.getTimezoneOffset = function() {
    return -480; // Asia/Hong_Kong
};

// 15. 电池 API（某些网站用于指纹）
navigator.getBattery = () => Promise.resolve({
    charging: true,
    chargingTime: 0,
    dischargingTime: Infinity,
    level: 1.0,
    addEventListener: () => {},
    removeEventListener: () => {}
});

console.log('[Stealth] Anti-detection initialized');
"""


class StealthBrowser:
    """
    终极隐身浏览器
    结合多种反检测技术绕过 Cloudflare、LinkedIn 等
    """

    def __init__(
        self,
        headless: bool = False,
        proxy: Optional[str] = None,
        profile_dir: Optional[Path] = None,
        slow_mo: int = 0,
        country: str = "hk",  # 新增：地区参数
    ):
        self.headless = headless
        self.proxy = proxy
        self.profile_dir = profile_dir or Path.home() / ".stealth_browser"
        self.slow_mo = slow_mo
        self.country = country

        self.playwright = None
        self.browser = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # 只使用 Chrome User-Agent（避免 Sec-Ch-Ua 不匹配）
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.viewport = random.choice(VIEWPORTS)

        # 根据地区设置时区
        self.timezone_map = {
            "hk": {"timezone_id": "Asia/Hong_Kong", "lat": 22.3193, "lng": 114.1694},
            "us": {"timezone_id": "America/New_York", "lat": 40.7128, "lng": -74.0060},
            "uk": {"timezone_id": "Europe/London", "lat": 51.5074, "lng": -0.1278},
            "sg": {"timezone_id": "Asia/Singapore", "lat": 1.3521, "lng": 103.8198},
            "ca": {"timezone_id": "America/Toronto", "lat": 43.6532, "lng": -79.3832},
            "au": {"timezone_id": "Australia/Sydney", "lat": -33.8688, "lng": 151.2093},
        }
        self.tz_info = self.timezone_map.get(country, self.timezone_map["hk"])

    async def start(self) -> Page:
        """启动隐身浏览器"""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self.playwright = await async_playwright().start()

        # 浏览器启动参数
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-site-isolation-trials',
            '--disable-web-security',
            '--disable-features=BlockInsecurePrivateNetworkRequests',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--hide-scrollbars',
            '--mute-audio',
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-breakpad',
            '--disable-component-extensions-with-background-pages',
            '--disable-component-update',
            '--disable-default-apps',
            '--disable-extensions',
            '--disable-features=TranslateUI',
            '--disable-hang-monitor',
            '--disable-ipc-flooding-protection',
            '--disable-popup-blocking',
            '--disable-prompt-on-repost',
            '--disable-renderer-backgrounding',
            '--disable-sync',
            '--force-color-profile=srgb',
            '--metrics-recording-only',
            '--enable-features=NetworkService,NetworkServiceInProcess',
            f'--window-size={self.viewport["width"]},{self.viewport["height"]}',
        ]

        if self.headless:
            args.append('--headless=new')

        # 使用持久化上下文（保留 cookies 和状态）
        launch_options = {
            "channel": "chrome",
            "headless": False,  # 用 args 控制
            "args": args,
            "slow_mo": self.slow_mo,
            "ignore_default_args": ["--enable-automation"],
            "chromium_sandbox": False,
        }

        if self.proxy:
            launch_options["proxy"] = {"server": self.proxy}

        # 上下文选项
        context_options = {
            "viewport": self.viewport,
            "user_agent": self.user_agent,
            "locale": "en-US",
            "timezone_id": self.tz_info["timezone_id"],
            "geolocation": {"latitude": self.tz_info["lat"], "longitude": self.tz_info["lng"]},
            "permissions": ["geolocation"],
            "color_scheme": "light",
            "device_scale_factor": 1,
            "is_mobile": False,
            "has_touch": False,
            "ignore_https_errors": True,
            "java_script_enabled": True,
            "bypass_csp": True,
            "extra_http_headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        }

        self.context = await self.playwright.chromium.launch_persistent_context(
            str(self.profile_dir),
            **launch_options,
            **context_options,
        )

        # 注入反检测脚本
        await self.context.add_init_script(STEALTH_SCRIPT)

        # 获取或创建页面
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        # 再次注入到当前页面
        await self.page.add_init_script(STEALTH_SCRIPT)

        logger.info(f"[StealthBrowser] Started with UA: {self.user_agent[:50]}...")
        return self.page

    async def goto(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 30000,
        human_delay: bool = True,
    ) -> bool:
        """
        访问页面，带智能等待和人类行为模拟
        """
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=timeout)

            if human_delay:
                # 模拟人类阅读时间
                await asyncio.sleep(random.uniform(1.5, 3.0))

                # 随机滚动
                await self._human_scroll()

            return True
        except Exception as e:
            logger.error(f"[StealthBrowser] Failed to goto {url}: {e}")
            return False

    async def _human_scroll(self):
        """模拟人类滚动行为"""
        try:
            # 随机滚动几次
            for _ in range(random.randint(1, 3)):
                scroll_y = random.randint(100, 500)
                await self.page.mouse.wheel(0, scroll_y)
                await asyncio.sleep(random.uniform(0.3, 0.8))
        except:
            pass

    async def human_move_and_click(self, selector: str, timeout: int = 5000) -> bool:
        """
        模拟人类鼠标移动和点击
        """
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if not element:
                return False

            box = await element.bounding_box()
            if not box:
                return False

            # 计算随机点击位置（不要正中心）
            x = box["x"] + random.uniform(box["width"] * 0.2, box["width"] * 0.8)
            y = box["y"] + random.uniform(box["height"] * 0.2, box["height"] * 0.8)

            # 移动鼠标（模拟贝塞尔曲线）
            await self._bezier_mouse_move(x, y)

            # 随机短暂停顿
            await asyncio.sleep(random.uniform(0.1, 0.3))

            # 点击
            await self.page.mouse.click(x, y)

            return True
        except Exception as e:
            logger.warning(f"[StealthBrowser] Click failed: {e}")
            return False

    async def _bezier_mouse_move(self, target_x: float, target_y: float):
        """贝塞尔曲线鼠标移动（更像人类）"""
        try:
            # 获取当前鼠标位置（假设在视口中心）
            current_x = self.viewport["width"] / 2
            current_y = self.viewport["height"] / 2

            # 分多步移动
            steps = random.randint(10, 20)
            for i in range(steps):
                t = i / steps
                # 简单的曲线插值
                x = current_x + (target_x - current_x) * t + random.uniform(-5, 5)
                y = current_y + (target_y - current_y) * t + random.uniform(-5, 5)
                await self.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.01, 0.03))

            # 最终精确移动到目标
            await self.page.mouse.move(target_x, target_y)
        except:
            pass

    async def human_type(self, selector: str, text: str, timeout: int = 5000) -> bool:
        """
        模拟人类打字（有随机延迟）
        """
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.click(selector)
            await asyncio.sleep(random.uniform(0.1, 0.3))

            for char in text:
                await self.page.keyboard.type(char, delay=random.randint(50, 150))

            return True
        except Exception as e:
            logger.warning(f"[StealthBrowser] Type failed: {e}")
            return False

    async def wait_for_cloudflare(self, max_wait: int = 15) -> bool:
        """
        等待 Cloudflare 验证通过
        """
        for i in range(max_wait):
            title = await self.page.title()
            if "moment" not in title.lower() and "cloudflare" not in title.lower():
                logger.info(f"[StealthBrowser] Cloudflare passed after {i+1}s")
                return True
            await asyncio.sleep(1)

        logger.warning("[StealthBrowser] Cloudflare challenge timeout")
        return False

    async def save_cookies(self, path: str):
        """保存 cookies"""
        cookies = await self.context.cookies()
        import json
        with open(path, "w") as f:
            json.dump(cookies, f, indent=2)
        logger.info(f"[StealthBrowser] Cookies saved to {path}")

    async def load_cookies(self, path: str) -> bool:
        """加载 cookies"""
        import json
        try:
            with open(path, "r") as f:
                cookies = json.load(f)
            await self.context.add_cookies(cookies)
            logger.info(f"[StealthBrowser] Cookies loaded from {path}")
            return True
        except Exception as e:
            logger.warning(f"[StealthBrowser] Failed to load cookies: {e}")
            return False

    async def close(self):
        """关闭浏览器"""
        if self.context:
            try:
                await self.context.close()
            except:
                pass
        if self.playwright:
            try:
                await self.playwright.stop()
            except:
                pass
        logger.info("[StealthBrowser] Closed")


async def test_stealth():
    """测试隐身浏览器"""
    browser = StealthBrowser(headless=False)

    try:
        await browser.start()

        # 测试 Indeed
        print("🚀 Testing Indeed HK...")
        await browser.goto("https://hk.indeed.com/jobs?q=data+analyst&l=Hong+Kong")

        # 等待 Cloudflare
        passed = await browser.wait_for_cloudflare()

        if passed:
            title = await browser.page.title()
            print(f"✅ Page: {title}")

            # 找职位卡片
            cards = await browser.page.query_selector_all('[data-jk]')
            print(f"🔍 Found {len(cards)} jobs")
        else:
            print("❌ Cloudflare blocked")

        await asyncio.sleep(5)

    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_stealth())
