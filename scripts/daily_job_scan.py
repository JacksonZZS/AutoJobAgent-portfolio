#!/usr/bin/env python3
"""
每日职位扫描脚本
- 自动爬取 Indeed/LinkedIn 职位
- 匹配用户简历评分
- 高分职位发送邮件通知

使用方式：
1. 直接运行：python3 scripts/daily_job_scan.py
2. 配合 macOS launchd 定时运行
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


async def load_user_config():
    """加载用户配置（搜索关键词、邮件偏好等）"""
    config_path = PROJECT_ROOT / "data" / "daily_scan_config.json"

    if not config_path.exists():
        # 默认配置
        default_config = {
            "enabled": True,
            "keywords": ["software engineer", "frontend developer", "python developer"],
            "location": "Hong Kong",
            "platforms": ["indeed"],  # indeed, linkedin
            "min_match_score": 80,
            "email_notify": True,
            "max_jobs_per_scan": 20
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(default_config, indent=2, ensure_ascii=False))
        return default_config

    return json.loads(config_path.read_text())


async def scrape_jobs(config: dict) -> list:
    """爬取职位"""
    from core.indeed_dp import IndeedScraper

    jobs = []

    if "indeed" in config.get("platforms", []):
        print(f"[{datetime.now()}] 开始爬取 Indeed...")
        try:
            scraper = IndeedScraper()
            for keyword in config.get("keywords", []):
                print(f"  搜索关键词: {keyword}")
                result = await scraper.search_jobs(
                    keyword=keyword,
                    location=config.get("location", ""),
                    max_results=config.get("max_jobs_per_scan", 20)
                )
                jobs.extend(result)
        except Exception as e:
            print(f"  Indeed 爬取失败: {e}")

    print(f"[{datetime.now()}] 共爬取 {len(jobs)} 个职位")
    return jobs


async def match_and_score(jobs: list, config: dict) -> list:
    """匹配简历并评分"""
    from core.resume_generator import analyze_job_match

    scored_jobs = []
    min_score = config.get("min_match_score", 80)

    print(f"[{datetime.now()}] 开始匹配评分（最低分数: {min_score}）...")

    for job in jobs:
        try:
            # 获取默认简历
            resume_path = PROJECT_ROOT / "data" / "uploads" / "default_resume.pdf"
            if not resume_path.exists():
                # 尝试找任意简历
                uploads_dir = PROJECT_ROOT / "data" / "uploads"
                if uploads_dir.exists():
                    pdf_files = list(uploads_dir.glob("**/*.pdf"))
                    if pdf_files:
                        resume_path = pdf_files[0]

            if resume_path.exists():
                score = await analyze_job_match(str(resume_path), job.get("description", ""))
                job["match_score"] = score

                if score >= min_score:
                    scored_jobs.append(job)
                    print(f"  ✓ {job.get('title', 'Unknown')} @ {job.get('company', 'Unknown')} - {score}分")
        except Exception as e:
            print(f"  评分失败: {e}")

    print(f"[{datetime.now()}] 高分职位: {len(scored_jobs)} 个")
    return scored_jobs


async def send_notification(jobs: list, config: dict):
    """发送邮件通知"""
    if not config.get("email_notify", True) or not jobs:
        print(f"[{datetime.now()}] 跳过邮件通知（无高分职位或未启用）")
        return

    print(f"[{datetime.now()}] 发送邮件通知...")

    try:
        from backend.services.email_service import send_job_alert_email

        await send_job_alert_email(
            jobs=jobs,
            min_score=config.get("min_match_score", 80)
        )
        print(f"[{datetime.now()}] ✓ 邮件发送成功")
    except Exception as e:
        print(f"[{datetime.now()}] ✗ 邮件发送失败: {e}")


async def save_scan_result(jobs: list):
    """保存扫描结果"""
    result_path = PROJECT_ROOT / "data" / "scan_results" / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "scan_time": datetime.now().isoformat(),
        "total_jobs": len(jobs),
        "jobs": jobs
    }

    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"[{datetime.now()}] 结果保存到: {result_path}")


async def main():
    """主函数"""
    print("=" * 60)
    print(f"AutoJobAgent 每日职位扫描")
    print(f"开始时间: {datetime.now()}")
    print("=" * 60)

    # 1. 加载配置
    config = await load_user_config()

    if not config.get("enabled", True):
        print("每日扫描已禁用，退出")
        return

    # 2. 爬取职位
    jobs = await scrape_jobs(config)

    if not jobs:
        print("没有爬取到职位，退出")
        return

    # 3. 匹配评分
    high_score_jobs = await match_and_score(jobs, config)

    # 4. 保存结果
    await save_scan_result(high_score_jobs)

    # 5. 发送通知
    await send_notification(high_score_jobs, config)

    print("=" * 60)
    print(f"扫描完成: {datetime.now()}")
    print(f"高分职位: {len(high_score_jobs)} 个")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
