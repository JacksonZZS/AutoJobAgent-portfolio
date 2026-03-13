#!/usr/bin/env python3
"""
手动登录 JobsDB 并保存 Cookies
运行后会打开浏览器，你手动完成 Cloudflare 验证，然后按 Enter 保存 cookies
"""
import asyncio
import json
import sys
sys.path.insert(0, '.')

from pathlib import Path
from playwright.async_api import async_playwright

COOKIES_PATH = Path("data/cookies/jobsdb_cookies.json")

async def main():
    print("🚀 启动浏览器...")
    print("👆 请手动完成 Cloudflare 验证，然后回到终端按 Enter\n")

    async with async_playwright() as p:
        # 使用真实 Chrome，不加任何自动化标志
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        # 访问 JobsDB
        await page.goto("https://hk.jobsdb.com/jobs?keywords=Data%20Scientist")

        print("=" * 50)
        print("🔐 请在浏览器中完成 Cloudflare 验证")
        print("✅ 看到职位列表后，回到这里按 Enter")
        print("=" * 50)

        input("\n按 Enter 保存 cookies...")

        # 保存 cookies
        COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        cookies = await context.cookies()

        with open(COOKIES_PATH, "w") as f:
            json.dump(cookies, f, indent=2)

        print(f"\n✅ Cookies 已保存到: {COOKIES_PATH}")
        print(f"📊 共 {len(cookies)} 个 cookies")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
