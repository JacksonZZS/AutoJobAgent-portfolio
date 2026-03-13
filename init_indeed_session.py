#!/usr/bin/env python3
"""
Indeed Session 初始化脚本（DrissionPage 版）
用途：手动完成一次人机验证，保存 Session 供后续爬取复用

使用方法：
    python init_indeed_session.py [country]

    country: hk, us, uk, ca, au, sg (默认 hk)
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

from DrissionPage import ChromiumPage, ChromiumOptions


# 支持的国家站点
INDEED_URLS = {
    "hk": "https://hk.indeed.com",
    "us": "https://www.indeed.com",
    "uk": "https://uk.indeed.com",
    "ca": "https://ca.indeed.com",
    "au": "https://au.indeed.com",
    "sg": "https://sg.indeed.com",
}


def init_indeed_session(country: str = "hk"):
    """初始化 Indeed Session"""

    print("=" * 60)
    print("🔐 Indeed Session 初始化 (DrissionPage)")
    print("=" * 60)
    print()

    # Profile 目录 - 与 indeed_dp.py 一致
    profile_dir = Path(__file__).parent / "chrome_profile" / f"indeed_dp_{country}"
    profile_dir.mkdir(parents=True, exist_ok=True)

    session_file = profile_dir / "session_status.json"

    print(f"📁 Profile 目录: {profile_dir}")
    print(f"🌍 目标站点: {INDEED_URLS.get(country, INDEED_URLS['hk'])}")
    print()

    # 配置浏览器
    co = ChromiumOptions()
    co.set_user_data_path(str(profile_dir))

    # 反检测配置
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--disable-infobars')
    co.set_argument('--window-size=1920,1080')
    co.set_argument('--window-position=100,100')  # 显示在屏幕上
    co.set_argument('--lang=en-US')
    co.set_argument('--no-proxy-server')  # 绕过 VPN

    # 真实 User-Agent
    co.set_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    print("🚀 启动浏览器...")
    page = ChromiumPage(co)

    # 注入反检测脚本
    try:
        page.run_js("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)
    except:
        pass

    # 访问 Indeed
    base_url = INDEED_URLS.get(country, INDEED_URLS['hk'])
    search_url = f"{base_url}/jobs?q=data+analyst"

    print(f"🌐 访问: {search_url}")
    page.get(search_url)

    print()
    print("=" * 60)
    print("⏳ 请在浏览器中完成以下操作：")
    print("=" * 60)
    print()
    print("  1. 如果出现 Cloudflare 验证，请手动点击完成")
    print("  2. 确认页面显示职位列表")
    print("  3. (可选) 登录你的 Indeed 账号")
    print()
    print("  完成后回到这里按 Enter 键保存 Session")
    print()

    input(">>> 验证完成后按 Enter: ")

    # 检查是否成功
    try:
        title = page.title.lower()

        if "just a moment" in title or "cloudflare" in title:
            print("❌ 验证似乎还没完成，请重试")
            page.quit()
            return False

        # 检查是否有职位卡片
        job_cards = page.eles('css:[data-jk]') or page.eles('css:.job_seen_beacon')

        if job_cards:
            print(f"✅ 检测到 {len(job_cards)} 个职位卡片，验证成功！")
        else:
            print("⚠️ 未检测到职位卡片，但可能是页面结构变化")

        # 保存 Session 状态
        status = {
            "last_verified": datetime.now().isoformat(),
            "country": country,
            "url": page.url,
            "title": page.title,
        }

        with open(session_file, 'w') as f:
            json.dump(status, f, indent=2)

        print()
        print("=" * 60)
        print("🎉 Session 已保存！")
        print("=" * 60)
        print()
        print(f"📁 保存位置: {session_file}")
        print(f"⏰ 有效期: 约 24-48 小时")
        print()
        print("现在可以运行爬虫了：")
        print(f"  python -c \"from core.indeed_dp import test_indeed_dp; test_indeed_dp()\"")
        print()

        # 保持浏览器打开一会儿
        time.sleep(2)
        page.quit()
        return True

    except Exception as e:
        print(f"❌ 保存 Session 失败: {e}")
        page.quit()
        return False


def check_session_status(country: str = "hk"):
    """检查 Session 状态"""
    profile_dir = Path(__file__).parent / "chrome_profile" / f"indeed_dp_{country}"
    session_file = profile_dir / "session_status.json"

    print(f"\n📋 检查 {country.upper()} Session 状态...")

    if not session_file.exists():
        print("❌ Session 文件不存在，需要初始化")
        return False

    try:
        with open(session_file, 'r') as f:
            status = json.load(f)

        last_verified = datetime.fromisoformat(status.get("last_verified", "2000-01-01"))
        hours_ago = (datetime.now() - last_verified).total_seconds() / 3600

        print(f"   上次验证: {last_verified.strftime('%Y-%m-%d %H:%M')}")
        print(f"   距今: {hours_ago:.1f} 小时")

        if hours_ago < 24:
            print("   ✅ Session 有效")
            return True
        else:
            print("   ⚠️ Session 可能已过期，建议重新初始化")
            return False

    except Exception as e:
        print(f"❌ 读取 Session 失败: {e}")
        return False


if __name__ == "__main__":
    # 获取国家参数
    country = sys.argv[1] if len(sys.argv) > 1 else "hk"

    if country not in INDEED_URLS:
        print(f"❌ 不支持的国家: {country}")
        print(f"   支持: {', '.join(INDEED_URLS.keys())}")
        sys.exit(1)

    # 先检查现有 Session
    if check_session_status(country):
        print()
        answer = input("Session 仍有效，是否重新初始化？(y/N): ")
        if answer.lower() != 'y':
            print("已取消")
            sys.exit(0)

    # 初始化
    print()
    success = init_indeed_session(country)
    sys.exit(0 if success else 1)
