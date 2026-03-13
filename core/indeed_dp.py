# core/indeed_dp.py
"""
Indeed 爬虫 - 使用 DrissionPage 绕过 Cloudflare
DrissionPage 是国产反爬神器，结合了 Selenium 和 Requests 的优点

🔴 反检测策略：
1. 使用 Profile 目录保存登录态，首次验证后复用
2. 窗口移到屏幕外，不打扰用户
3. 模拟人类行为（随机延迟、滚动）
"""

import time
import random
import logging
import json
import subprocess
from typing import List, Optional
from dataclasses import dataclass
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime, timedelta

from DrissionPage import ChromiumPage, ChromiumOptions

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


@dataclass
class IndeedJob:
    """Indeed 职位信息"""
    job_id: str
    title: str
    company: str
    location: str
    job_url: str
    salary: Optional[str] = None
    jd_content: str = ""
    is_easy_apply: bool = False
    source: str = "indeed"


class IndeedDPScraper:
    """
    Indeed 爬虫 - 使用 DrissionPage
    DrissionPage 的优势：
    1. 基于 CDP (Chrome DevTools Protocol)，不是 WebDriver
    2. 更难被检测
    3. 支持接管已打开的浏览器

    🔴 Session 复用策略：
    - 首次运行需要手动验证 CAPTCHA
    - 验证后 Cookie 保存在 chrome_profile 目录
    - 后续运行自动复用，无需再验证（通常 24-48 小时有效）
    """

    # Session 状态文件
    SESSION_FILE = "session_status.json"
    COOKIE_FILE = "indeed_cookies.json"  # 手动导出的 Cookie

    def __init__(
        self,
        user_id: str,
        headless: bool = False,  # 🔴 保持有头模式，但窗口会移到屏幕外
        country: str = "hk",
        background_mode: bool = True,  # 🔴 新增：后台模式（窗口不可见）
    ):
        self.user_id = user_id
        self.headless = headless
        self.country = country
        self.background_mode = background_mode
        self.base_url = INDEED_COUNTRY_URLS.get(country, "https://www.indeed.com")
        self.history = HistoryManager(user_id=user_id)
        self.page = None

        # Profile 目录
        self.profile_dir = Path(__file__).parent.parent / "chrome_profile" / f"indeed_dp_{country}"
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        # Session 状态
        self.session_file = self.profile_dir / self.SESSION_FILE

        # 手动导出的 Cookie 文件
        self.cookie_file = Path(__file__).parent.parent / "chrome_profile" / self.COOKIE_FILE

        # 🔴 风控：请求计数 + 自适应延迟
        self._request_count = 0          # 本次会话总请求数
        self._last_request_time = 0.0    # 上次请求时间戳
        self._cloudflare_hits = 0        # 被 Cloudflare 拦截次数

    def _load_manual_cookies(self) -> bool:
        """加载手动导出的 Cookie（cf_clearance）"""
        if not self.cookie_file.exists():
            return False

        try:
            with open(self.cookie_file, 'r') as f:
                data = json.load(f)

            cookies = data.get("cookies", [])
            if not cookies:
                return False

            # 通过 JavaScript 设置 Cookie
            for cookie in cookies:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                domain = cookie.get("domain", ".indeed.com")

                if name and value:
                    js_code = f'document.cookie = "{name}={value}; domain={domain}; path=/; secure";'
                    try:
                        self.page.run_js(js_code)
                        print(f"   🍪 已加载 Cookie: {name}")
                    except Exception as e:
                        print(f"   ⚠️ 加载 Cookie 失败: {e}")

            return True
        except Exception as e:
            print(f"   ⚠️ 读取 Cookie 文件失败: {e}")
            return False

    def _check_session_valid(self) -> bool:
        """检查 Session 是否有效（24小时内验证过）"""
        if not self.session_file.exists():
            return False

        try:
            with open(self.session_file, 'r') as f:
                status = json.load(f)

            last_verified = datetime.fromisoformat(status.get("last_verified", "2000-01-01"))
            # Session 有效期 24 小时
            if datetime.now() - last_verified < timedelta(hours=24):
                print(f"   ✅ Session 有效（上次验证: {last_verified.strftime('%Y-%m-%d %H:%M')}）")
                return True
        except Exception:
            pass

        return False

    def _save_session_status(self):
        """保存 Session 状态"""
        try:
            status = {
                "last_verified": datetime.now().isoformat(),
                "country": self.country,
            }
            with open(self.session_file, 'w') as f:
                json.dump(status, f)
        except Exception as e:
            print(f"   ⚠️ 保存 Session 状态失败: {e}")

    def _send_macos_notification(self, title: str, message: str):
        """发送 macOS 系统通知 + 弹窗，确保用户看到"""
        try:
            # 1. 系统通知（通知中心）
            subprocess.run([
                'osascript', '-e',
                f'display notification "{message}" with title "{title}" sound name "Glass"'
            ], timeout=5)
            # 2. 弹窗置前（确保用户看到）
            subprocess.run([
                'osascript', '-e',
                f'display dialog "{message}" with title "{title}" buttons {{"去验证"}} default button "去验证" giving up after 30'
            ], timeout=35)
        except Exception as e:
            print(f"   ⚠️ macOS 通知发送失败: {e}")

    def _bring_browser_to_front(self):
        """将 Chrome 浏览器窗口置前"""
        try:
            subprocess.run([
                'osascript', '-e',
                'tell application "Google Chrome" to activate'
            ], timeout=5)
        except Exception:
            pass

    def _get_cdp_window_id(self):
        """获取当前 Chrome 窗口的 windowId"""
        try:
            result = self.page.run_cdp('Browser.getWindowForTarget')
            return result.get('windowId', 1)
        except Exception:
            return 1

    def _move_window_to_screen(self):
        """把窗口移回屏幕内（需要手动验证时）- 三层保障"""
        window_id = self._get_cdp_window_id()

        # Method 1 (最可靠): CDP 协议直接控制窗口
        try:
            self.page.run_cdp('Browser.setWindowBounds', windowId=window_id, bounds={
                'left': 100, 'top': 100, 'width': 1400, 'height': 900, 'windowState': 'normal'
            })
        except Exception as e:
            print(f"   ⚠️ CDP setWindowBounds failed: {e}")

        # Method 2: JS 兜底
        try:
            self.page.run_js("window.moveTo(100, 100); window.resizeTo(1400, 900);")
        except Exception:
            pass

        # Method 3: macOS AppleScript 兜底
        try:
            subprocess.run([
                'osascript', '-e',
                'tell application "Google Chrome"\n'
                '  activate\n'
                '  set bounds of front window to {100, 100, 1500, 1000}\n'
                'end tell'
            ], timeout=5)
        except Exception:
            pass

        print("   🖥️ 窗口已移到屏幕内，请手动完成验证...")
        self._bring_browser_to_front()
        self._send_macos_notification(
            "Indeed Session 过期",
            "需要人机验证！请到浏览器窗口完成验证。"
        )

    def _move_window_off_screen(self):
        """隐藏窗口 - 用最小化代替移到屏幕外

        🔴 关键发现：窗口移到屏幕外时，Chrome 会降低渲染优先级，
        导致 Cloudflare JS challenge 无法正常执行，验证永远过不了。
        改用最小化：窗口不可见但 JS 仍正常运行。
        """
        window_id = self._get_cdp_window_id()

        # Method 1 (最可靠): CDP 最小化
        try:
            self.page.run_cdp('Browser.setWindowBounds', windowId=window_id, bounds={
                'windowState': 'minimized'
            })
            print("   🔽 窗口已最小化")
            return
        except Exception as e:
            print(f"   ⚠️ CDP minimize failed: {e}")

        # Method 2: AppleScript 最小化
        try:
            subprocess.run([
                'osascript', '-e',
                'tell application "Google Chrome"\n'
                '  set miniaturized of front window to true\n'
                'end tell'
            ], timeout=5)
            print("   🔽 窗口已最小化 (AppleScript)")
            return
        except Exception:
            pass

        # Method 3: 实在不行才移到屏幕外
        try:
            self.page.run_cdp('Browser.setWindowBounds', windowId=window_id, bounds={
                'left': -5000, 'top': -5000, 'width': 1400, 'height': 900, 'windowState': 'normal'
            })
        except Exception:
            pass

    def _create_page(self, force_visible: bool = False):
        """创建 DrissionPage 浏览器

        Args:
            force_visible: 强制显示窗口（用于首次验证）
        """
        co = ChromiumOptions()

        # 使用独立的用户数据目录（保存 Cookie 和登录态）
        co.set_user_data_path(str(self.profile_dir))

        # 基本配置（精简版 - 去掉暴露自动化特征的参数）
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--window-size=1920,1080')
        co.set_argument('--lang=en-US')

        # 🔴 绕过 VPN/系统代理（关键！）
        co.set_argument('--no-proxy-server')

        # 🔴 窗口位置：始终在屏幕内启动
        # 不再用 --window-position=-2400 移到屏幕外！
        # 原因：Chrome 窗口在屏幕外时会降低渲染优先级，Cloudflare JS challenge 过不了
        # 策略：正常位置启动 → 创建后立刻最小化
        co.set_argument('--window-position=100,100')

        # 🔴 反检测配置（只保留最关键的一个）
        co.set_argument('--disable-blink-features=AutomationControlled')
        # 注意：去掉了 --disable-infobars 和 --disable-extensions
        # 这两个参数会让浏览器指纹看起来像自动化工具

        # 🔴 User-Agent 必须和实际 Chrome 版本匹配！
        # 你的 Chrome 是 145.0.7632.46，写 120 会被 Cloudflare 直接标记可疑
        co.set_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.7632.46 Safari/537.36')

        if self.headless:
            co.headless(True)

        # 创建页面
        self.page = ChromiumPage(co)

        # 🔴 后台模式：启动后立刻最小化，避免打扰用户
        # 注意：不能移到屏幕外！Chrome 屏幕外会降低渲染优先级，Cloudflare 过不了
        if self.background_mode and not self.headless and not force_visible:
            self._move_window_off_screen()

        # 🔴 先访问 Indeed 首页（设置 Cookie 需要先在域名下）
        self.page.get(self.base_url)
        time.sleep(1)

        # 🔴 加载手动导出的 Cookie（cf_clearance）
        if self.cookie_file.exists():
            self._load_manual_cookies()

        # 🔴 注入反检测脚本
        try:
            self.page.run_js("""
                // 隐藏 webdriver 标志
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                // 隐藏 Chrome 自动化特征
                window.chrome = { runtime: {} };
            """)
        except Exception:
            pass

        print(f"   🔑 DrissionPage 已启动，Profile: {self.profile_dir}")
        return self.page

    def _anti_detect_delay(self):
        """🔴 风控：自适应延迟，模拟真人浏览节奏

        策略：
        - 前 3 次请求：5-10 秒（刚开始浏览，节奏正常）
        - 4-8 次请求：10-20 秒（浏览久了会慢下来）
        - 9+ 次请求：15-30 秒（疲劳期，真人会更慢）
        - 被 Cloudflare 拦截过：额外加 10-20 秒惩罚
        - 确保两次请求间隔至少 5 秒
        """
        self._request_count += 1
        now = time.time()

        # 确保最小间隔
        elapsed = now - self._last_request_time if self._last_request_time > 0 else 999
        min_gap = 5.0

        if elapsed < min_gap:
            time.sleep(min_gap - elapsed)

        # 自适应延迟
        if self._request_count <= 3:
            delay = random.uniform(5, 10)
        elif self._request_count <= 8:
            delay = random.uniform(10, 20)
        else:
            delay = random.uniform(15, 30)

        # Cloudflare 惩罚：被拦截过就更慢
        if self._cloudflare_hits > 0:
            penalty = random.uniform(10, 20) * min(self._cloudflare_hits, 3)
            delay += penalty
            print(f"   🛡️ 风控延迟: {delay:.0f}s（含 Cloudflare 惩罚 {penalty:.0f}s, 拦截次数: {self._cloudflare_hits}）")
        else:
            print(f"   🛡️ 风控延迟: {delay:.0f}s（第 {self._request_count} 次请求）")

        time.sleep(delay)
        self._last_request_time = time.time()

    def _human_browse_simulation(self):
        """🔴 模拟真人浏览行为：随机滚动 + 停顿 + 鼠标移动"""
        actions = random.randint(2, 5)
        for _ in range(actions):
            action = random.choice(['scroll', 'pause', 'scroll_up'])
            if action == 'scroll':
                try:
                    self.page.scroll.down(random.randint(200, 500))
                except Exception:
                    pass
                time.sleep(random.uniform(0.5, 2.0))
            elif action == 'scroll_up':
                try:
                    self.page.scroll.up(random.randint(100, 300))
                except Exception:
                    pass
                time.sleep(random.uniform(0.3, 1.0))
            elif action == 'pause':
                time.sleep(random.uniform(1.0, 3.0))

    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """随机延迟"""
        time.sleep(random.uniform(min_sec, max_sec))

    def _human_scroll(self):
        """模拟人类滚动"""
        try:
            self.page.scroll.down(random.randint(300, 600))
            self._random_delay(0.5, 1.0)
        except Exception:
            pass

    def _wait_for_cloudflare(self, max_wait: int = 300) -> bool:
        """等待 Cloudflare 验证通过（智能弹窗）

        增强版：
        - 超时延长到 300 秒（5 分钟），给足手动验证时间
        - 每 5 秒打印 debug 信息（title + URL）
        - 更多验证通过判断条件
        - 验证失败时截图保存
        """
        print("   ⏳ 检测页面状态...")

        need_manual_verify = False
        notification_count = 0
        verify_loop_count = 0  # 检测验证循环：验证通过后又回到验证页

        for i in range(max_wait):
            try:
                title = self.page.title.lower() if self.page.title else ""
                current_url = (self.page.url or "").lower()

                # 🔴 每 5 秒打印 debug（帮助排查问题）
                if i % 5 == 0 and i > 0:
                    print(f"   [DEBUG] {i}s | title='{title[:60]}' | url='{current_url[:80]}'")

                # ===== 1. 检查是否需要验证 =====
                # 🔴 必须先检查！这些关键词出现就说明还没通过
                challenge_keywords_in_title = (
                    "just a moment" in title
                    or "cloudflare" in title
                    or "verify" in title
                    or "captcha" in title
                    or "robot" in title
                    or "human" in title
                    or "security check" in title
                    or "checking" in title
                    or "attention required" in title
                    or "access denied" in title
                )
                challenge_keywords_in_url = (
                    "challenge" in current_url
                    or "cdn-cgi" in current_url
                    or "__cf_chl" in current_url
                )
                is_challenge = challenge_keywords_in_title or challenge_keywords_in_url

                if is_challenge:
                    if not need_manual_verify:
                        need_manual_verify = True
                        self._cloudflare_hits += 1  # 🔴 风控：记录被拦截次数，影响后续延迟
                        print(f"   ⚠️ 检测到需要人机验证！(第 {self._cloudflare_hits} 次) title='{title}' url='{current_url[:80]}'")
                        self._move_window_to_screen()

                    # 每 30 秒再次通知
                    if i % 30 == 0 and notification_count < 5:
                        notification_count += 1
                        if notification_count > 1:
                            print(f"   ⏳ 仍在等待验证... ({i}s) - 请完成浏览器中的验证")
                            self._bring_browser_to_front()
                    elif i % 10 == 0:
                        print(f"   ⏳ 等待验证中... ({i}s)")

                    time.sleep(1)
                    continue

                # ===== 2. 检查是否验证通过 =====

                # 条件 A: 检测到职位卡片
                job_cards = self.page.eles('css:[data-jk]') or self.page.eles('css:.jobsearch-ResultsList')
                if job_cards:
                    print(f"   ✅ 页面加载成功，检测到职位卡片 ({i}s)")
                    self._save_session_status()
                    if self.background_mode:
                        self._move_window_off_screen()
                    return True

                # 条件 B: Indeed 正常页面 title
                # 🔴 注意：必须排除验证页面的 title（如 "security check - indeed.com"）
                # 所以不能只检查 "indeed" in title，要确认不含验证关键词
                is_indeed_page = (
                    not challenge_keywords_in_title
                    and not challenge_keywords_in_url
                    and (
                        "job search" in title
                        or ("jobs" in title and "indeed" in current_url)
                        or ("indeed" in title and "security" not in title and "check" not in title)
                    )
                )
                if is_indeed_page:
                    print(f"   ✅ Cloudflare 验证通过 ({i}s) | title='{title}'")
                    self._save_session_status()
                    if self.background_mode:
                        self._move_window_off_screen()
                    return True

                # 条件 C: URL 已经是 Indeed 正常页面（即使 title 还没更新）
                is_indeed_url = (
                    not challenge_keywords_in_title
                    and not challenge_keywords_in_url
                    and (
                        "indeed.com/jobs" in current_url
                        or "indeed.com/?from" in current_url
                        or "indeed.com/m/" in current_url
                    )
                )
                # URL 是 Indeed 但不是首页根路径（等 title 加载完再确认）
                if is_indeed_url and i > 3:
                    # 给 3 秒让 title 加载，避免误判
                    print(f"   ✅ 已到达 Indeed 页面 ({i}s) | url='{current_url[:80]}'")
                    self._save_session_status()
                    if self.background_mode:
                        self._move_window_off_screen()
                    return True

                # ===== 3. 未知状态，继续等待 =====
                if i % 10 == 0:
                    print(f"   ⏳ 等待页面加载... ({i}s) | title='{title[:40]}' | url='{current_url[:60]}'")
                time.sleep(1)

            except Exception as e:
                if i % 10 == 0:
                    print(f"   ⚠️ 检测异常: {e}")
                time.sleep(1)
                continue

        # 超时 - 截图保存用于排查
        print("   ❌ 验证超时 (300s)")
        try:
            screenshot_path = self.profile_dir / f"timeout_{int(time.time())}.png"
            self.page.get_screenshot(path=str(screenshot_path))
            print(f"   📸 超时截图已保存: {screenshot_path}")
        except Exception:
            pass
        return False

    def search_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        page: int = 1,
        fetch_jd: bool = True,  # 🔴 新增：是否抓取详细 JD
    ) -> List[IndeedJob]:
        """搜索 Indeed 职位"""
        if not self.page:
            self._create_page()

        jobs = []

        # 🔴 风控：搜索前自适应延迟（第一次请求除外）
        if self._request_count > 0:
            self._anti_detect_delay()

        # 构建搜索 URL
        params = {
            "q": keyword,
            "start": (page - 1) * 10,
        }
        if location:
            params["l"] = location

        search_url = f"{self.base_url}/jobs?{urlencode(params)}"
        print(f"   🔍 Indeed DP: {search_url}")

        try:
            # 访问搜索页
            self.page.get(search_url)
            self._random_delay(3, 6)  # 🔴 延长等待，避免 Cloudflare 风控

            # 等待 Cloudflare 验证
            if not self._wait_for_cloudflare():
                return []

            # 🔴 模拟真人浏览行为（随机滚动 + 停顿）
            self._human_browse_simulation()

            # 🔴 修复：使用完整的卡片容器选择器（不是 <a> 链接）
            # 2025 新版选择器
            job_cards = self.page.eles('css:.cardOutline')
            if not job_cards:
                job_cards = self.page.eles('css:.resultContent')
            if not job_cards:
                # 备用选择器
                job_cards = self.page.eles('css:.job_seen_beacon')
            if not job_cards:
                # 列表项
                job_cards = self.page.eles('css:.jobsearch-ResultsList > li')

            print(f"   📦 找到 {len(job_cards)} 个职位卡片")

            for idx, card in enumerate(job_cards, 1):
                try:
                    print(f"      [{idx}/{len(job_cards)}] 解析中...", end="", flush=True)
                    job = self._parse_job_card(card)
                    if job and not self.history.is_processed(job.job_id):
                        # 🔴 自动抓取详细 JD
                        if fetch_jd:
                            print(f" 📖", end="", flush=True)
                            jd = self.get_job_details_from_sidebar(job.job_id)
                            job.jd_content = jd
                        jobs.append(job)
                        print(f" ✅ {job.title[:30]}")
                    else:
                        print(f" ⏭️ 跳过")
                except Exception as e:
                    print(f" ❌ {e}")
                    continue

            print(f"   ✅ Indeed DP 找到 {len(jobs)} 个有效职位")

        except Exception as e:
            logger.error(f"[IndeedDP] Search error: {e}")
            print(f"   ❌ Indeed DP 搜索失败: {e}")

        return jobs

    def _parse_job_card(self, card) -> Optional[IndeedJob]:
        """解析职位卡片"""
        try:
            # 🔴 调试：打印卡片 HTML（前 500 字符）
            try:
                card_html = card.html[:500] if hasattr(card, 'html') else str(card)[:500]
                print(f"      [DEBUG] 卡片 HTML: {card_html[:200]}...")
            except:
                pass

            # 获取职位标题 - 减少超时
            title_elem = card.ele('css:.jobTitle span', timeout=0.5)
            if not title_elem:
                title_elem = card.ele('css:h2.jobTitle a', timeout=0.5)
            if not title_elem:
                return None

            title = title_elem.text.strip()
            if not title:
                return None

            # 获取 job_id - 优先从卡片本身获取
            job_id = card.attr('data-jk')  # 卡片本身可能就是 <a data-jk="xxx">

            if not job_id:
                link_elem = card.ele('css:a[data-jk]', timeout=0.5)
                if link_elem:
                    job_id = link_elem.attr('data-jk')

            if not job_id:
                # 尝试从其他属性获取
                jk_elem = card.ele('css:[data-jk]', timeout=0.5)
                if jk_elem:
                    job_id = jk_elem.attr('data-jk')

            if not job_id:
                # 尝试从卡片本身获取 data-jk
                job_id = card.attr('data-jk')

            if not job_id:
                # 生成一个基于标题的 ID（这会导致链接无效！）
                import hashlib
                job_id = hashlib.md5(title.encode()).hexdigest()[:16]
                print(f" ⚠️ 使用假ID: {job_id}")

            # 获取公司名称 - 添加更多备用选择器
            company = "Unknown Company"
            company_selectors = [
                'css:[data-testid="company-name"]',
                'css:.companyName',
                'css:.company_location .companyName',
                'css:span.css-1h7lukg',  # Indeed 新版样式
                'css:.metadata .companyName',
                'css:.company',
                'css:span[data-testid="company-name"]',
                'css:.jobMetaData .companyName',  # 新增
                'css:div[class*="company"]',  # 通配
            ]
            for selector in company_selectors:
                try:
                    company_elem = card.ele(selector, timeout=0.3)
                    if company_elem and company_elem.text.strip():
                        company = company_elem.text.strip()
                        print(f"      [DEBUG] 公司名找到! 选择器: {selector} → {company}")
                        break
                except:
                    continue

            if company == "Unknown Company":
                print(f"      [DEBUG] ⚠️ 公司名未找到，尝试打印所有文本...")
                try:
                    all_text = card.text[:300] if hasattr(card, 'text') else ""
                    print(f"      [DEBUG] 卡片文本: {all_text}")
                except:
                    pass

            # 获取地点
            location = ""
            location_elem = card.ele('css:[data-testid="text-location"]', timeout=0.5)
            if not location_elem:
                location_elem = card.ele('css:.companyLocation', timeout=0.5)
            if location_elem:
                location = location_elem.text.strip()

            # 获取薪资 - 最短超时
            salary = None
            salary_elem = card.ele('css:.salary-snippet', timeout=0.3)
            if salary_elem:
                salary = salary_elem.text.strip()

            # 构建职位 URL
            job_url = f"{self.base_url}/viewjob?jk={job_id}"

            return IndeedJob(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                job_url=job_url,
                salary=salary,
            )

        except Exception as e:
            logger.warning(f"Error parsing job card: {e}")
            return None

    def get_job_details(self, job_url: str) -> str:
        """获取职位详情 (JD) - 2025 版本，从搜索页侧边栏获取"""
        if not self.page:
            self._create_page()

        try:
            # 从 job_url 提取 job_id
            import re
            match = re.search(r'jk=([a-f0-9]+)', job_url)
            if not match:
                print(f"         ⚠️ 无法从 URL 提取 job_id")
                return ""

            job_id = match.group(1)

            # 检查当前页面是否是 Indeed 搜索页
            current_url = self.page.url or ""
            if "indeed.com/jobs" not in current_url:
                # 需要先访问搜索页
                search_url = f"{self.base_url}/jobs?q=&vjk={job_id}"
                print(f"         📖 访问: {search_url[:60]}...")
                self.page.get(search_url)
                self._random_delay(2, 3)

            # 方法1: 直接点击对应的职位卡片
            job_card = self.page.ele(f'css:a[data-jk="{job_id}"]', timeout=5)
            if job_card:
                job_card.click()
                self._random_delay(1, 2)

            # 方法2: 从侧边栏获取 JD
            jd_elem = self.page.ele('css:#jobDescriptionText', timeout=10)
            if not jd_elem:
                jd_elem = self.page.ele('css:.jobsearch-jobDescriptionText', timeout=5)
            if not jd_elem:
                jd_elem = self.page.ele('css:[id*="jobDescription"]', timeout=3)

            if jd_elem and jd_elem.text:
                jd_text = jd_elem.text.strip()
                print(f"         ✅ JD 长度: {len(jd_text)} 字符")
                return jd_text
            else:
                print(f"         ⚠️ 未找到 JD 元素")
                return ""

        except Exception as e:
            print(f"         ❌ 获取 JD 失败: {e}")
            return ""

    def get_job_details_from_sidebar(self, job_id: str) -> str:
        """从当前页面的侧边栏获取 JD（需要先点击职位卡片）

        Indeed 2025 版本的搜索结果页：
        - 左侧是职位列表，右侧是侧边栏显示 JD
        - 点击左侧卡片 → 右侧侧边栏加载 JD 内容
        """
        try:
            # ===== 1. 点击职位卡片，触发侧边栏加载 =====
            clicked = False

            # 尝试多种选择器点击卡片
            click_selectors = [
                f'css:a[data-jk="{job_id}"]',
                f'css:[data-jk="{job_id}"]',
                f'css:td.resultContent a[data-jk="{job_id}"]',
                f'css:h2.jobTitle a[data-jk="{job_id}"]',
            ]
            for selector in click_selectors:
                try:
                    job_card = self.page.ele(selector, timeout=1)
                    if job_card:
                        job_card.click()
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                print(f" ⚠️ 未找到卡片({job_id[:8]})", end="", flush=True)

            # 等待侧边栏加载（关键！之前等太短）
            self._random_delay(2, 3)

            # ===== 2. 从侧边栏获取 JD 内容 =====
            jd_selectors = [
                'css:#jobDescriptionText',
                'css:.jobsearch-jobDescriptionText',
                'css:[id*="jobDescription"]',
                'css:.jobsearch-JobComponent-description',
                'css:[data-testid="jobDescriptionText"]',
                'css:.jobDescription',
                'css:#jobsearch-ViewjobPaneWrapper',
            ]

            for selector in jd_selectors:
                try:
                    jd_elem = self.page.ele(selector, timeout=2)
                    if jd_elem and jd_elem.text and len(jd_elem.text.strip()) > 50:
                        jd_text = jd_elem.text.strip()
                        print(f" 📄{len(jd_text)}字", end="", flush=True)
                        return jd_text
                except Exception:
                    continue

            # ===== 3. 兜底：尝试从 iframe 获取 =====
            try:
                iframe = self.page.ele('css:iframe[id*="vjs"]', timeout=2)
                if iframe:
                    # 切换到 iframe 内部
                    iframe_page = iframe.ele('css:body', timeout=2)
                    if iframe_page and iframe_page.text and len(iframe_page.text.strip()) > 50:
                        jd_text = iframe_page.text.strip()
                        print(f" 📄{len(jd_text)}字(iframe)", end="", flush=True)
                        return jd_text
            except Exception:
                pass

            print(f" ⚠️JD空", end="", flush=True)
            return ""
        except Exception as e:
            print(f" ❌JD:{e}", end="", flush=True)
            return ""

    def close(self):
        """关闭浏览器"""
        if self.page:
            try:
                self.page.quit()
            except Exception:
                pass
            self.page = None
            print("   🔒 DrissionPage 已关闭")


# 测试函数
def test_indeed_dp():
    """测试 Indeed DP 爬虫"""
    print("\n🚀 测试 Indeed DP 爬虫 (DrissionPage)")
    print("=" * 50)

    scraper = IndeedDPScraper(
        user_id="test",
        headless=False,
        country="hk",
    )

    try:
        jobs = scraper.search_jobs("data analyst", page=1)
        print(f"\n📊 找到 {len(jobs)} 个职位")

        for i, job in enumerate(jobs[:5], 1):
            print(f"\n{i}. {job.title}")
            print(f"   公司: {job.company}")
            print(f"   地点: {job.location}")
            print(f"   链接: {job.job_url}")

        if jobs:
            print(f"\n📖 获取第一个职位的 JD...")
            jd = scraper.get_job_details(jobs[0].job_url)
            print(f"   JD 长度: {len(jd)} 字符")
            if jd:
                print(f"   预览: {jd[:200]}...")

    finally:
        scraper.close()

    print("\n✅ 测试完成")


if __name__ == "__main__":
    test_indeed_dp()
