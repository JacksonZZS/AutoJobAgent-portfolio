# core/ultimate_stealth.py
"""
终极反爬浏览器 v2.0 - 自研反检测框架
绕过 Cloudflare、Indeed、LinkedIn 等 2025 最新反爬

核心改进：
1. CDP 检测绕过
2. Runtime.enable 隐藏
3. 更完整的指纹伪装
4. Headless 特征消除
5. 人类行为深度模拟
"""

import os
import random
import asyncio
import logging
import json
import math
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)

# ============================================================
# 1. 真实浏览器指纹数据（从真实浏览器采集）
# ============================================================
REAL_FINGERPRINTS = [
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "platform": "MacIntel",
        "vendor": "Google Inc.",
        "renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)",
        "webgl_vendor": "Google Inc. (Apple)",
        "screen": {"width": 1920, "height": 1080, "depth": 24, "pixelRatio": 2},
        "timezone": "Asia/Hong_Kong",
        "language": "en-US",
        "languages": ["en-US", "en", "zh-CN", "zh-TW"],
        "hardware_concurrency": 10,
        "device_memory": 8,
        "max_touch_points": 0,
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "platform": "Win32",
        "vendor": "Google Inc.",
        "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "screen": {"width": 2560, "height": 1440, "depth": 24, "pixelRatio": 1},
        "timezone": "America/New_York",
        "language": "en-US",
        "languages": ["en-US", "en"],
        "hardware_concurrency": 16,
        "device_memory": 32,
        "max_touch_points": 0,
    },
]


def get_stealth_script(fingerprint: Dict) -> str:
    """生成完整的反检测脚本"""
    return f"""
// ========== Ultimate Stealth Script v2.0 ==========
// 在页面加载前注入，修改所有检测点

(() => {{
    'use strict';

    const fp = {json.dumps(fingerprint)};

    // ========== 1. 核心: 修复 webdriver 检测 ==========
    // 不只是设置为 undefined，而是完全删除 getter
    const originalDescriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
    Object.defineProperty(Navigator.prototype, 'webdriver', {{
        get: () => undefined,
        configurable: true,
        enumerable: true
    }});

    // 防止通过 getOwnPropertyDescriptor 检测
    const originalGetOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;
    Object.getOwnPropertyDescriptor = function(obj, prop) {{
        if (obj === Navigator.prototype && prop === 'webdriver') {{
            return undefined;
        }}
        return originalGetOwnPropertyDescriptor.apply(this, arguments);
    }};

    // ========== 2. CDP 检测绕过 ==========
    // 隐藏 Runtime.enable 等 CDP 特征

    // 2.1 删除 cdc_ 变量（ChromeDriver 特征）
    for (let key in window) {{
        if (key.match(/^(cdc_|__driver_|__webdriver_|__selenium_|__fxdriver_|__wdc_)/)) {{
            try {{ delete window[key]; }} catch(e) {{}}
        }}
    }}

    // 2.2 隐藏 Runtime 注入的变量
    const protectedProps = ['__playwright', '__puppeteer', '__selenium', '__nightmare', '__webdriver'];
    protectedProps.forEach(prop => {{
        try {{ delete window[prop]; }} catch(e) {{}}
        Object.defineProperty(window, prop, {{
            get: () => undefined,
            set: () => {{}},
            configurable: false
        }});
    }});

    // ========== 3. Chrome 对象完整模拟 ==========
    if (!window.chrome) {{
        window.chrome = {{}};
    }}

    window.chrome.runtime = {{
        id: undefined,  // 真实 Chrome 没有扩展时是 undefined
        connect: function() {{ throw new Error("Could not establish connection."); }},
        sendMessage: function() {{ throw new Error("Could not establish connection."); }},
        onConnect: {{ addListener: function() {{}}, removeListener: function() {{}} }},
        onMessage: {{ addListener: function() {{}}, removeListener: function() {{}} }},
        getManifest: function() {{ return undefined; }},
        getURL: function(path) {{ return ''; }},
        getPlatformInfo: function(callback) {{ callback({{ os: 'mac', arch: 'arm' }}); }}
    }};

    window.chrome.app = {{
        isInstalled: false,
        InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }},
        RunningState: {{ CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }},
        getDetails: function() {{ return null; }},
        getIsInstalled: function() {{ return false; }}
    }};

    window.chrome.csi = function() {{
        return {{
            startE: performance.timing.navigationStart,
            onloadT: performance.timing.loadEventEnd,
            pageT: Date.now() - performance.timing.navigationStart,
            tran: 15
        }};
    }};

    window.chrome.loadTimes = function() {{
        const perf = performance.timing;
        return {{
            commitLoadTime: perf.responseStart / 1000,
            connectionInfo: 'h2',
            finishDocumentLoadTime: perf.domContentLoadedEventEnd / 1000,
            finishLoadTime: perf.loadEventEnd / 1000,
            firstPaintAfterLoadTime: 0,
            firstPaintTime: perf.responseEnd / 1000,
            navigationType: 'Other',
            npnNegotiatedProtocol: 'h2',
            requestTime: perf.requestStart / 1000,
            startLoadTime: perf.navigationStart / 1000,
            wasAlternateProtocolAvailable: false,
            wasFetchedViaSpdy: true,
            wasNpnNegotiated: true
        }};
    }};

    // ========== 4. Navigator 属性完整伪装 ==========
    const navigatorProps = {{
        platform: fp.platform,
        vendor: fp.vendor,
        language: fp.language,
        languages: fp.languages,
        hardwareConcurrency: fp.hardware_concurrency,
        deviceMemory: fp.device_memory,
        maxTouchPoints: fp.max_touch_points,
        cookieEnabled: true,
        doNotTrack: null,
        pdfViewerEnabled: true,
        javaEnabled: () => false,
    }};

    for (const [key, value] of Object.entries(navigatorProps)) {{
        try {{
            Object.defineProperty(Navigator.prototype, key, {{
                get: typeof value === 'function' ? value : () => value,
                configurable: true,
                enumerable: true
            }});
        }} catch(e) {{}}
    }}

    // ========== 5. 插件模拟（真实 Chrome 的插件列表）==========
    const mockPlugins = [
        {{ name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format', mimeTypes: ['application/pdf', 'text/pdf'] }},
        {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', mimeTypes: ['application/pdf'] }},
        {{ name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: '', mimeTypes: ['application/pdf'] }},
        {{ name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: '', mimeTypes: ['application/pdf'] }},
        {{ name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: '', mimeTypes: ['application/pdf'] }},
    ];

    const pluginArray = Object.create(PluginArray.prototype);
    mockPlugins.forEach((p, i) => {{
        const plugin = Object.create(Plugin.prototype);
        Object.defineProperties(plugin, {{
            name: {{ value: p.name, enumerable: true }},
            filename: {{ value: p.filename, enumerable: true }},
            description: {{ value: p.description, enumerable: true }},
            length: {{ value: p.mimeTypes.length, enumerable: true }}
        }});
        pluginArray[i] = plugin;
    }});
    Object.defineProperty(pluginArray, 'length', {{ value: mockPlugins.length }});
    pluginArray.item = i => pluginArray[i];
    pluginArray.namedItem = n => [...pluginArray].find(p => p.name === n);
    pluginArray.refresh = () => {{}};

    Object.defineProperty(Navigator.prototype, 'plugins', {{
        get: () => pluginArray,
        configurable: true,
        enumerable: true
    }});

    // ========== 6. WebGL 深度伪装 ==========
    const webglParams = {{
        37445: fp.webgl_vendor,  // UNMASKED_VENDOR_WEBGL
        37446: fp.renderer,      // UNMASKED_RENDERER_WEBGL
        7937: 'WebKit WebGL',    // VENDOR
        7938: 'WebGL 1.0 (OpenGL ES 2.0 Chromium)',  // VERSION
        7936: 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)',  // SHADING_LANGUAGE_VERSION
        3379: 16384,  // MAX_TEXTURE_SIZE
        34076: 16384, // MAX_CUBE_MAP_TEXTURE_SIZE
        34024: 16384, // MAX_RENDERBUFFER_SIZE
        35661: 80,    // MAX_COMBINED_TEXTURE_IMAGE_UNITS
        34930: 16,    // MAX_TEXTURE_IMAGE_UNITS
        36347: 1024,  // MAX_VERTEX_UNIFORM_VECTORS
        36348: 1024,  // MAX_VARYING_VECTORS
        36349: 256,   // MAX_FRAGMENT_UNIFORM_VECTORS
    }};

    const getParameterProxyHandler = {{
        apply(target, thisArg, args) {{
            const param = args[0];
            if (param in webglParams) {{
                return webglParams[param];
            }}
            return Reflect.apply(target, thisArg, args);
        }}
    }};

    WebGLRenderingContext.prototype.getParameter = new Proxy(
        WebGLRenderingContext.prototype.getParameter,
        getParameterProxyHandler
    );

    if (typeof WebGL2RenderingContext !== 'undefined') {{
        WebGL2RenderingContext.prototype.getParameter = new Proxy(
            WebGL2RenderingContext.prototype.getParameter,
            getParameterProxyHandler
        );
    }}

    // ========== 7. Canvas 指纹随机化 ==========
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    const originalToBlob = HTMLCanvasElement.prototype.toBlob;
    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;

    // 为每个 session 生成固定的噪声种子
    const noiseSeed = {random.randint(1, 999999)};

    function addNoise(data) {{
        const noise = (noiseSeed % 10) - 5;
        for (let i = 0; i < data.length; i += 4) {{
            data[i] = Math.max(0, Math.min(255, data[i] + noise));     // R
            data[i+1] = Math.max(0, Math.min(255, data[i+1] - noise)); // G
        }}
        return data;
    }}

    HTMLCanvasElement.prototype.toDataURL = function(...args) {{
        const ctx = this.getContext('2d');
        if (ctx) {{
            try {{
                const imageData = originalGetImageData.call(ctx, 0, 0, this.width, this.height);
                addNoise(imageData.data);
                ctx.putImageData(imageData, 0, 0);
            }} catch(e) {{}}
        }}
        return originalToDataURL.apply(this, args);
    }};

    // ========== 8. Screen 属性 ==========
    const screenProps = {{
        width: fp.screen.width,
        height: fp.screen.height,
        availWidth: fp.screen.width,
        availHeight: fp.screen.height - 25,  // 减去任务栏
        colorDepth: fp.screen.depth,
        pixelDepth: fp.screen.depth,
    }};

    for (const [key, value] of Object.entries(screenProps)) {{
        try {{
            Object.defineProperty(Screen.prototype, key, {{
                get: () => value,
                configurable: true
            }});
        }} catch(e) {{}}
    }}

    Object.defineProperty(window, 'devicePixelRatio', {{
        get: () => fp.screen.pixelRatio,
        configurable: true
    }});

    // ========== 9. 权限 API 伪装 ==========
    if (navigator.permissions) {{
        const originalQuery = navigator.permissions.query;
        navigator.permissions.query = function(parameters) {{
            if (parameters.name === 'notifications') {{
                return Promise.resolve({{ state: 'prompt', onchange: null }});
            }}
            if (parameters.name === 'push') {{
                return Promise.resolve({{ state: 'prompt', onchange: null }});
            }}
            if (parameters.name === 'midi') {{
                return Promise.resolve({{ state: 'granted', onchange: null }});
            }}
            return originalQuery.call(this, parameters).catch(() => ({{ state: 'prompt', onchange: null }}));
        }};
    }}

    // ========== 10. 隐藏自动化特征 ==========
    // document.hidden 始终为 false
    Object.defineProperty(Document.prototype, 'hidden', {{
        get: () => false,
        configurable: true
    }});

    Object.defineProperty(Document.prototype, 'visibilityState', {{
        get: () => 'visible',
        configurable: true
    }});

    // ========== 11. 时区一致性 ==========
    const tzOffset = {{ 'Asia/Hong_Kong': -480, 'America/New_York': 300, 'Europe/London': 0 }}[fp.timezone] || 0;
    Date.prototype.getTimezoneOffset = function() {{ return tzOffset; }};

    // ========== 12. 电池 API ==========
    if (navigator.getBattery) {{
        navigator.getBattery = () => Promise.resolve({{
            charging: true,
            chargingTime: 0,
            dischargingTime: Infinity,
            level: 1.0,
            addEventListener: () => {{}},
            removeEventListener: () => {{}}
        }});
    }}

    // ========== 13. 网络信息 ==========
    Object.defineProperty(Navigator.prototype, 'connection', {{
        get: () => ({{
            effectiveType: '4g',
            rtt: 50 + Math.floor(Math.random() * 50),
            downlink: 10 + Math.random() * 5,
            saveData: false,
            type: 'wifi',
            onchange: null,
            addEventListener: () => {{}},
            removeEventListener: () => {{}}
        }}),
        configurable: true
    }});

    // ========== 14. Headless 检测绕过 ==========
    // 14.1 修复 window.outerWidth/outerHeight
    Object.defineProperty(window, 'outerWidth', {{
        get: () => window.innerWidth + 16,  // 真实浏览器有边框
        configurable: true
    }});
    Object.defineProperty(window, 'outerHeight', {{
        get: () => window.innerHeight + 88,  // 工具栏 + 标签栏
        configurable: true
    }});

    // 14.2 修复 window.chrome.webstore（旧版检测）
    if (window.chrome) {{
        window.chrome.webstore = undefined;  // 2023年后已废弃
    }}

    // ========== 15. iframe 检测修复 ==========
    // 正确处理 iframe contentWindow
    const originalContentWindow = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {{
        get: function() {{
            try {{
                return originalContentWindow.get.call(this);
            }} catch(e) {{
                return null;
            }}
        }},
        configurable: true
    }});

    // ========== 16. Function.prototype.toString 保护 ==========
    // 防止检测我们修改过的函数
    const originalToString = Function.prototype.toString;
    const nativeFunctionStr = 'function () {{ [native code] }}';

    const modifiedFunctions = new Set([
        navigator.permissions?.query,
        navigator.getBattery,
        WebGLRenderingContext.prototype.getParameter,
    ].filter(Boolean));

    Function.prototype.toString = function() {{
        if (modifiedFunctions.has(this)) {{
            return nativeFunctionStr;
        }}
        return originalToString.call(this);
    }};

    // ========== 17. Error 堆栈清理 ==========
    // 移除错误堆栈中的自动化痕迹
    const originalError = Error;
    window.Error = function(...args) {{
        const error = new originalError(...args);
        if (error.stack) {{
            error.stack = error.stack.replace(/playwright|puppeteer|selenium|webdriver/gi, 'chromium');
        }}
        return error;
    }};
    window.Error.prototype = originalError.prototype;

    console.log('[UltimateStealth] v2.0 initialized - all detection points patched');
}})();
"""


class UltimateStealthBrowser:
    """
    终极隐身浏览器 v2.0
    解决所有已知检测点
    """

    def __init__(
        self,
        headless: bool = False,
        proxy: Optional[str] = None,
        profile_dir: Optional[Path] = None,
        slow_mo: int = 0,
        country: str = "hk",
        fingerprint_index: int = 0,
    ):
        self.headless = headless
        self.proxy = proxy
        self.profile_dir = profile_dir or Path.home() / ".ultimate_stealth"
        self.slow_mo = slow_mo
        self.country = country

        # 选择指纹
        self.fingerprint = REAL_FINGERPRINTS[fingerprint_index % len(REAL_FINGERPRINTS)]

        self.playwright = None
        self.browser = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # 鼠标轨迹记录
        self.mouse_pos = {"x": 0, "y": 0}

    async def start(self) -> Page:
        """启动隐身浏览器"""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self.playwright = await async_playwright().start()

        # ============================================================
        # 关键改进：使用更少的自动化标志
        # ============================================================
        args = [
            # 核心：禁用自动化标志
            '--disable-blink-features=AutomationControlled',

            # 禁用不必要的功能（减少指纹）
            '--disable-features=IsolateOrigins,site-per-process,TranslateUI',
            '--disable-site-isolation-trials',
            '--disable-infobars',
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-breakpad',
            '--disable-component-extensions-with-background-pages',
            '--disable-component-update',
            '--disable-default-apps',
            '--disable-dev-shm-usage',
            '--disable-hang-monitor',
            '--disable-ipc-flooding-protection',
            '--disable-popup-blocking',
            '--disable-prompt-on-repost',
            '--disable-renderer-backgrounding',
            '--disable-sync',

            # 窗口大小
            f'--window-size={self.fingerprint["screen"]["width"]},{self.fingerprint["screen"]["height"]}',

            # 语言和时区
            f'--lang={self.fingerprint["language"]}',

            # 其他
            '--no-first-run',
            '--no-default-browser-check',
            '--password-store=basic',
            '--use-mock-keychain',

            # 关键：不要 --headless 参数，用 headless 选项
        ]

        # 添加绕过系统代理的参数
        args.append('--no-proxy-server')  # 关键：绕过 VPN/系统代理

        # 启动配置
        launch_options = {
            "channel": "chrome",  # 使用真实 Chrome
            "headless": self.headless,
            "args": args,
            "slow_mo": self.slow_mo,
            "ignore_default_args": [
                "--enable-automation",
                "--enable-blink-features=IdleDetection",
            ],
        }

        if self.proxy:
            launch_options["proxy"] = {"server": self.proxy}
        else:
            # 明确设置不使用代理，绕过 Clash/VPN
            launch_options["proxy"] = {"server": "direct://"}

        # 上下文配置
        context_options = {
            "viewport": {
                "width": self.fingerprint["screen"]["width"],
                "height": self.fingerprint["screen"]["height"]
            },
            "user_agent": self.fingerprint["user_agent"],
            "locale": self.fingerprint["language"],
            "timezone_id": self.fingerprint["timezone"],
            "color_scheme": "light",
            "device_scale_factor": self.fingerprint["screen"]["pixelRatio"],
            "is_mobile": False,
            "has_touch": self.fingerprint["max_touch_points"] > 0,
            "ignore_https_errors": True,
            "extra_http_headers": self._get_headers(),
        }

        # 使用持久化上下文
        self.context = await self.playwright.chromium.launch_persistent_context(
            str(self.profile_dir),
            **launch_options,
            **context_options,
        )

        # 注入反检测脚本（在每个页面加载前）
        stealth_script = get_stealth_script(self.fingerprint)
        await self.context.add_init_script(stealth_script)

        # 获取页面
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        # 初始化鼠标位置
        self.mouse_pos = {
            "x": self.fingerprint["screen"]["width"] // 2,
            "y": self.fingerprint["screen"]["height"] // 2
        }

        logger.info(f"[UltimateStealth] Started with fingerprint: {self.fingerprint['platform']}")
        return self.page

    def _get_headers(self) -> Dict[str, str]:
        """生成一致的 HTTP 头"""
        ua = self.fingerprint["user_agent"]

        # 从 UA 提取 Chrome 版本
        chrome_version = "121"
        if "Chrome/" in ua:
            chrome_version = ua.split("Chrome/")[1].split(".")[0]

        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": f"{self.fingerprint['language']},en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": f'"Not A(Brand";v="99", "Google Chrome";v="{chrome_version}", "Chromium";v="{chrome_version}"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": f'"{self.fingerprint["platform"][:3] if self.fingerprint["platform"] == "MacIntel" else "Windows"}"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    # ============================================================
    # 人类行为模拟
    # ============================================================

    async def human_goto(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 30000,
    ) -> bool:
        """人类式访问页面"""
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=timeout)

            # 模拟人类加载后行为
            await asyncio.sleep(random.uniform(1.0, 2.5))

            # 随机滚动
            await self._human_scroll()

            # 随机移动鼠标
            await self._random_mouse_move()

            return True
        except Exception as e:
            logger.error(f"[UltimateStealth] Goto failed: {e}")
            return False

    async def _human_scroll(self):
        """模拟人类滚动"""
        try:
            scroll_times = random.randint(1, 3)
            for _ in range(scroll_times):
                # 随机滚动方向和距离
                scroll_y = random.randint(100, 400)
                if random.random() < 0.2:  # 20% 概率向上滚动
                    scroll_y = -scroll_y

                # 平滑滚动
                steps = random.randint(5, 10)
                for i in range(steps):
                    await self.page.mouse.wheel(0, scroll_y / steps)
                    await asyncio.sleep(random.uniform(0.02, 0.05))

                await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception:
            pass

    async def _random_mouse_move(self):
        """随机移动鼠标"""
        try:
            # 随机目标位置
            target_x = random.randint(100, self.fingerprint["screen"]["width"] - 100)
            target_y = random.randint(100, self.fingerprint["screen"]["height"] - 100)

            await self._bezier_move(target_x, target_y)
        except Exception:
            pass

    async def _bezier_move(self, target_x: float, target_y: float):
        """贝塞尔曲线鼠标移动（更真实）"""
        start_x, start_y = self.mouse_pos["x"], self.mouse_pos["y"]

        # 生成控制点
        cp1_x = start_x + (target_x - start_x) * random.uniform(0.2, 0.4) + random.uniform(-50, 50)
        cp1_y = start_y + (target_y - start_y) * random.uniform(0.2, 0.4) + random.uniform(-50, 50)
        cp2_x = start_x + (target_x - start_x) * random.uniform(0.6, 0.8) + random.uniform(-30, 30)
        cp2_y = start_y + (target_y - start_y) * random.uniform(0.6, 0.8) + random.uniform(-30, 30)

        # 计算路径点
        steps = random.randint(20, 40)
        points = []
        for i in range(steps + 1):
            t = i / steps
            # 三次贝塞尔曲线
            x = (1-t)**3 * start_x + 3*(1-t)**2*t * cp1_x + 3*(1-t)*t**2 * cp2_x + t**3 * target_x
            y = (1-t)**3 * start_y + 3*(1-t)**2*t * cp1_y + 3*(1-t)*t**2 * cp2_y + t**3 * target_y
            points.append((x, y))

        # 移动鼠标
        for x, y in points:
            await self.page.mouse.move(x, y)
            # 随机延迟（人类手抖动）
            await asyncio.sleep(random.uniform(0.005, 0.02))

        self.mouse_pos = {"x": target_x, "y": target_y}

    async def human_click(self, selector: str, timeout: int = 5000) -> bool:
        """人类式点击"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if not element:
                return False

            box = await element.bounding_box()
            if not box:
                return False

            # 随机点击位置（不在正中心）
            x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            y = box["y"] + box["height"] * random.uniform(0.3, 0.7)

            # 贝塞尔曲线移动到目标
            await self._bezier_move(x, y)

            # 随机停顿（人类犹豫）
            await asyncio.sleep(random.uniform(0.1, 0.3))

            # 点击
            await self.page.mouse.click(x, y)

            return True
        except Exception as e:
            logger.warning(f"[UltimateStealth] Click failed: {e}")
            return False

    async def human_type(self, selector: str, text: str, timeout: int = 5000) -> bool:
        """人类式打字"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.human_click(selector)
            await asyncio.sleep(random.uniform(0.2, 0.5))

            for char in text:
                await self.page.keyboard.type(char, delay=random.randint(50, 150))

                # 偶尔打错再删除（更真实）
                if random.random() < 0.02:
                    wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
                    await self.page.keyboard.type(wrong_char, delay=random.randint(50, 100))
                    await asyncio.sleep(random.uniform(0.1, 0.2))
                    await self.page.keyboard.press('Backspace')

            return True
        except Exception as e:
            logger.warning(f"[UltimateStealth] Type failed: {e}")
            return False

    async def wait_for_cloudflare(self, max_wait: int = 20) -> bool:
        """等待 Cloudflare 验证"""
        for i in range(max_wait):
            try:
                title = await self.page.title()
                content = await self.page.content()

                # 检测 Cloudflare 挑战
                cf_indicators = [
                    "just a moment",
                    "checking your browser",
                    "cloudflare",
                    "please wait",
                    "verifying you are human",
                ]

                is_cf = any(ind in title.lower() or ind in content.lower() for ind in cf_indicators)

                if not is_cf:
                    logger.info(f"[UltimateStealth] Cloudflare passed after {i+1}s")
                    return True

                # 如果有 turnstile，尝试模拟人类行为
                if "turnstile" in content.lower():
                    await self._random_mouse_move()
                    await self._human_scroll()

            except Exception:
                pass

            await asyncio.sleep(1)

        logger.warning("[UltimateStealth] Cloudflare challenge timeout")
        return False

    async def save_cookies(self, path: str):
        """保存 cookies"""
        cookies = await self.context.cookies()
        with open(path, "w") as f:
            json.dump(cookies, f, indent=2)
        logger.info(f"[UltimateStealth] Cookies saved to {path}")

    async def load_cookies(self, path: str) -> bool:
        """加载 cookies"""
        try:
            with open(path, "r") as f:
                cookies = json.load(f)
            await self.context.add_cookies(cookies)
            logger.info(f"[UltimateStealth] Cookies loaded from {path}")
            return True
        except Exception as e:
            logger.warning(f"[UltimateStealth] Failed to load cookies: {e}")
            return False

    async def close(self):
        """关闭浏览器"""
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
        logger.info("[UltimateStealth] Closed")


# ============================================================
# 测试函数
# ============================================================
async def test_ultimate_stealth():
    """测试终极隐身浏览器"""
    browser = UltimateStealthBrowser(headless=False, country="hk")

    try:
        await browser.start()

        # 测试反检测
        print("🧪 Testing anti-detection...")
        await browser.human_goto("https://bot.sannysoft.com/")
        await asyncio.sleep(3)

        # 截图检查结果
        await browser.page.screenshot(path="stealth_test.png")
        print("📸 Screenshot saved to stealth_test.png")

        # 测试 Indeed
        print("\n🚀 Testing Indeed HK...")
        await browser.human_goto("https://hk.indeed.com/jobs?q=data+analyst&l=Hong+Kong")

        passed = await browser.wait_for_cloudflare()
        if passed:
            title = await browser.page.title()
            print(f"✅ Page: {title}")

            cards = await browser.page.query_selector_all('[data-jk]')
            print(f"🔍 Found {len(cards)} jobs")
        else:
            print("❌ Cloudflare blocked")

        await asyncio.sleep(5)

    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_ultimate_stealth())
