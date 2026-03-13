"""
JobsDB 自动投递功能使用示例

这个示例展示了如何将自动投递功能集成到现有的 main.py 流程中
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime

from core.scraper import search_and_crawl_jobs
from core.pdf_parser import extract_text_from_pdf
from core.llm_engine import LLMEngine
from core.cv_renderer import generate_pdf_cv
from core.history_manager import HistoryManager
from core.apply_bot import JobsDBApplyBot, ApplyJobInfo


async def main_with_auto_apply():
    """
    集成了自动投递功能的主流程示例
    """
    print("🤖 === AutoJobAgent with Auto-Apply | AI 驱动全自动模式 ===")

    # 0. 初始化核心组件
    llm = LLMEngine()
    history = HistoryManager("data/history/processed_jobs.json")

    # 1. 加载简历资料
    resume_path = "data/inputs/my_resume.pdf"
    transcript_path = "data/inputs/transcript.pdf"

    resume_text = extract_text_from_pdf(resume_path)
    transcript_text = extract_text_from_pdf(transcript_path)

    # 构建候选人画像
    candidate_profile = {
        "resume_text": resume_text + "\n" + transcript_text,
        "name": "Your Name",  # 从简历中提取或手动设置
    }

    # 2. AI 生成搜索策略
    strategy = llm.generate_search_strategy(resume_text, transcript_text)
    search_queries = strategy["keywords"]
    search_blacklist = strategy.get("blacklist", [])

    print(f"✅ AI 搜索词: {search_queries}")
    print(f"🚫 排除关键词: {search_blacklist}")

    # 3. 搜索并评分职位
    high_score_jobs = []

    for keyword in search_queries[:3]:  # 限制搜索次数以便测试
        print(f"\n🔍 搜索关键词: {keyword}")

        jobs = await search_and_crawl_jobs(
            keyword=keyword,
            max_count=5,  # 每次搜索 5 个职位
            blacklist=search_blacklist
        )

        for job in jobs:
            # 跳过已处理的职位
            if history.is_processed(job['link']):
                continue

            # AI 匹配评分
            match_result = llm.check_match_score(
                resume_text=candidate_profile["resume_text"],
                jd_text=job['jd_content']
            )

            if match_result and match_result.get("score", 0) >= 70:
                score = match_result["score"]
                print(f"   ✨ 发现高分职位 ({score}分): {job['title']} @ {job['company']}")

                # 生成定制简历
                cv_data = llm.generate_resume_data(
                    resume_text=resume_text,
                    transcript_text=transcript_text,
                    jd_text=job['jd_content']
                )

                if cv_data:
                    # 生成 PDF
                    filename = f"[{score}分]_{job['company']}_{job['title']}_{datetime.now().strftime('%m%d')}.pdf"
                    cv_path = f"data/outputs/{filename}"
                    await generate_pdf_cv(cv_data, cv_path)

                    # 记录到高分职位列表
                    high_score_jobs.append({
                        "job_id": job.get("id", job["link"]),
                        "title": job["title"],
                        "company": job["company"],
                        "location": job.get("location", "Hong Kong"),
                        "job_url": job["link"],
                        "jd_text": job["jd_content"],
                        "score": score,
                        "cv_path": cv_path,
                        "match_analysis": match_result
                    })

                    # 记录历史
                    history.add_job(job['link'], job['title'], job['company'], status=f"GENERATED_{score}")

        await asyncio.sleep(2)  # 避免过于频繁的请求

    # 4. 自动投递高分职位
    if high_score_jobs:
        print(f"\n📨 准备投递 {len(high_score_jobs)} 个高分职位...")

        # 转换为 ApplyJobInfo 列表
        apply_jobs = []
        for job_data in high_score_jobs:
            apply_jobs.append(ApplyJobInfo(
                job_id=job_data["job_id"],
                title=job_data["title"],
                company=job_data["company"],
                location=job_data["location"],
                job_url=job_data["job_url"],
                jd_text=job_data["jd_text"],
                score=job_data["score"],
                match_analysis=job_data["match_analysis"]
            ))

        # 初始化自动投递机器人
        with JobsDBApplyBot(
            llm_engine=llm,
            cv_path=None,  # 每个职位使用不同的 CV，在 apply_to_job 中单独设置
            headless=False,  # 显示浏览器，便于调试
            allow_manual_captcha=True,  # 允许手动处理验证码
            captcha_timeout=300  # 验证码处理超时 5 分钟
        ) as bot:

            results = []

            # 逐个投递（因为每个职位有不同的 CV）
            for i, job in enumerate(apply_jobs, 1):
                print(f"\n[{i}/{len(apply_jobs)}] 投递职位: {job.title} @ {job.company}")

                # 设置当前职位的 CV
                bot.cv_path = high_score_jobs[i-1]["cv_path"]

                # 执行投递
                result = bot.apply_to_job(job, candidate_profile)
                results.append(result)

                # 更新历史记录
                if result.status.value == "success":
                    history.add_job(
                        job.job_url,
                        job.title,
                        job.company,
                        status=f"APPLIED_{job.score}"
                    )
                    print(f"   ✅ 投递成功")
                elif result.status.value == "already_applied":
                    print(f"   ℹ️ 已投递过")
                else:
                    print(f"   ❌ 投递失败: {result.message}")

                # 延迟，避免被检测
                if i < len(apply_jobs):
                    await asyncio.sleep(5)

            # 汇总结果
            success_count = sum(1 for r in results if r.status.value == "success")
            already_count = sum(1 for r in results if r.status.value == "already_applied")
            failed_count = sum(1 for r in results if r.status.value == "failed")

            print("\n" + "="*50)
            print("📊 投递结果汇总:")
            print(f"   ✅ 成功投递: {success_count}")
            print(f"   ℹ️ 已投递过: {already_count}")
            print(f"   ❌ 投递失败: {failed_count}")
            print("="*50)
    else:
        print("\n⚠️ 没有找到符合条件的高分职位")

    print("\n🎉 任务完成！")


if __name__ == "__main__":
    try:
        asyncio.run(main_with_auto_apply())
    except KeyboardInterrupt:
        print("\n🛑 任务已由用户手动停止。")
    except Exception as e:
        print(f"❌ 运行过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
