"""
任务管理 API 路由
封装自动投递流程，支持后台任务和实时状态管理
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
import asyncio
import time
import os
from pathlib import Path

# 导入核心业务模块（保持不变）
from core.status_manager import get_status_manager, TaskStatus
from core.history_manager import HistoryManager
from core.scraper import search_and_crawl_jobs
from core.apply_bot import JobsDBApplyBot
from core.user_identity import get_user_identity_manager
from core.health_checker import check_indeed_health, get_health_checker, IndeedStatus
from core.market_analyzer import extract_skills, extract_salary

# 导入认证依赖
from backend.api.v1.auth import get_current_user
from backend.models.schemas import (
    UserInfo,
    StartTaskRequest,
    StartTaskResponse,
    TaskStatusResponse,
    ManualDecisionRequest,
    CurrentJobInfo,
    TaskStats,
    ManualReviewData,
    DimensionScore,
    MessageResponse,
    BatchSkipRequest,
    BatchSkipResponse
)

router = APIRouter(prefix="/jobs", tags=["Job Management"])


# ============================================================
# 后台任务函数
# ============================================================

def run_job_task(user_id: int, request: StartTaskRequest):
    """
    后台任务：运行自动投递流程（目标驱动循环）

    Args:
        user_id: 用户 ID
        request: 任务启动请求参数
    """
    try:
        status_mgr = get_status_manager(str(user_id))
        history_mgr = HistoryManager(user_id=str(user_id))

        # 1. 初始化
        status_mgr.update(
            status=TaskStatus.INITIALIZING,
            message="正在初始化任务...",
            progress=0,
            step="init"
        )

        # 2. 获取用户身份信息
        identity_mgr = get_user_identity_manager()
        user_identity = identity_mgr.get_user_identity(str(user_id))

        # 转换为字典以便访问（identity 是 UserIdentity 对象）
        identity_dict = user_identity.to_dict() if user_identity else {}

        # 🔴 读取真实简历内容
        resume_text = ""
        if request.resume_path and os.path.exists(request.resume_path):
            try:
                from core.llm_engine import load_pdf_text
                resume_text = load_pdf_text(request.resume_path)
                print(f"✅ 成功加载简历，文本长度: {len(resume_text)} 字符")
            except Exception as e:
                print(f"⚠️ 加载简历失败: {e}")
                resume_text = ""

        # 构造候选人画像
        candidate_profile = {
            "user_id": str(user_id),
            "real_name": identity_dict.get("real_name", ""),
            "email": identity_dict.get("email", ""),
            "phone": identity_dict.get("phone", ""),
            "linkedin": identity_dict.get("linkedin"),
            "github": identity_dict.get("github"),
            "resume_text": resume_text,  # 🔴 传入真实简历内容
            "resume_language": "en"
        }

        # 3. 初始化 LLM 引擎
        from core.llm_engine import LLMEngine
        llm_engine = LLMEngine()

        # 🔴 获取平台类型
        platform = request.platform.value if hasattr(request, 'platform') else "jobsdb"
        print(f"🎯 目标平台: {platform.upper()}")

        # 🔴 调试：打印过滤参数
        print(f"🚫 标题排除词: {request.title_exclusions}")
        print(f"🚫 公司黑名单: {request.company_blacklist}")
        print(f"📊 分数阈值: {request.score_threshold}")

        # 🔴 目标驱动循环变量
        keywords_list = [k.strip() for k in request.keywords.split(',')]
        target_count = request.target_count
        success_count = 0
        processed_count = 0
        failed_count = 0
        skipped_count = 0

        # 关键词轮询状态
        keyword_page_map = {kw: 1 for kw in keywords_list}  # 每个关键词当前页码
        exhausted_keywords = set()  # 已枯竭的关键词
        max_pages_per_keyword = 10  # 每个关键词最多翻页次数
        jobs_per_page = 20  # 每页抓取职位数

        # 🔴 提前初始化 ApplyBot（浏览器只打开一次）
        from core.apply_bot import JobsDBApplyBot, ApplyJobInfo
        bot = None
        indeed_scraper = None  # 🔴 Indeed 爬虫实例（复用）
        jobsdb_scraper = None  # 🔴 JobsDB 爬虫实例（复用）

        print(f"\n🚀 开始目标驱动循环...")
        print(f"🎯 目标: 成功投递 {target_count} 个职位")
        print(f"🔑 关键词: {keywords_list}")
        print(f"💡 第一个高分职位出现时会打开浏览器窗口\n")

        # 🔴 根据平台选择爬虫
        linkedin_scraper = None  # 🔴 LinkedIn 爬虫实例

        if platform == "linkedin":
            # 🔴 使用 JobSpy 爬取 LinkedIn（协议层，不需要浏览器）
            from core.jobspy_scraper import JobSpyScraper
            linkedin_scraper = JobSpyScraper(user_id=str(user_id))
            print("🌐 正在初始化 LinkedIn 爬虫 (JobSpy Guest API)...")
            print("✅ LinkedIn 爬虫已就绪（无需浏览器）\n")
        elif platform == "indeed":
            from core.indeed_dp import IndeedDPScraper
            indeed_scraper = IndeedDPScraper(
                user_id=str(user_id),
                headless=False,
                country="hk"
            )
            print("🌐 正在初始化 Indeed 浏览器 (DrissionPage)...")
            # DrissionPage 会在第一次 search_jobs 时自动创建浏览器
            print("✅ Indeed 爬虫已就绪\n")
        else:
            # 🔴 JobsDB 也提前初始化浏览器（复用）
            from core.jobsdb_bot import JobsDBScraper
            jobsdb_scraper = JobsDBScraper(user_id=str(user_id), headless=True)
            print("🌐 正在初始化 JobsDB 浏览器...")
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(jobsdb_scraper.init_browser())
            print("✅ JobsDB 浏览器已就绪\n")

        # 🔴 外层循环：目标驱动 + 关键词轮询
        round_count = 0
        max_rounds = 50  # 防止无限循环
        keyword_index = 0  # 🔴 关键词轮询索引

        try:
            while success_count < target_count and round_count < max_rounds:
                round_count += 1

                # 检查是否所有关键词都已枯竭
                if len(exhausted_keywords) == len(keywords_list):
                    print(f"\n⚠️ 所有关键词都已搜索完毕，无更多职位")
                    break

                # 检查是否应该停止
                current_status = status_mgr.read_status()
                if current_status.get("status") == TaskStatus.STOPPED.value:
                    print(f"\n🛑 收到停止信号，终止任务")
                    break

                # 🔴 真正的关键词轮询：每个关键词各爬一页再换下一个
                active_keywords = [kw for kw in keywords_list if kw not in exhausted_keywords]
                if not active_keywords:
                    print(f"\n⚠️ 所有关键词都已枯竭")
                    break

                keyword = active_keywords[keyword_index % len(active_keywords)]
                keyword_index += 1  # 下一轮换下一个关键词

                if success_count >= target_count:
                    break

                current_page = keyword_page_map[keyword]

                # 检查是否超过最大页数
                if current_page > max_pages_per_keyword:
                    print(f"   🔄 关键词 '{keyword}' 已达最大页数，标记为枯竭")
                    exhausted_keywords.add(keyword)
                    continue

                # 更新状态
                status_mgr.update(
                    status=TaskStatus.SCRAPING,
                    message=f"搜索: {keyword} (第 {current_page} 页)",
                    progress=10 + (success_count / target_count) * 30,
                    step="scraping"
                )

                print(f"\n📄 关键词: '{keyword}' - 第 {current_page} 页")

                # 🔴 爬取当前页职位 - 根据平台选择不同爬虫
                # 使用 nest_asyncio 或新事件循环来避免 "cannot be called from a running event loop"
                import nest_asyncio
                nest_asyncio.apply()

                if platform == "linkedin":
                    # 🔴 使用 JobSpy 搜索 LinkedIn（协议层，Guest API）
                    try:
                        raw_jobs = linkedin_scraper.search_jobs(
                            keyword=keyword,
                            location="Hong Kong",
                            sites=["linkedin"],
                            results_wanted=jobs_per_page,
                            hours_old=72,
                            fetch_description=True  # 获取完整 JD
                        )
                        # 转换为统一格式
                        jobs = []
                        for job in raw_jobs:
                            jd_text = job.description or ""
                            if jd_text:
                                print(f"   ✅ 获取 JD: {job.title[:30]}... ({len(jd_text)} 字符)")
                            else:
                                print(f"   ⚠️ JD 为空: {job.title[:30]}...")

                            jobs.append({
                                "title": job.title,
                                "company": job.company,
                                "location": job.location,
                                "link": job.job_url,
                                "jd_content": jd_text,
                                "source": "linkedin"
                            })
                    except Exception as e:
                        print(f"   ❌ LinkedIn 搜索失败: {e}")
                        import traceback
                        traceback.print_exc()
                        jobs = []
                elif platform == "indeed":
                    # 🔴 使用 DrissionPage 搜索（同步方法）
                    try:
                        raw_jobs = indeed_scraper.search_jobs(
                            keyword=keyword,
                            location="Hong Kong",
                            page=current_page
                        )
                        # 转换为统一格式，并获取 JD
                        jobs = []
                        for job in raw_jobs:
                            # 获取职位详情 JD
                            jd_text = job.jd_content or ""
                            if not jd_text:
                                try:
                                    jd_text = indeed_scraper.get_job_details(job.job_url)
                                    print(f"   ✅ 获取 JD: {job.title[:30]}... ({len(jd_text)} 字符)")
                                except Exception as e:
                                    print(f"   ⚠️ 获取 JD 失败: {e}")

                            jobs.append({
                                "title": job.title,
                                "company": job.company,
                                "location": job.location,
                                "link": job.job_url,
                                "jd_content": jd_text,
                                "source": "indeed"
                            })
                    except Exception as e:
                        print(f"   ❌ Indeed 搜索失败: {e}")
                        jobs = []
                else:
                    # 🔴 使用已初始化的 JobsDB 爬虫（复用浏览器）
                    try:
                        raw_jobs = asyncio.run(jobsdb_scraper.search_jobs(
                            keyword=keyword,
                            location="Hong Kong",
                            page=current_page,
                            filters={
                                "blacklist": request.company_blacklist or [],
                                "title_exclusions": request.title_exclusions or []
                            }
                        ))
                        # 转换为统一格式
                        jobs = []
                        for job in raw_jobs:
                            # 获取 JD
                            jd_text = ""
                            try:
                                jd_text = asyncio.run(jobsdb_scraper.get_job_details(job.job_url))
                            except:
                                pass
                            jobs.append({
                                "title": job.title,
                                "company": job.company,
                                "location": job.location,
                                "link": job.job_url,
                                "jd_content": jd_text,
                                "source": "jobsdb"
                            })
                    except Exception as e:
                        print(f"   ❌ JobsDB 搜索失败: {e}")
                        jobs = []

                # 更新页码
                keyword_page_map[keyword] = current_page + 1

                if not jobs:
                    print(f"   ⚠️ 关键词 '{keyword}' 无更多职位，标记为枯竭")
                    exhausted_keywords.add(keyword)
                    continue

                print(f"   📦 抓取到 {len(jobs)} 个职位")

                # 🔴 处理当前批次的职位
                for job in jobs:
                    if success_count >= target_count:
                        break

                    # 检查是否应该停止
                    current_status = status_mgr.read_status()
                    if current_status.get("status") == TaskStatus.STOPPED.value:
                        break

                    job_link = job.get("link", "")
                    job_title = job.get("title", "")
                    job_company = job.get("company", "")

                    # 🔴 修复：使用与 apply_bot 相同的 job_id 提取逻辑（8-10位数字）
                    import re
                    job_id = ""
                    if job_link:
                        match = re.search(r'/job/(\d{8,10})', job_link)
                        if match:
                            job_id = match.group(1)
                        else:
                            # 备用：尝试提取任意位置的 8-10 位数字
                            match = re.search(r'(\d{8,10})', job_link)
                            if match:
                                job_id = match.group(1)
                            else:
                                # 最后备用：使用 URL 最后一段
                                job_id = job_link.split("/")[-1]

                    # 🔴 先检查历史记录（在 AI 评分之前）
                    # 使用完整 link 检查，确保和 add_job() 使用相同的 ID 提取逻辑
                    if job_link and history_mgr.is_processed(job_link):
                        print(f"   ⏭️  跳过（历史）: {job_title[:30]}...")
                        skipped_count += 1
                        continue

                    # 🔴 标题排除词过滤（Senior, Manager, Director 等）
                    title_exclusions = request.title_exclusions or []
                    if title_exclusions:
                        title_lower = job_title.lower()
                        excluded = False
                        for exclusion in title_exclusions:
                            if exclusion.lower() in title_lower:
                                print(f"   🚫 跳过（标题排除）: {job_title[:30]}... (命中: {exclusion})")
                                skipped_count += 1
                                excluded = True
                                break
                        if excluded:
                            continue

                    # 🔴 公司黑名单过滤
                    company_blacklist = request.company_blacklist or []
                    if company_blacklist:
                        company_lower = job_company.lower()
                        blacklisted = False
                        for blocked in company_blacklist:
                            if blocked.lower() in company_lower:
                                print(f"   🚫 跳过（公司黑名单）: {job_company} - {job_title[:20]}...")
                                skipped_count += 1
                                blacklisted = True
                                break
                        if blacklisted:
                            continue

                    # 更新状态
                    current_job = {
                        "title": job_title,
                        "company": job_company,
                        "score": None,
                        "jd_content": job.get("jd_content", ""),
                        "job_url": job.get("job_url", ""),
                        "location": job.get("location", "")
                    }

                    status_mgr.update(
                        status=TaskStatus.ANALYZING,
                        message=f"AI 评分: {job_title[:40]}...",
                        progress=40 + (success_count / target_count) * 40,
                        current_job=current_job
                    )

                    # 🔴 LLM 评分
                    try:
                        match_result = llm_engine.check_match_score(
                            resume_text=candidate_profile["resume_text"],
                            jd_text=job.get("jd_content", ""),
                            resume_language="en"
                        )

                        score = match_result.get("score", 0) if match_result else 0
                        current_job["score"] = score
                        processed_count += 1

                        print(f"   📊 {job_title[:30]}... → {score}/100 (阈值: {request.score_threshold})")

                        # 判断是否达到阈值
                        if score >= request.score_threshold:
                            print(f"      ✅ 评分合格，准备投递...")

                            # 构造 ApplyJobInfo
                            job_info = ApplyJobInfo(
                                job_id=job_id,
                                title=job_title,
                                company=job_company,
                                location=job.get("location", ""),
                                job_url=job.get("link", ""),
                                jd_text=job.get("jd_content", ""),
                                score=score,
                                match_analysis=match_result
                            )

                            # 🔴 手动审核模式：生成简历和求职信 PDF，用户在前端下载后手动投递
                            print(f"      📋 高分职位，正在生成物料...")

                            # 更新状态：生成物料中
                            status_mgr.update(
                                status=TaskStatus.GENERATING,
                                message=f"正在生成定制简历和求职信: {job_title}",
                                progress=50 + (success_count / target_count) * 50,
                                current_job=current_job
                            )

                            # 🔴 调用 apply_bot 生成 PDF（但不自动投递）
                            resume_path = ""
                            cl_path = ""
                            cl_text = ""

                            try:
                                # 初始化 apply_bot（传入 llm_engine）
                                if bot is None:
                                    bot = JobsDBApplyBot(
                                        user_id=str(user_id),
                                        headless=True,
                                        status_manager=status_mgr,
                                        llm_engine=llm_engine
                                    )

                                # 生成定制简历和求职信
                                from pathlib import Path as PathLib
                                import re as regex

                                # 清理文件名（防止路径遍历攻击）
                                def sanitize_path_component(name: str, max_len: int = 30) -> str:
                                    # 移除 ../ 和其他危险字符
                                    safe = regex.sub(r'[^\w\s-]', '', name)
                                    safe = safe.replace('..', '').replace('/', '').replace('\\', '')
                                    return safe[:max_len].strip() or 'unknown'

                                username = identity_mgr.get_user_identity(str(user_id))
                                # 🔴 修复：对 username 也进行过滤，防止路径遍历
                                username_str = sanitize_path_component(
                                    username.username if username else f"user_{user_id}",
                                    30
                                )
                                c_name = sanitize_path_component(job_company, 20)
                                j_title = sanitize_path_component(job_title, 20)

                                # 创建输出目录（使用绝对路径）
                                # jobs.py 在 backend/api/v1/ 下，需要向上 4 级到项目根目录
                                base_dir = PathLib(__file__).parent.parent.parent.parent
                                job_folder = base_dir / "data" / "outputs" / username_str / f"{c_name}_{j_title}"
                                job_folder.mkdir(parents=True, exist_ok=True)

                                # 生成定制简历 PDF
                                resume_filename = f"Resume_{c_name}_{j_title}.pdf"
                                resume_pdf_path = job_folder / resume_filename

                                try:
                                    resume_path = bot._generate_custom_resume_pdf(
                                        candidate_profile=candidate_profile,
                                        job_info=job_info,
                                        output_path=str(resume_pdf_path)
                                    )
                                    print(f"      ✅ 定制简历已生成: {resume_path}")
                                except Exception as resume_err:
                                    print(f"      ⚠️ 简历生成失败: {resume_err}")

                                # 生成求职信
                                try:
                                    cl_text = bot.generate_cover_letter(candidate_profile, job_info)
                                    if cl_text:
                                        cl_filename = f"Cover_Letter_{c_name}_{j_title}.pdf"
                                        cl_pdf_path = job_folder / cl_filename
                                        cl_path = bot._generate_cover_letter_pdf(
                                            cover_letter_text=cl_text,
                                            job_info=job_info,
                                            output_path=str(cl_pdf_path)
                                        )
                                        print(f"      ✅ 求职信已生成: {cl_path}")
                                except Exception as cl_err:
                                    print(f"      ⚠️ 求职信生成失败: {cl_err}")

                            except Exception as gen_err:
                                print(f"      ❌ 物料生成失败: {gen_err}")

                            # 更新状态：人工复核（与 manual-decision API 匹配）
                            status_mgr.update(
                                status=TaskStatus.MANUAL_REVIEW,
                                message=f"请手动投递: {job_title}",
                                progress=50 + (success_count / target_count) * 50,
                                current_job=current_job
                            )

                            # 写入 manual_review_data（包含 PDF 路径）
                            current_data = status_mgr.read_status()
                            current_data["manual_review_data"] = {
                                "job_id": job_id,
                                "job_title": job_title,
                                "company_name": job_company,
                                "location": job.get("location", ""),
                                "job_url": job.get("link", ""),
                                "score": score,
                                "match_analysis": match_result,
                                "resume_path": resume_path,
                                "cl_path": cl_path,
                                "cl_text": cl_text
                            }
                            status_mgr._write_status(current_data)
                            print(f"      📂 物料已准备完成，等待用户操作...")

                            # 等待用户决定（通过前端按钮）
                            from core.interaction_manager import InteractionManager
                            interaction_mgr = InteractionManager(user_id=str(user_id))

                            user_decision = interaction_mgr.wait_for_user_action(
                                message=f"请投递后点击「已投递」，或跳过此职位",
                                timeout=600  # 10 分钟超时
                            )

                            if user_decision:
                                # 用户确认已投递
                                success_count += 1
                                print(f"      🎉 用户确认已投递！({success_count}/{target_count})")
                                # Extract skills/salary for Market Intelligence
                                _jd = job.get("jd_content", "")
                                _skills = extract_skills(_jd) if _jd else []
                                _salary = extract_salary(_jd) or extract_salary(job_title)

                                history_mgr.add_job(
                                    link=job.get("link", ""),
                                    title=job_title,
                                    company=job_company,
                                    status="applied",
                                    score=score,
                                    jd_content=_jd,
                                    location=job.get("location", ""),
                                    salary_raw=_salary.get("raw") if _salary else None,
                                    extracted_skills=_skills,
                                )
                            else:
                                # 用户跳过
                                skipped_count += 1
                                print(f"      ⏭️ 用户跳过此职位")

                        else:
                            # 评分不足，记录到历史避免重复评分
                            # Extract skills/salary for Market Intelligence
                            _jd_low = job.get("jd_content", "")
                            _skills_low = extract_skills(_jd_low) if _jd_low else []
                            _salary_low = extract_salary(_jd_low) or extract_salary(job_title)

                            history_mgr.add_job(
                                link=job.get("link", ""),
                                title=job_title,
                                company=job_company,
                                status="low_score",
                                score=score,
                                jd_content=_jd_low,
                                location=job.get("location", ""),
                                salary_raw=_salary_low.get("raw") if _salary_low else None,
                                extracted_skills=_skills_low,
                            )
                            failed_count += 1

                    except Exception as e:
                        print(f"      ❌ 评分失败: {e}")
                        failed_count += 1

            # 轮询间隙 - 🔴 关键词/翻页之间必须有延迟，否则 Cloudflare 会重新触发验证
            if success_count < target_count:
                # 随机延迟 8-15 秒，模拟真人浏览行为
                import random
                delay = random.uniform(8, 15)
                print(f"\n⏳ 第 {round_count} 轮完成，成功: {success_count}/{target_count}，等待 {delay:.0f}s 后继续...")
                time.sleep(delay)

        finally:
            # 🔴 关闭浏览器（确保在任何情况下都关闭）
            if indeed_scraper is not None:
                try:
                    indeed_scraper.close()  # DrissionPage 是同步方法
                    print("✅ Indeed 浏览器已关闭")
                except:
                    pass

            if jobsdb_scraper is not None:
                try:
                    asyncio.run(jobsdb_scraper.close())
                    print("✅ JobsDB 浏览器已关闭")
                except:
                    pass

            if bot is not None:
                try:
                    bot.close()
                except:
                    pass

        print(f"\n📊 目标驱动循环完成！")
        print(f"   总计评分: {processed_count} 个")
        print(f"   投递成功: {success_count} 个")
        print(f"   投递失败: {failed_count} 个")
        print(f"   跳过: {skipped_count} 个\n")

        # 7. 完成
        status_mgr.update(
            status=TaskStatus.COMPLETED,
            message=f"✅ 任务完成！成功投递: {success_count}/{target_count} 个",
            progress=100,
            step="completed"
        )

        # 更新统计数据
        status_mgr.update_stats(
            total_processed=processed_count,
            success=success_count,
            skipped=skipped_count,
            failed=failed_count
        )

    except Exception as e:
        # 错误处理
        status_mgr = get_status_manager(str(user_id))
        status_mgr.update(
            status=TaskStatus.ERROR,
            message=f"❌ 任务失败: {str(e)}",
            progress=0,
            step="error"
        )
        import traceback
        traceback.print_exc()


# ============================================================
# API 端点
# ============================================================

@router.post("/start-task", response_model=StartTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_task(
    request: StartTaskRequest,
    background_tasks: BackgroundTasks,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    启动自动投递任务

    **功能**：
    - 启动后台任务处理职位投递
    - 返回 WebSocket 连接地址用于实时监控
    - 任务在后台异步执行，不阻塞 API 响应

    **流程**：
    1. 验证是否有正在运行的任务
    2. 启动后台任务
    3. 返回 WebSocket 连接信息
    """

    status_mgr = get_status_manager(str(current_user.id))
    current_status = status_mgr.read_status()

    # 检查是否有正在运行的任务
    active_statuses = [
        TaskStatus.INITIALIZING.value,
        TaskStatus.SCRAPING.value,
        TaskStatus.ANALYZING.value,
        TaskStatus.GENERATING.value,
        TaskStatus.APPLYING.value,
        TaskStatus.MANUAL_REVIEW.value,
        TaskStatus.WAITING_USER.value
    ]

    if current_status.get("status") in active_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A task is already running. Please stop it first or wait for completion."
        )

    # 重置状态
    status_mgr.reset()

    # 启动后台任务
    background_tasks.add_task(run_job_task, current_user.id, request)

    # 生成任务 ID
    task_id = f"task_{current_user.id}_{int(time.time())}"

    return StartTaskResponse(
        task_id=task_id,
        status=TaskStatus.INITIALIZING,
        message="Task started successfully. Connect to WebSocket for real-time updates.",
        websocket_url=f"ws://localhost:8000/api/v1/ws/{current_user.id}"
    )


@router.get("/task-status", response_model=TaskStatusResponse)
async def get_task_status(current_user: UserInfo = Depends(get_current_user)):
    """
    获取任务状态

    **功能**：
    - 获取当前用户的任务执行状态
    - 包含进度、统计数据、当前处理职位等信息
    - 如果有人工复核任务，返回复核数据
    """

    status_mgr = get_status_manager(str(current_user.id))
    data = status_mgr.read_status()

    # 构造响应
    response = TaskStatusResponse(
        status=TaskStatus(data.get("status", "idle")),
        message=data.get("message", ""),
        progress=data.get("progress", 0),
        stats=TaskStats(**data.get("stats", {}))
    )

    # 添加当前职位信息
    if data.get("current_job"):
        response.current_job = CurrentJobInfo(**data["current_job"])

    # 添加人工复核数据
    if data.get("manual_review_data"):
        review_data = data["manual_review_data"]

        # 转换 dimensions
        dimensions = []
        for dim in review_data.get("dimensions", []):
            dimensions.append(DimensionScore(**dim))

        response.manual_review_data = ManualReviewData(
            score=review_data.get("score", 0),
            dimensions=dimensions,
            job_url=review_data.get("job_url", ""),
            job_title=review_data.get("job_title", ""),
            company_name=review_data.get("company_name", ""),
            resume_path=review_data.get("resume_path", ""),
            cl_path=review_data.get("cl_path", ""),
            cl_text=review_data.get("cl_text", ""),
            decision=review_data.get("decision")
        )

    # 添加最后更新时间
    if data.get("last_updated"):
        from datetime import datetime
        response.last_updated = datetime.fromisoformat(data["last_updated"])

    return response


@router.post("/manual-decision", response_model=MessageResponse)
async def submit_manual_decision(
    request: ManualDecisionRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    提交人工复核决策

    **功能**：
    - 用户对高分职位做出决策（投递/跳过）
    - 决策类型：APPLY / SKIP_PERMANENT / SKIP_TEMPORARY
    - 更新状态管理器，后台任务继续执行

    **决策说明**：
    - APPLY: 确认投递该职位
    - SKIP_PERMANENT: 永久跳过（写入历史记录）
    - SKIP_TEMPORARY: 稍后处理（下次运行仍会出现）
    """

    status_mgr = get_status_manager(str(current_user.id))

    # 验证当前状态
    current_status = status_mgr.read_status()
    if current_status.get("status") != TaskStatus.MANUAL_REVIEW.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No manual review pending. Current status: " + current_status.get("status", "unknown")
        )

    # 验证决策类型
    valid_decisions = ["APPLY", "SKIP_PERMANENT", "SKIP_TEMPORARY"]
    if request.decision not in valid_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision. Must be one of: {', '.join(valid_decisions)}"
        )

    # 设置决策
    status_mgr.set_manual_decision(request.decision)

    # 🔴 修复：SKIP_PERMANENT 需要写入历史记录
    if request.decision == "SKIP_PERMANENT":
        manual_review_data = current_status.get("manual_review_data", {})
        if manual_review_data:
            from core.history_manager import HistoryManager
            history_mgr = HistoryManager(user_id=str(current_user.id))
            # 🔴 修复字段名：写入时用的是 job_title/company_name，不是 title/company
            job_title = manual_review_data.get("job_title") or manual_review_data.get("title", "Unknown")
            company_name = manual_review_data.get("company_name") or manual_review_data.get("company", "Unknown")
            history_mgr.add_job(
                link=manual_review_data.get("job_url", ""),
                title=job_title,
                company=company_name,
                status="skipped_permanent",
                score=manual_review_data.get("score"),
                reason="User chose to permanently skip",
                location=manual_review_data.get("location", ""),
            )
            print(f"[跳过] 已写入历史: {company_name} - {job_title}")

    # 🔴 修复：同时设置 InteractionManager 信号，让后台任务继续
    from core.interaction_manager import get_interaction_manager
    interaction_mgr = get_interaction_manager(str(current_user.id))

    if request.decision == "APPLY":
        interaction_mgr.set_signal("continue", {"decision": "APPLY"})
    else:
        interaction_mgr.set_signal("cancel", {"decision": request.decision})

    # 🔴 修复：清除 manual_review_data，让物料卡片消失
    status_mgr.clear_manual_review()

    # 更新状态为"正在匹配下一个职位"
    status_mgr.update(
        status=TaskStatus.ANALYZING,
        message="正在匹配下一个职位...",
        progress=None  # 保留当前进度
    )

    # 删除锁文件（如果存在）
    lock_file = Path(f"data/locks/user_interaction_{current_user.id}.lock")
    if lock_file.exists():
        lock_file.unlink()

    next_action = {
        "APPLY": "Proceeding with application...",
        "SKIP_PERMANENT": "Job permanently skipped and added to history.",
        "SKIP_TEMPORARY": "Job skipped for now, will appear again in next run."
    }

    return MessageResponse(
        message="Decision recorded successfully",
        status="success",
        data={
            "decision": request.decision,
            "next_action": next_action.get(request.decision, "Task will resume")
        }
    )


@router.post("/stop-task", response_model=MessageResponse)
async def stop_task(current_user: UserInfo = Depends(get_current_user)):
    """
    停止当前任务

    **功能**：
    - 停止正在运行的自动投递任务
    - 更新任务状态为 STOPPED
    - 保留已处理的统计数据
    """

    status_mgr = get_status_manager(str(current_user.id))
    current_status = status_mgr.read_status()

    # 检查是否有任务在运行
    if current_status.get("status") in [TaskStatus.IDLE.value, TaskStatus.COMPLETED.value, TaskStatus.STOPPED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active task to stop"
        )

    # 更新状态
    status_mgr.update(
        status=TaskStatus.STOPPED,
        message="⏹️ 任务已手动停止",
        progress=current_status.get("progress", 0)
    )

    # 🔴 清除物料卡片
    status_mgr.clear_manual_review()

    return MessageResponse(
        message="Task stopped successfully",
        status="success",
        data={
            "stats": current_status.get("stats", {})
        }
    )


@router.post("/batch-skip-low-score", response_model=BatchSkipResponse)
async def batch_skip_low_score(
    request: BatchSkipRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    批量跳过低分职位

    **功能**：
    - 从历史记录中找出所有低于指定分数的职位
    - 将它们标记为永久跳过或临时跳过
    - 返回被跳过的职位数量和列表

    **参数**：
    - threshold: 分数阈值（默认 60），低于此分数的职位会被跳过
    - skip_type: 跳过类型（SKIP_PERMANENT / SKIP_TEMPORARY）
    """

    history_mgr = HistoryManager(user_id=str(current_user.id))
    history_data = history_mgr.history

    skipped_jobs = []
    skipped_count = 0

    # 遍历历史记录，找出低分且未处理的职位
    for job_id, record in list(history_data.items()):
        score = record.get("score")
        current_status = record.get("status", "")

        # 跳过已经是 applied/skipped_permanent 的职位
        if current_status in ["applied", "success", "skipped_permanent"]:
            continue

        # 检查分数是否低于阈值
        if score is not None and score < request.threshold:
            # 更新状态
            if request.skip_type == "SKIP_PERMANENT":
                history_data[job_id]["status"] = "skipped_permanent"
                history_data[job_id]["reason"] = f"Batch skipped: score {score} < {request.threshold}"
            else:
                history_data[job_id]["status"] = "skipped_temporary"
                history_data[job_id]["reason"] = f"Temporarily skipped: score {score} < {request.threshold}"

            skipped_jobs.append({
                "job_id": job_id,
                "title": record.get("title", ""),
                "company": record.get("company", ""),
                "score": score
            })
            skipped_count += 1

    # 保存更新后的历史记录
    if skipped_count > 0:
        history_mgr._save_history()

    return BatchSkipResponse(
        skipped_count=skipped_count,
        message=f"成功跳过 {skipped_count} 个低于 {request.threshold} 分的职位",
        skipped_jobs=skipped_jobs
    )


@router.get("/status", response_model=TaskStatusResponse)
async def get_status(current_user: UserInfo = Depends(get_current_user)):
    """
    获取任务状态（简化版，用于轮询）

    **功能**：
    - 与 /task-status 相同，提供更短的路径
    """
    return await get_task_status(current_user)


@router.get("/health/indeed")
async def check_indeed_health_endpoint(
    force: bool = False,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    检测 Indeed 可访问性

    **功能**：
    - 快速检测 Indeed 是否可访问
    - 返回状态、当前爬虫策略、是否可以继续
    - 自动缓存结果 5 分钟

    **参数**：
    - force: 是否强制刷新（忽略缓存）

    **返回**：
    - status: healthy / captcha / blocked / timeout / unknown
    - scraper_type: playwright / drission
    - can_proceed: 是否可以继续爬取
    - message: 详细信息
    """
    result = await check_indeed_health(force=force)
    checker = get_health_checker()

    return {
        "status": result.status.value,
        "scraper_type": result.scraper_type.value,
        "current_scraper": checker.current_scraper.value,
        "can_proceed": result.can_proceed,
        "message": result.message,
        "check_time": round(result.check_time, 2),
        "fallback_count": checker._fallback_count,
    }


@router.post("/health/indeed/switch")
async def switch_indeed_scraper(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    手动切换 Indeed 爬虫策略

    **功能**：
    - 在 Playwright 和 DrissionPage 之间切换
    - 用于手动绕过封锁

    **返回**：
    - new_scraper: 切换后的爬虫类型
    """
    checker = get_health_checker()
    new_scraper = checker.switch_scraper()

    return {
        "message": f"Switched to {new_scraper.value}",
        "new_scraper": new_scraper.value,
        "fallback_count": checker._fallback_count,
    }


@router.post("/health/indeed/reset")
async def reset_indeed_health(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    重置 Indeed 健康检测状态

    **功能**：
    - 重置爬虫策略为默认（Playwright）
    - 清除缓存
    - 重置切换计数
    """
    checker = get_health_checker()
    checker.reset()

    return {
        "message": "Indeed health checker reset",
        "current_scraper": checker.current_scraper.value,
        "fallback_count": 0,
    }
