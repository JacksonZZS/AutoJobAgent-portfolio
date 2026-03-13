#!/usr/bin/env python3
"""
反爬测试脚本 - 使用 ultimate_stealth 模块测试
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.ultimate_stealth import UltimateStealthBrowser

async def test_antibot():
    print("🧪 反爬测试开始 (使用 UltimateStealthBrowser)...")
    print("=" * 50)

    browser = UltimateStealthBrowser(
        headless=False,  # 有头模式，方便观察
        country="hk"
    )

    try:
        page = await browser.start()
        print("   ✅ 反爬浏览器启动成功")

        # 测试 1: JobsDB
        print("\n📍 测试 1: JobsDB (hk.jobsdb.com)")
        try:
            success = await browser.human_goto(
                "https://hk.jobsdb.com/jobs?keywords=data%20analyst",
                timeout=60000
            )

            if success:
                # 等待 Cloudflare 验证
                cf_passed = await browser.wait_for_cloudflare(max_wait=30)
                if cf_passed:
                    print("   ✅ Cloudflare 验证通过")
                else:
                    print("   ⚠️ Cloudflare 验证超时，继续尝试...")

                await asyncio.sleep(3)
                cards = await page.query_selector_all("article")
                if len(cards) > 0:
                    print(f"   ✅ JobsDB 通过！找到 {len(cards)} 个职位卡片")
                else:
                    content = await page.content()
                    if "Checking your browser" in content or "cloudflare" in content.lower():
                        print("   ❌ JobsDB 被 Cloudflare 拦截")
                    else:
                        print("   ⚠️ 页面加载但没找到职位卡片")
            else:
                print("   ❌ 页面加载失败")

            await page.screenshot(path="test_jobsdb_stealth.png")
            print("   📸 截图: test_jobsdb_stealth.png")

        except Exception as e:
            print(f"   ❌ JobsDB 测试失败: {e}")

        # 测试 2: Indeed HK
        print("\n📍 测试 2: Indeed HK (hk.indeed.com)")
        try:
            success = await browser.human_goto(
                "https://hk.indeed.com/jobs?q=data+analyst",
                timeout=60000
            )

            if success:
                await asyncio.sleep(5)
                cards = await page.query_selector_all("div.job_seen_beacon, div.jobsearch-ResultsList > div, div.jobCard")
                if len(cards) > 0:
                    print(f"   ✅ Indeed 通过！找到 {len(cards)} 个职位卡片")
                else:
                    content = await page.content()
                    if "blocked" in content.lower() or "captcha" in content.lower() or "verify" in content.lower():
                        print("   ❌ Indeed 被拦截")
                    else:
                        print("   ⚠️ 页面加载但没找到职位卡片")
            else:
                print("   ❌ 页面加载失败")

            await page.screenshot(path="test_indeed_stealth.png")
            print("   📸 截图: test_indeed_stealth.png")

        except Exception as e:
            print(f"   ❌ Indeed 测试失败: {e}")

        print("\n" + "=" * 50)
        print("🧪 测试完成！查看截图确认结果")
        print("⏳ 浏览器将在 15 秒后关闭...")
        await asyncio.sleep(15)

    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_antibot())
