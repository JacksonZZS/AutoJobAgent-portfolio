#!/usr/bin/env python3
"""
Indeed 爬虫快速测试脚本
"""
import asyncio
from core.indeed_bot import IndeedScraper, search_indeed_jobs

async def test_indeed():
    print("🚀 测试 Indeed 爬虫...")

    # 测试参数
    keyword = "data analyst"
    country = "hk"  # 香港站点
    user_id = "test_user"

    print(f"📍 搜索关键词: {keyword}")
    print(f"🌍 站点: Indeed {country.upper()}")

    # 方式1: 使用便捷函数
    jobs = await search_indeed_jobs(
        keyword=keyword,
        user_id=user_id,
        location=None,
        country=country,
        max_pages=1,  # 只爬1页测试
        headless=False,  # 显示浏览器方便调试
    )

    print(f"\n✅ 找到 {len(jobs)} 个职位:")
    for i, job in enumerate(jobs[:5], 1):  # 只显示前5个
        print(f"\n--- 职位 {i} ---")
        print(f"标题: {job.title}")
        print(f"公司: {job.company}")
        print(f"地点: {job.location}")
        print(f"链接: {job.job_url}")
        print(f"Easy Apply: {job.is_easy_apply}")

if __name__ == "__main__":
    asyncio.run(test_indeed())
