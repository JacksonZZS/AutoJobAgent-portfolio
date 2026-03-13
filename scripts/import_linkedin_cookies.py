#!/usr/bin/env python3
"""
LinkedIn Cookie 导入工具

使用方法:
1. 用你的 Chrome 浏览器登录 LinkedIn
2. 安装 Chrome 扩展 "EditThisCookie" 或 "Cookie-Editor"
3. 导出 LinkedIn cookies 为 JSON 格式
4. 保存到 linkedin_cookies.json
5. 运行此脚本导入
"""

import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

PROJECT_ROOT = Path(__file__).parent.parent
COOKIE_FILE = PROJECT_ROOT / "linkedin_cookies.json"
PROFILE_DIR = PROJECT_ROOT / "chrome_profile" / "linkedin"


async def import_cookies():
    """导入 LinkedIn cookies 到浏览器 profile"""

    if not COOKIE_FILE.exists():
        print(f"❌ Cookie 文件不存在: {COOKIE_FILE}")
        print("\n请按以下步骤操作:")
        print("1. 用你的 Chrome 浏览器登录 LinkedIn")
        print("2. 安装扩展 'Cookie-Editor' 或 'EditThisCookie'")
        print("3. 在 LinkedIn 页面点击扩展，导出所有 cookies")
        print(f"4. 保存到: {COOKIE_FILE}")
        return False

    # 读取 cookies
    with open(COOKIE_FILE, "r") as f:
        cookies = json.load(f)

    print(f"📄 读取到 {len(cookies)} 个 cookies")

    # 转换格式 (EditThisCookie -> Playwright)
    playwright_cookies = []
    for cookie in cookies:
        pc = {
            "name": cookie.get("name"),
            "value": cookie.get("value"),
            "domain": cookie.get("domain", ".linkedin.com"),
            "path": cookie.get("path", "/"),
        }
        # 可选字段
        if cookie.get("expirationDate"):
            pc["expires"] = cookie["expirationDate"]
        if cookie.get("secure"):
            pc["secure"] = cookie["secure"]
        if cookie.get("httpOnly"):
            pc["httpOnly"] = cookie["httpOnly"]

        # 转换 sameSite 格式
        same_site = cookie.get("sameSite")
        if same_site:
            # 转换 Chrome 格式到 Playwright 格式
            same_site_map = {
                "no_restriction": "None",
                "lax": "Lax",
                "strict": "Strict",
                "unspecified": "Lax",
            }
            pc["sameSite"] = same_site_map.get(same_site.lower(), "Lax") if isinstance(same_site, str) else "Lax"

        playwright_cookies.append(pc)

    # 启动浏览器并添加 cookies
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # 添加 cookies
        await context.add_cookies(playwright_cookies)
        print(f"✅ 已添加 {len(playwright_cookies)} 个 cookies")

        # 测试登录状态
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.linkedin.com/feed/")
        await asyncio.sleep(3)

        if "/login" in page.url or "/authwall" in page.url:
            print("❌ Cookie 无效或已过期，请重新导出")
            await context.close()
            return False
        else:
            print("✅ LinkedIn 登录成功！")
            print("🔒 登录状态已保存到 chrome_profile/linkedin/")
            await context.close()
            return True


if __name__ == "__main__":
    asyncio.run(import_cookies())
