#!/usr/bin/env python3
"""
Indeed 登录脚本
打开浏览器让用户手动登录，保存 Cookie 供后续使用
"""

import asyncio
import nodriver as uc
from pathlib import Path

PROFILE_DIR = Path.home() / ".nodriver_profile"


async def init_indeed_login():
    """打开 Indeed 登录页面，等待用户手动登录"""
    print("=" * 60)
    print("🔐 Indeed 登录初始化")
    print("=" * 60)
    print()
    print("📌 说明:")
    print("  1. 浏览器会打开 Indeed 登录页面")
    print("  2. 请手动登录你的 Indeed 账号")
    print("  3. 登录成功后，回到这里按 Enter 继续")
    print("  4. Cookie 会保存到:", PROFILE_DIR)
    print()

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    config = uc.Config()
    config.headless = False
    config.user_data_dir = str(PROFILE_DIR)

    browser = await uc.start(config)

    # 先等浏览器启动
    await asyncio.sleep(2)

    # 打开 Indeed 登录页
    print("🌐 正在打开 Indeed 登录页...")
    page = await browser.get("https://secure.indeed.com/account/login")

    # 等待页面加载
    await asyncio.sleep(3)

    print("✅ 浏览器已打开！")
    print()
    print("⏳ 请在浏览器中登录 Indeed...")
    print("   登录完成后，回到这里按 Enter 键")
    print()

    # 等待用户输入
    input(">>> 登录完成后按 Enter: ")

    # 检查登录状态
    try:
        current_url = await page.evaluate("window.location.href")
        print(f"当前页面: {current_url}")
    except:
        pass

    # 尝试访问 Indeed 首页确认登录状态
    print("🔍 检查登录状态...")
    page = await browser.get("https://hk.indeed.com")
    await asyncio.sleep(3)

    # 检查是否有登录指示器
    try:
        is_logged_in = await page.evaluate("""
            (function() {
                const profileBtn = document.querySelector('[data-gnav-element-name="ProfileButton"]');
                const accountBtn = document.querySelector('[data-gnav-element-name="Account"]');
                const signedIn = document.body.innerText.includes('Sign Out') ||
                                 document.body.innerText.includes('My jobs');
                return !!(profileBtn || accountBtn || signedIn);
            })()
        """)

        if is_logged_in:
            print("✅ 登录成功！Cookie 已保存")
        else:
            print("⚠️ 无法确认登录状态，但 Cookie 应该已保存")
    except:
        print("⚠️ 检查登录状态时出错，但 Cookie 应该已保存")

    print()
    print("🎉 完成！现在可以运行测试脚本了:")
    print("   python test_indeed_json.py")
    print()

    browser.stop()


if __name__ == "__main__":
    asyncio.run(init_indeed_login())
