#!/usr/bin/env python3
"""
测试 Indeed JSON 提取模式
"""

import asyncio
import logging
from core.indeed_bot import IndeedScraper

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def test_indeed_scraper():
    """测试 Indeed 爬虫"""
    print("=" * 60)
    print("🧪 测试 Indeed JSON 提取模式")
    print("=" * 60)

    scraper = IndeedScraper(
        user_id="test_user",
        country="hk",
        headless=True,  # 测试 headless 模式
    )

    try:
        # 测试 1: 单页搜索
        print("\n📍 测试 1: 单页搜索 (data analyst)")
        jobs = await scraper.search_jobs(
            keyword="data analyst",
            location="Hong Kong",
            page=1
        )

        print(f"✅ 找到 {len(jobs)} 个职位")

        if jobs:
            print("\n前 3 个职位:")
            for i, job in enumerate(jobs[:3]):
                print(f"  {i+1}. {job.title}")
                print(f"     公司: {job.company}")
                print(f"     地点: {job.location}")
                print(f"     薪资: {job.salary_range or 'N/A'}")
                print(f"     链接: {job.job_url}")
                print()

        # 测试 2: 获取 JD
        if jobs:
            print("\n📍 测试 2: 获取第一个职位的 JD")
            first_job = jobs[0]
            jd = await scraper.get_job_details(first_job.job_url)

            if jd:
                print(f"✅ JD 长度: {len(jd)} 字符")
                print(f"JD 预览:\n{jd[:500]}...")
            else:
                print("❌ 未能获取 JD")

        print("\n" + "=" * 60)
        print("🎉 测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(test_indeed_scraper())
