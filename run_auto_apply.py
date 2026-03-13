#!/usr/bin/env python3
"""
AutoJobAgent - 自动投递主程序
目标驱动的流式投递循环

核心逻辑：
1. 外层循环：while success_count < limit
2. 内层循环：遍历关键词列表
3. 对每个关键词：抓取一页 → 逐个处理（读取JD → LLM评分 → 投递）→ 翻页
4. 达到目标立即退出

使用方法:
    python run_auto_apply.py --resume_path data/inputs/my_resume.pdf --keywords "Python Developer" --limit 5
"""

import sys
import os
import asyncio
import nest_asyncio

# 允许嵌套的 asyncio 事件循环，解决 Playwright Sync API 与 asyncio 的冲突
nest_asyncio.apply()
import os
import sys
import argparse
import logging
import signal
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from core.scraper import search_and_crawl_jobs
from core.pdf_parser import extract_text_from_pdf
from core.llm_engine import LLMEngine
from core.cv_renderer import generate_pdf_cv
from core.history_manager import HistoryManager
from core.apply_bot import JobsDBApplyBot, ApplyJobInfo
from core.status_manager import get_status_manager, TaskStatus
from core.resume_language_processor import ResumeLanguageProcessor  # 🔴 新增：多语言处理

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data/logs/auto_apply.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


class StreamingScraper:
    """
    流式爬虫适配器
    将异步爬虫适配为同步的分页接口
    """

    def __init__(self, user_id: str, blacklist: List[str] = None, title_exclusions: List[str] = None):
        self.user_id = user_id
        self.blacklist = blacklist or []
        self.title_exclusions = title_exclusions or []

    def fetch_page(self, keyword: str, page: int, page_size: int) -> List[Dict[str, Any]]:
        """
        抓取指定关键词的指定页

        Args:
            keyword: 搜索关键词
            page: 页码（从1开始）
            page_size: 每页数量

        Returns:
            职位列表
        """
        logger.info(f"🔍 抓取关键词 '{keyword}' 第 {page} 页 (每页上限 {page_size} 个)...")
        # 🔴 [DEBUG] 验证参数传递
        logger.debug(f"   [DEBUG] 传入爬虫的参数: max_count={page_size}")

        try:
            # 调用异步爬虫
            jobs = asyncio.run(search_and_crawl_jobs(
                keyword=keyword,
                max_count=page_size,  # 🔴 传递 page_size 作为每页抓取上限
                blacklist=self.blacklist,
                title_exclusions=self.title_exclusions,
                start_page=page,
                user_id=self.user_id
            ))

            # 🔴 [DEBUG] 显示抓取结果
            logger.info(f"   ✅ 本页抓取完成: 实际获得 {len(jobs)} 个职位")
            if len(jobs) < page_size:
                logger.info(f"   ℹ️  注意: 本页职位数量 ({len(jobs)}) 少于上限 ({page_size})，可能已抓取本页所有符合条件的职位")

            return jobs

        except Exception as e:
            logger.error(f"抓取失败: {e}")
            return []


def main_auto_apply(
    resume_path: str,
    keywords: str,
    user_id: str = "default",  # 🔴 新增：用户 ID 参数
    block_list: str = "",
    title_exclusions: str = "",
    transcript_path: str = None,
    limit: int = 10,
    headless: bool = False,
    delay: float = 5.0,
    page_size: int = 200  # 🔴 [修复] 提高默认值，抓取整页职位
):
    """
    目标驱动的自动投递主流程（支持多用户数据隔离）

    Args:
        resume_path: 简历 PDF 路径
        keywords: 搜索关键词（逗号分隔）
        user_id: 用户 ID，用于多用户数据隔离（必需）
        block_list: 公司黑名单（逗号分隔）
        title_exclusions: 职位排除词（逗号分隔）
        transcript_path: 成绩单 PDF 路径（可选）
        limit: 目标成功投递数量
        headless: 是否无头模式
        delay: 投递延迟（秒）
        page_size: 每页抓取数量
    """
    # 🔴 获取用户专属的状态管理器
    status_mgr = get_status_manager(user_id=user_id)

    # 🔴 [新增] 清理旧的 lock_file（防止重启后残留）
    from pathlib import Path
    lock_file = Path(f"data/locks/user_interaction_{user_id}.lock")
    if lock_file.exists():
        try:
            lock_file.unlink()
            logger.info(f"🧹 清理旧的 lock_file: {lock_file}")
        except Exception as e:
            logger.warning(f"⚠️ 清理 lock_file 失败: {e}")

    # 🔴 方案1：程序启动时自动检查并清理过期状态
    logger.info("🔍 检查是否存在过期状态...")
    was_cleaned = status_mgr.check_and_clean_stale_status(max_age_minutes=10)
    if was_cleaned:
        logger.info("✅ 已清理上次中断时的旧状态")
    else:
        logger.info("✅ 状态正常，继续执行")
        # 如果状态不是过期的，但也不是 IDLE/COMPLETED，则重置
        current = status_mgr.read_status()
        if current.get("status") not in ["idle", "completed"]:
            logger.warning("⚠️ 检测到未完成的任务状态，重置为初始状态")
            status_mgr.reset()

    status_mgr.update(
        status=TaskStatus.INITIALIZING,
        message="正在初始化系统...",
        progress=5,
        step="initialization"
    )

    logger.info("=" * 80)
    logger.info("🤖 AutoJobAgent - 目标驱动自动投递系统（多用户版）")
    logger.info(f"👤 用户 ID: {user_id}")
    logger.info("=" * 80)

    # 确保日志目录存在
    Path("data/logs").mkdir(parents=True, exist_ok=True)
    Path("data/outputs").mkdir(parents=True, exist_ok=True)

    # 1. 验证文件存在
    status_mgr.update(
        status=TaskStatus.INITIALIZING,
        message="正在验证文件...",
        progress=10,
        step="file_validation"
    )

    if not os.path.exists(resume_path):
        logger.error(f"❌ 简历文件不存在: {resume_path}")
        status_mgr.set_error(f"简历文件不存在: {resume_path}")
        return

    if transcript_path and not os.path.exists(transcript_path):
        logger.error(f"❌ 成绩单文件不存在: {transcript_path}")
        status_mgr.set_error(f"成绩单文件不存在: {transcript_path}")
        return

    # 2. 解析参数
    search_queries = [k.strip() for k in keywords.split(",") if k.strip()]
    blocked_companies = [b.strip() for b in block_list.split(",") if b.strip()]
    excluded_titles = [t.strip() for t in title_exclusions.split(",") if t.strip()]

    logger.info(f"📋 配置信息:")
    logger.info(f"   简历: {resume_path}")
    if transcript_path:
        logger.info(f"   成绩单: {transcript_path}")
    logger.info(f"   目标投递数: {limit}")
    logger.info(f"   搜索关键词: {search_queries}")
    logger.info(f"   黑名单公司: {blocked_companies if blocked_companies else '无'}")
    logger.info(f"   排除职位词: {excluded_titles if excluded_titles else '无'}")
    logger.info(f"   无头模式: {headless}")
    logger.info(f"   投递延迟: {delay}s")
    logger.info(f"   每页抓取: {page_size} 个")

    # 3. 加载简历文本
    logger.info("\n📄 正在解析简历...")
    status_mgr.update(
        status=TaskStatus.INITIALIZING,
        message="正在解析简历文件...",
        progress=15,
        step="resume_parsing"
    )

    try:
        resume_text = extract_text_from_pdf(resume_path)
        logger.info(f"   ✅ 简历解析成功 (长度: {len(resume_text)} 字符)")
    except Exception as e:
        logger.error(f"   ❌ 简历解析失败: {e}")
        status_mgr.set_error(f"简历解析失败: {e}")
        return

    # 4. 初始化 LLM 引擎（提前初始化，用于成绩单清洗）
    logger.info("\n🧠 正在初始化 AI 引擎...")
    status_mgr.update(
        status=TaskStatus.INITIALIZING,
        message="正在初始化 AI 引擎...",
        progress=20,
        step="llm_initialization"
    )

    try:
        llm_engine = LLMEngine()
        logger.info("   ✅ AI 引擎初始化成功")
    except Exception as e:
        logger.error(f"   ❌ AI 引擎初始化失败: {e}")
        logger.warning("   ⚠️ 将在没有 AI 评分的情况下继续")
        llm_engine = None

    # 🔴 新增：多语言简历处理
    logger.info("\n🌐 正在进行多语言简历处理...")
    status_mgr.update(
        status=TaskStatus.INITIALIZING,
        message="正在检测简历语言并处理...",
        progress=22,
        step="language_processing"
    )

    resume_language_data = {}
    if llm_engine:
        try:
            language_processor = ResumeLanguageProcessor(llm_engine)
            resume_language_data = language_processor.process_resume(resume_text)

            logger.info(f"   ✅ 语言检测: {resume_language_data.get('resume_language', 'unknown')}")
            logger.info(f"   ✅ 置信度: {resume_language_data.get('language_confidence', 0):.2f}")

            if resume_language_data.get('translation_needed'):
                logger.info(f"   ✅ 已生成英文摘要 (长度: {len(resume_language_data.get('resume_en_summary', ''))} 字符)")
            else:
                logger.info("   ℹ️  简历已为英文，无需翻译")

        except Exception as e:
            logger.warning(f"   ⚠️ 多语言处理失败: {e}")
            logger.warning("   ⚠️ 将使用原始简历文本继续")
    else:
        logger.warning("   ⚠️ AI 引擎不可用，跳过多语言处理")

    # 5. 加载成绩单（如果有）
    transcript_text = ""
    clean_course_list = ""

    if transcript_path:
        logger.info("\n📄 正在解析成绩单...")
        status_mgr.update(
            status=TaskStatus.INITIALIZING,
            message="正在解析成绩单...",
            progress=25,
            step="transcript_parsing"
        )

        try:
            transcript_text = extract_text_from_pdf(transcript_path)
            logger.info(f"   ✅ 成绩单解析成功 (长度: {len(transcript_text)} 字符)")

            # 🔴 关键修改：使用 LLM 智能清洗成绩单，提取优选课程
            if llm_engine:
                logger.info("🧠 正在使用 AI 智能提取优选课程（B+ 或以上）...")
                status_mgr.update(
                    status=TaskStatus.INITIALIZING,
                    message="AI 正在提取优选课程...",
                    progress=30,
                    step="course_extraction"
                )
                clean_course_list = llm_engine.extract_top_courses(transcript_text)

                if clean_course_list:
                    logger.info(f"🎓 提取的优选课程: {clean_course_list}")
                else:
                    logger.warning("⚠️ 未能提取到符合条件的课程，将使用原始成绩单文本")
            else:
                logger.warning("⚠️ AI 引擎不可用，跳过成绩单清洗")

        except Exception as e:
            logger.warning(f"   ⚠️ 成绩单解析失败: {e}")

    # 6. 准备候选人资料
    # 🔴 关键修改：使用清洗后的课程列表，而不是原始成绩单文本
    # 🔴 新增：包含多语言处理数据
    # 🔴 [修复] 从简历中提取姓名，而不是从 profile 数据库读取
    # 这样求职信的姓名与简历上的姓名保持一致
    extracted_name = "Candidate"  # 默认占位符

    # 尝试从简历文本中提取姓名（简历顶部通常是姓名）
    try:
        # 简单提取：假设简历第一行或前几行包含姓名
        resume_lines = resume_text.strip().split('\n')[:5]  # 取前5行
        for line in resume_lines:
            line = line.strip()
            # 跳过空行和明显不是姓名的行（如包含 Email、Phone 等）
            if line and len(line) < 50 and not any(keyword in line.lower() for keyword in ['email', 'phone', 'tel', '@', 'http', 'www']):
                # 假设这是姓名行
                extracted_name = line
                break
    except Exception as e:
        logger.warning(f"⚠️ 从简历提取姓名失败: {e}，使用默认值")

    logger.info(f"📝 从简历提取的姓名: {extracted_name}")

    if clean_course_list:
        # 如果成功提取了优选课程，将其格式化后添加到简历文本
        coursework_section = f"\n\nRELEVANT COURSEWORK (High Distinction/A Grades):\n{clean_course_list}"
        candidate_profile = {
            "resume_text": resume_text + coursework_section,
            "transcript_text": transcript_text,  # 保留原始成绩单供其他用途
            "name": extracted_name,  # ✅ 使用从简历提取的姓名
            # 🔴 新增：多语言处理数据
            "resume_language": resume_language_data.get("resume_language", "unknown"),
            "language_confidence": resume_language_data.get("language_confidence", 0.0),
            "resume_en_summary": resume_language_data.get("resume_en_summary", ""),
            "skill_keywords": resume_language_data.get("skill_keywords", ""),
            "translation_needed": resume_language_data.get("translation_needed", False)
        }
        logger.info(f"✅ 已将优选课程添加到候选人资料（姓名: {extracted_name}）")
    else:
        # 如果没有成绩单或提取失败，只使用简历文本
        candidate_profile = {
            "resume_text": resume_text,
            "transcript_text": transcript_text if transcript_text else "",
            "name": extracted_name,  # ✅ 使用从简历提取的姓名
            # 🔴 新增：多语言处理数据
            "resume_language": resume_language_data.get("resume_language", "unknown"),
            "language_confidence": resume_language_data.get("language_confidence", 0.0),
            "resume_en_summary": resume_language_data.get("resume_en_summary", ""),
            "skill_keywords": resume_language_data.get("skill_keywords", ""),
            "translation_needed": resume_language_data.get("translation_needed", False)
        }
        logger.info(f"✅ 候选人资料已准备（姓名: {extracted_name}）")
        logger.info("ℹ️ 使用原始简历文本（无成绩单或提取失败）")

    # 7. 初始化流式爬虫
    logger.info("\n🕷️ 正在初始化爬虫...")
    status_mgr.update(
        status=TaskStatus.INITIALIZING,
        message="正在初始化爬虫...",
        progress=35,
        step="scraper_initialization"
    )

    # 🔴 创建流式爬虫（传入 user_id 确保历史记录隔离）
    scraper = StreamingScraper(
        user_id=user_id,
        blacklist=blocked_companies,
        title_exclusions=excluded_titles
    )

    # 8. 初始化投递机器人（不启动浏览器）
    logger.info("\n🤖 正在初始化投递机器人...")
    status_mgr.update(
        status=TaskStatus.INITIALIZING,
        message="正在初始化投递机器人...",
        progress=40,
        step="bot_initialization"
    )

    bot = None  # 初始化 bot 变量
    try:
        bot = JobsDBApplyBot(
            llm_engine=llm_engine,
            headless=headless,
            cv_path=resume_path,
            keywords=search_queries,
            limit=limit,
            status_manager=status_mgr,  # 传递用户专属的状态管理器
            user_id=user_id  # 🔴 新增：传递 user_id
        )
        logger.info("   ✅ 投递机器人初始化成功")
        logger.info("   ℹ️  浏览器将在找到匹配职位后按需启动（Lazy Initialization）")

        # 🔴 方案2：设置信号处理器（在 bot 初始化后）
        setup_signal_handlers(status_mgr, bot)
        logger.info("   ✅ 信号处理器已设置（Ctrl+C 将优雅退出）")

    except Exception as e:
        logger.error(f"   ❌ 投递机器人初始化失败: {e}")
        status_mgr.set_error(f"投递机器人初始化失败: {e}")
        return

    # 9. 执行流式投递（浏览器将在 apply_to_job 中按需启动）
    logger.info("\n" + "=" * 80)
    logger.info("🚀 开始执行目标驱动的流式投递循环")
    logger.info("=" * 80)

    status_mgr.update(
        status=TaskStatus.SCRAPING,
        message="开始搜索职位...",
        progress=45,
        step="job_search"
    )

    try:
        results = bot.stream_apply_with_target(
            scraper_func=scraper.fetch_page,
            candidate_profile=candidate_profile,
            delay_between_jobs=delay,
            block_list=blocked_companies,
            title_exclusions=excluded_titles,
            page_size=page_size
        )

        # 10. 输出结果
        logger.info("\n" + "=" * 80)
        logger.info("📊 投递结果汇总")
        logger.info("=" * 80)

        success_results = [r for r in results if r.status.value == "success"]
        failed_results = [r for r in results if r.status.value == "failed"]
        skipped_results = [r for r in results if r.status.value == "skipped"]

        logger.info(f"✅ 成功投递: {len(success_results)}")
        for r in success_results:
            logger.info(f"   • {r.job_info.title} @ {r.job_info.company}")

        if failed_results:
            logger.info(f"\n❌ 投递失败: {len(failed_results)}")
            for r in failed_results:
                logger.info(f"   • {r.job_info.title} @ {r.job_info.company} - {r.message}")

        if skipped_results:
            logger.info(f"\n🚫 已跳过: {len(skipped_results)}")
            for r in skipped_results[:5]:  # 只显示前5个
                logger.info(f"   • {r.job_info.title} @ {r.job_info.company} - {r.message}")
            if len(skipped_results) > 5:
                logger.info(f"   ... 还有 {len(skipped_results) - 5} 个")

        # 🔴 关键修复：根据实际投递数判断任务状态
        actual_success_count = len(success_results)
        target_reached = actual_success_count >= limit

        logger.info("\n" + "=" * 80)
        if target_reached:
            logger.info("🎉 任务完成！已达到目标投递数")
            logger.info("=" * 80)

            # 设置完成状态
            status_mgr.set_completed(
                f"✅ 任务完成！成功投递 {actual_success_count} 个职位（目标: {limit}）"
            )
        else:
            logger.warning("⚠️ 任务未完成：未达到目标投递数")
            logger.warning(f"   目标: {limit} 个，实际: {actual_success_count} 个")
            logger.warning("   可能原因：")
            logger.warning("   1. 所有关键词的职位已抓取完毕")
            logger.warning("   2. 大部分职位被 AI 评分过滤（< 70 分）")
            logger.warning("   3. 大部分职位在黑名单或排除词列表中")
            logger.info("=" * 80)

            # 🔴 设置部分完成状态（不是 completed，而是 partial_completed）
            status_mgr.update(
                status="partial_completed",  # 自定义状态
                message=f"⚠️ 部分完成：成功投递 {actual_success_count}/{limit} 个职位",
                progress=int((actual_success_count / limit) * 100) if limit > 0 else 0,
                step="partial_completed"
            )

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户中断任务")
        status_mgr.update(
            status=TaskStatus.STOPPED,
            message="任务已被用户中断",
            progress=0,
            step="interrupted"
        )
    except Exception as e:
        logger.exception(f"\n❌ 执行过程中发生错误: {e}")
        status_mgr.set_error(str(e))
    finally:
        # 11. 清理资源（只在整个脚本结束时关闭浏览器）
        logger.info("\n🧹 正在清理资源...")
        try:
            # 只有当浏览器已启动时才需要关闭
            if bot._is_browser_ready():
                bot.close()
                logger.info("   ✅ 浏览器已关闭，资源清理完成")
            else:
                logger.info("   ℹ️  浏览器未启动，无需清理")
        except Exception as e:
            logger.error(f"   ⚠️ 资源清理失败: {e}")


def setup_signal_handlers(status_mgr, bot=None):
    """
    方案2：设置信号处理器，捕获 Ctrl+C 中断

    Args:
        status_mgr: 状态管理器实例
        bot: 投递机器人实例（可选）
    """
    def signal_handler(signum, frame):
        """处理中断信号"""
        logger.warning("\n⚠️ 接收到中断信号 (Ctrl+C)，正在优雅退出...")

        # 清理状态
        try:
            status_mgr.update(
                status=TaskStatus.STOPPED,
                message="任务已被用户中断",
                progress=0,
                step="interrupted"
            )
            logger.info("✅ 状态已清理")
        except Exception as e:
            logger.error(f"清理状态失败: {e}")

        # 关闭浏览器
        if bot:
            try:
                if bot._is_browser_ready():
                    bot.close()
                    logger.info("✅ 浏览器已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器失败: {e}")

        logger.info("👋 程序已退出")
        sys.exit(0)

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill 命令


if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="AutoJobAgent - 目标驱动自动投递系统（多用户版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_auto_apply.py --user_id jackson --resume_path data/inputs/my_resume.pdf --keywords "Python" --limit 1
        """
    )

    # 必需参数
    parser.add_argument("--resume_path", required=True, help="简历 PDF 路径")
    parser.add_argument("--keywords", required=True, help="搜索关键词（逗号分隔）")

    # 🔴 新增：用户 ID 参数（必需）
    parser.add_argument("--user_id", required=True, help="用户 ID，用于多用户数据隔离（必需）")

    # 可选参数
    parser.add_argument("--transcript_path", default=None, help="成绩单 PDF 路径（可选）")
    parser.add_argument("--limit", type=int, default=10, help="目标成功投递数量（默认: 10）")
    parser.add_argument("--block_list", default="", help="公司黑名单（逗号分隔）")
    parser.add_argument("--title_exclusions", default="", help="职位标题排除词（逗号分隔）")
    parser.add_argument("--headless", type=str, default="true", choices=["true", "false"], help="是否无头模式（默认: true）")
    parser.add_argument("--delay", type=float, default=5.0, help="投递延迟秒数（默认: 5.0）")
    parser.add_argument("--page_size", type=int, default=200, help="每页抓取数量上限（默认: 200，建议设置足够大以抓取整页）")

    args = parser.parse_args()

    # 解析 headless
    headless = args.headless.lower() == "true"
    limit = args.limit if args.limit > 0 else 10

    try:
        # ✅ 关键修改：传入 user_id 参数
        main_auto_apply(
            resume_path=args.resume_path,
            keywords=args.keywords,
            user_id=args.user_id,  # 🔴 新增
            block_list=args.block_list,
            title_exclusions=args.title_exclusions,
            transcript_path=args.transcript_path,
            limit=limit,
            headless=headless,
            delay=args.delay,
            page_size=args.page_size
        )
    except KeyboardInterrupt:
        logger.warning("\n🛑 任务已由用户手动停止")
    except Exception as e:
        logger.exception(f"\n❌ 运行过程中发生错误: {e}")
        sys.exit(1)