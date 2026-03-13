#!/usr/bin/env python3
"""
Indeed 认证初始化脚本
自动等待 Cloudflare 验证通过，保存 cookies 供后续使用
"""
import asyncio
from pathlib import Path
from core.stealth_browser import StealthBrowser

async def init_indeed_auth(country: str = "hk"):
    """
    初始化 Indeed 认证
    打开浏览器，自动等待 Cloudflare 验证通过
    """
    print(f"🚀 初始化 Indeed {country.upper()} 认证...")
    print("=" * 50)

    # 使用与 IndeedScraper 相同的 profile 目录
    profile_dir = Path(__file__).parent / "chrome_profile" / f"indeed_{country}"
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 Profile 目录: {profile_dir}")

    # 创建浏览器（非 headless）
    browser = StealthBrowser(
        headless=False,
        profile_dir=profile_dir,
    )

    try:
        page = await browser.start()

        # 访问 Indeed
        indeed_urls = {
            "hk": "https://hk.indeed.com",
            "us": "https://www.indeed.com",
            "uk": "https://uk.indeed.com",
            "sg": "https://sg.indeed.com",
            "ca": "https://ca.indeed.com",
            "au": "https://au.indeed.com",
        }

        url = indeed_urls.get(country, "https://hk.indeed.com")
        print(f"\n🌐 正在访问: {url}")

        await page.goto(url, wait_until="domcontentloaded")

        print("\n" + "=" * 50)
        print("⚠️  如果看到 Cloudflare 验证页面:")
        print("   请在浏览器中点击 'Verify you are human'")
        print("=" * 50)

        # 自动等待 Cloudflare 验证通过（最多等 60 秒）
        print("\n⏳ 等待 Cloudflare 验证通过...")

        for i in range(60):
            title = await page.title()
            # 检查是否还在 Cloudflare 验证页
            if "moment" not in title.lower() and "cloudflare" not in title.lower() and "verify" not in title.lower():
                print(f"\n✅ 验证通过！页面标题: {title}")
                break
            await asyncio.sleep(1)
            if i % 10 == 0:
                print(f"   等待中... ({i}/60秒)")

        # 额外等待页面完全加载
        await asyncio.sleep(3)

        # 保存 cookies
        cookies_path = profile_dir / "cookies.json"
        await browser.save_cookies(str(cookies_path))
        print(f"\n💾 Cookies 已保存到: {cookies_path}")

        # 保持浏览器打开 10 秒让用户确认
        print("\n🔍 浏览器将在 10 秒后关闭...")
        await asyncio.sleep(10)

        print("\n🎉 认证初始化完成！现在可以运行自动投递了。")

    finally:
        await browser.close()


if __name__ == "__main__":
    import sys

    country = sys.argv[1] if len(sys.argv) > 1 else "hk"
    print(f"初始化 Indeed {country.upper()} 站点认证\n")

    asyncio.run(init_indeed_auth(country))
