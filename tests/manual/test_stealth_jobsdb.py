#!/usr/bin/env python3
"""
测试反爬浏览器能否绕过 JobsDB 的 Cloudflare
"""
import asyncio
import sys
sys.path.insert(0, '.')

from core.ultimate_stealth import UltimateStealthBrowser
from pathlib import Path

async def test():
    print("🚀 启动反爬浏览器...")

    browser = UltimateStealthBrowser(
        headless=False,  # 显示浏览器方便观察
        profile_dir=Path("data/browser_profiles/test_stealth"),
        country="hk",
    )

    try:
        page = await browser.start()
        print("✅ 浏览器启动成功")

        # 访问 JobsDB
        url = "https://hk.jobsdb.com/jobs?keywords=Data%20Scientist"
        print(f"\n📄 访问: {url}")

        success = await browser.human_goto(url, timeout=60000)
        if not success:
            print("❌ 页面加载失败")
            return

        print("⏳ 等待 Cloudflare 验证...")
        cf_passed = await browser.wait_for_cloudflare(max_wait=30)

        if cf_passed:
            print("✅ Cloudflare 验证通过!")
        else:
            print("⚠️ Cloudflare 可能还在验证中...")

        # 检查页面标题
        title = await page.title()
        print(f"\n📌 页面标题: {title}")

        # 检测是否还在 Cloudflare
        if "moment" in title.lower() or "cloudflare" in title.lower():
            print("❌ 仍被 Cloudflare 拦截")
            await page.screenshot(path="test_cf_blocked.png")
            print("📸 截图: test_cf_blocked.png")
        else:
            print("✅ 成功进入 JobsDB!")

            # 等待职位卡片
            await asyncio.sleep(2)

            # 测试选择器
            selectors = [
                ("article", "article 标签"),
                ('[data-automation="jobTitle"]', 'jobTitle'),
            ]

            print("\n🔎 测试选择器:")
            for selector, desc in selectors:
                elements = await page.query_selector_all(selector)
                count = len(elements)
                if count > 0:
                    print(f"   ✅ {desc}: 找到 {count} 个")
                else:
                    print(f"   ❌ {desc}: 0 个")

            # 截图
            await page.screenshot(path="test_jobsdb_success.png")
            print("\n📸 截图: test_jobsdb_success.png")

        print("\n⏳ 5秒后关闭浏览器...")
        await asyncio.sleep(5)

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        print("👋 浏览器已关闭")

if __name__ == "__main__":
    asyncio.run(test())
