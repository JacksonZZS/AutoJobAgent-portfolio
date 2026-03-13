#!/usr/bin/env python3
"""
LinkedIn 爬虫视觉测试 - 使用 RealTester 验证功能
"""

import sys
import json
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.linkedin_dp import LinkedInDPScraper

def test_linkedin_scraper():
    """测试 LinkedIn 职位爬取"""

    print("=" * 60)
    print("🧪 LinkedIn 爬虫视觉测试")
    print("=" * 60)

    # 测试结果
    result = {
        "status": "unknown",
        "detected_issues": [],
        "screenshots": [],
        "jobs_found": [],
        "page_state": {},
        "suggested_fix": None
    }

    scraper = None

    try:
        # 1. 初始化爬虫
        print("\n📦 初始化爬虫...")
        scraper = LinkedInDPScraper(
            user_id="test_user",
            headless=False,  # 可见模式，方便调试
            cookies_file=str(Path(__file__).parent.parent / "linkedin_cookies.json")
        )

        # 2. 创建浏览器
        print("🚀 启动浏览器...")
        scraper._create_page()
        time.sleep(2)

        # 截图
        screenshot_path = "/tmp/visual_test/linkedin_01_browser_started.png"
        Path("/tmp/visual_test").mkdir(exist_ok=True)
        scraper.page.get_screenshot(path=screenshot_path)
        result["screenshots"].append(screenshot_path)
        print(f"  📸 截图: {screenshot_path}")

        # 3. 加载 Cookies
        print("\n🍪 加载 Cookies...")
        cookies_loaded = scraper._load_cookies()

        if not cookies_loaded:
            result["detected_issues"].append("Cookie 加载失败")
            result["suggested_fix"] = "检查 linkedin_cookies.json 是否存在且有效"

        # 截图
        screenshot_path = "/tmp/visual_test/linkedin_02_after_cookies.png"
        scraper.page.get_screenshot(path=screenshot_path)
        result["screenshots"].append(screenshot_path)
        print(f"  📸 截图: {screenshot_path}")

        # 4. 检查登录状态
        print("\n🔐 检查登录状态...")
        current_url = scraper.page.url
        result["page_state"]["url"] = current_url
        result["page_state"]["title"] = scraper.page.title

        if scraper._check_login_required():
            result["detected_issues"].append("需要登录 - Cookie 可能过期")
            result["status"] = "failed"
            result["suggested_fix"] = "重新导出 LinkedIn cookies 并更新 linkedin_cookies.json"

            # 截图登录页
            screenshot_path = "/tmp/visual_test/linkedin_03_login_required.png"
            scraper.page.get_screenshot(path=screenshot_path)
            result["screenshots"].append(screenshot_path)

            print(f"  ❌ 需要登录，Cookie 可能过期")
            print(f"  📸 截图: {screenshot_path}")
        else:
            print(f"  ✅ 已登录")

            # 5. 搜索职位
            print("\n🔍 搜索职位: Data Analyst, Hong Kong...")
            jobs = scraper.search_jobs(
                keyword="Data Analyst",
                location="Hong Kong",
                max_jobs=5,  # 只取5个测试
                easy_apply_only=False
            )

            # 截图搜索结果
            screenshot_path = "/tmp/visual_test/linkedin_04_search_results.png"
            scraper.page.get_screenshot(path=screenshot_path)
            result["screenshots"].append(screenshot_path)
            print(f"  📸 截图: {screenshot_path}")

            if jobs:
                print(f"\n✅ 找到 {len(jobs)} 个职位:")
                for i, job in enumerate(jobs[:5], 1):
                    print(f"  {i}. {job.title} @ {job.company}")
                    print(f"     📍 {job.location}")
                    print(f"     🔗 {job.job_url}")
                    result["jobs_found"].append({
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "url": job.job_url,
                        "easy_apply": job.is_easy_apply
                    })

                result["status"] = "success"
            else:
                result["detected_issues"].append("未找到职位")
                result["status"] = "failed"
                result["suggested_fix"] = "检查搜索选择器是否需要更新"

    except Exception as e:
        result["status"] = "error"
        result["detected_issues"].append(f"异常: {str(e)}")
        result["suggested_fix"] = f"检查错误: {str(e)}"
        print(f"\n❌ 错误: {e}")

        # 尝试截图
        try:
            if scraper and scraper.page:
                screenshot_path = "/tmp/visual_test/linkedin_error.png"
                scraper.page.get_screenshot(path=screenshot_path)
                result["screenshots"].append(screenshot_path)
        except:
            pass

    finally:
        # 关闭浏览器
        if scraper and scraper.page:
            try:
                scraper.page.quit()
            except:
                pass

    # 保存结果
    result_path = "/tmp/visual_test/linkedin_test_result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"📊 测试结果: {result['status'].upper()}")
    print(f"💾 结果保存: {result_path}")

    if result["detected_issues"]:
        print(f"\n🔍 检测到的问题:")
        for issue in result["detected_issues"]:
            print(f"  • {issue}")

    if result["suggested_fix"]:
        print(f"\n💡 建议修复: {result['suggested_fix']}")

    print("=" * 60)

    return result


if __name__ == "__main__":
    test_linkedin_scraper()
