#!/usr/bin/env python3
"""
测试 JobsDB 页面结构，诊断为什么搜不到职位
"""
import asyncio
from playwright.async_api import async_playwright

async def test_jobsdb():
    keyword = "Data Scientist"
    url = f"https://hk.jobsdb.com/jobs?keywords={keyword.replace(' ', '%20')}"

    print(f"🔍 测试 URL: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 显示浏览器
        page = await browser.new_page()

        try:
            print("📄 加载页面...")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)  # 等待页面完全加载

            # 检查页面标题
            title = await page.title()
            print(f"📌 页面标题: {title}")

            # 检查是否被反爬拦截
            content = await page.content()
            if "captcha" in content.lower() or "blocked" in content.lower():
                print("❌ 被反爬拦截了！")
            elif "cloudflare" in content.lower():
                print("❌ Cloudflare 拦截！")
            else:
                print("✅ 没有检测到反爬拦截")

            # 测试各种选择器
            selectors_to_test = [
                ("article", "article 标签"),
                ('[data-automation="jobTitle"]', 'data-automation="jobTitle"'),
                ('[data-testid="job-card"]', 'data-testid="job-card"'),
                ('[class*="job"]', 'class 包含 job'),
                ('h1 a', 'h1 a 链接'),
                ('[data-search-sol-meta]', 'data-search-sol-meta'),
            ]

            print("\n🔎 测试选择器:")
            for selector, desc in selectors_to_test:
                try:
                    elements = await page.query_selector_all(selector)
                    count = len(elements)
                    if count > 0:
                        print(f"   ✅ {desc}: 找到 {count} 个")
                    else:
                        print(f"   ❌ {desc}: 0 个")
                except Exception as e:
                    print(f"   ⚠️ {desc}: 错误 - {e}")

            # 打印页面 HTML 片段帮助调试
            print("\n📋 页面结构预览 (前 2000 字符):")
            print(content[:2000])

            # 截图保存
            await page.screenshot(path="jobsdb_debug.png")
            print("\n📸 截图已保存: jobsdb_debug.png")

            print("\n🏁 测试完成，3秒后关闭浏览器...")
            await asyncio.sleep(3)

        except Exception as e:
            print(f"❌ 错误: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_jobsdb())
