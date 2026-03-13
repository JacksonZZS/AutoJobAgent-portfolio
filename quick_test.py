#!/usr/bin/env python3
"""
Quick Test - 验证 PDF 生成修复
"""

import sys
import os
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 60)
    logger.info("🧪 测试 ReportLab PDF 生成")
    logger.info("=" * 60)

    try:
        from core.apply_bot import JobsDBApplyBot, ApplyJobInfo
        from core.llm_engine import LLMEngine
        from core.status_manager import get_status_manager

        user_id = "6"
        test_resume_path = "data/uploads/1d6c1fc3_resume.pdf"

        logger.info(f"📋 初始化组件...")
        llm_engine = LLMEngine()
        status_manager = get_status_manager(user_id=user_id)

        logger.info(f"🤖 初始化 Bot...")
        bot = JobsDBApplyBot(
            user_id=user_id,
            llm_engine=llm_engine,
            headless=True,
            cv_path=test_resume_path,
            keywords=["Python Developer"],
            limit=1,
            status_manager=status_manager
        )

        logger.info("✅ Bot 初始化成功")

        logger.info("🚀 启动浏览器...")
        bot.start()
        logger.info("✅ 浏览器启动成功")

        test_job = ApplyJobInfo(
            job_id="test_002",
            title="Senior Python Engineer",
            company="Tech Innovations Inc",
            location="Hong Kong",
            job_url="https://hk.jobsdb.com/job/test-002",
            jd_text="Looking for a senior Python engineer with 5+ years experience in backend development, microservices, and cloud platforms..."
        )

        candidate_profile = {
            "resume_text": "Experienced Python developer with 6 years in backend development, specializing in Django, FastAPI, and AWS cloud services...",
            "name": "Test User"
        }

        logger.info("🚀 测试投递流程...")
        logger.info(f"   职位: {test_job.title}")
        logger.info(f"   公司: {test_job.company}")

        result = bot.apply_to_job(
            job_info=test_job,
            candidate_profile=candidate_profile
        )

        logger.info("=" * 60)
        logger.info("📊 测试结果:")
        logger.info(f"   状态: {result.status.value}")
        logger.info(f"   消息: {result.message}")
        logger.info("=" * 60)

        # 检查生成的文件
        output_dir = Path("data/outputs/testuser/Tech_Innovations_Inc_Senior_Python_Engineer")
        if output_dir.exists():
            files = list(output_dir.glob("*.pdf"))
            logger.info(f"✅ 生成了 {len(files)} 个 PDF 文件:")
            for f in files:
                size = f.stat().st_size
                logger.info(f"   - {f.name} ({size} bytes)")

        bot.close()
        logger.info("✅ 测试完成！")

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
