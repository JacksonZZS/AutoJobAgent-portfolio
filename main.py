import asyncio
import os
import sys
from datetime import datetime
import hashlib

# 确保项目内部引用正常
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.scraper import search_and_crawl_jobs
from core.pdf_parser import extract_text_from_pdf
from core.llm_engine import LLMEngine
from core.cv_renderer import generate_pdf_cv
from core.history_manager import HistoryManager

# --- 全局路径配置 ---
INPUT_DIR = "data/inputs"
OUTPUT_DIR = "data/outputs"
HISTORY_PATH = "data/history/processed_jobs.json"

# --- 任务配置 ---
TARGET_COUNT = 1  # 🎯 目标：总共生成 10 份高质量简历
JOBS_PER_FETCH = 8 # 每次搜索抓取的数量

async def main():
    print(f"🤖 === AutoJobAgent | AI 驱动全自动模式 | {datetime.now().strftime('%H:%M:%S')} ===")
    
    # 0. 初始化核心组件
    llm = LLMEngine()
    history = HistoryManager(HISTORY_PATH)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # --- [Step 1] 核心资料加载与 MD5 自动校验 ---
    def get_file_md5(filepath):
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    transcript_path = os.path.join(INPUT_DIR, "transcript.pdf")
    resume_pdf_path = os.path.join(INPUT_DIR, "my_resume.pdf")

    if not os.path.exists(resume_pdf_path) or not os.path.exists(transcript_path):
        print("❌ 错误: 找不到核心资料 (my_resume.pdf 或 transcript.pdf)。请检查 data/inputs 目录。")
        return

    # 解析简历文本（带缓存机制）
    resume_md5 = get_file_md5(resume_pdf_path)
    resume_cache = os.path.join(INPUT_DIR, f"resume_{resume_md5}.cache.txt")
    
    if os.path.exists(resume_cache):
        with open(resume_cache, "r", encoding="utf-8") as f: 
            resume_text = f.read()
    else:
        print("📄 正在解析新简历 PDF...")
        resume_text = extract_text_from_pdf(resume_pdf_path)
        with open(resume_cache, "w", encoding="utf-8") as f: 
            f.write(resume_text)
    
    # 解析成绩单文本
    transcript_text = extract_text_from_pdf(transcript_path)

    # --- [Step 2] AI 制定自主搜索指令 ---
    print("\n🧠 [Step 2] AI 正在分析你的资历，自主生成最佳匹配关键词...")
    strategy = llm.generate_search_strategy(resume_text, transcript_text)
    
    # 🔴 严格模式检查：如果 AI 没返回，或 keywords 为空，直接退出
    if not strategy or not strategy.get("keywords"):
        print("❌ 错误: AI 未能生成有效的搜索策略。")
        print("⚠️ 因为您要求不使用默认关键词，程序将在此停止。请检查 API Key 或网络连接。")
        exit()  # 直接终止程序

    # ✅ 获取 AI 生成的搜索词
    search_queries = strategy["keywords"]
    search_blacklist = strategy.get("blacklist", [])

    print(f"✅ AI 制定搜索词 (100% AI生成): {search_queries}")
    print(f"🚫 排除关键词: {search_blacklist}")

    # --- [Step 3 & 4] 目标驱动的自主轮询循环 ---
    total_generated = 0
    keyword_index = 0
    already_seen_urls = set()

    # 循环直到凑齐 10 个成功生成的简历
    while total_generated < TARGET_COUNT:
        # 🔄 轮询 AI 提供的关键词 (使用 search_queries)
        current_keyword = search_queries[keyword_index % len(search_queries)]
        print(f"\n🚀 [进度: {total_generated}/{TARGET_COUNT}] AI 正在搜寻领域: '{current_keyword}'")

        # 调用爬虫抓取职位
        jobs = await search_and_crawl_jobs(
            keyword=current_keyword, 
            max_count=JOBS_PER_FETCH,
            blacklist=search_blacklist
        )

        if not jobs:
            print(f"   ℹ️ 领域 '{current_keyword}' 暂无符合要求的新职位。")
        else:
            for job in jobs:
                # 如果在循环内已经凑齐了，直接退出
                if total_generated >= TARGET_COUNT: break
                
                # 历史记录去重：不处理投过的，不处理本轮重复的
                if history.is_processed(job['link']) or job['link'] in already_seen_urls:
                    continue
                already_seen_urls.add(job['link'])
                
                # --- AI 深度决策中心 ---
                match_result = llm.check_match_score(
                    resume_text=resume_text + "\n" + transcript_text,
                    jd_text=job['jd_content']
                )

                # 🟢 增加容错检查，防止 NoneType 报错
                if match_result is None:
                    print(f"   ⚠️ AI 预审失败（可能是网络或格式问题），跳过该职位: {job['title']}")
                    continue

                # 评分判定
                score = match_result.get("score", 0)
                
                if score >= 70:
                    print(f"   ✨ 发现高分职位 ({score}分): {job['title']} @ {job['company']}")
                    
                    # AI 执行重构
                    cv_data = llm.generate_resume_data(
                        resume_text=resume_text,
                        transcript_text=transcript_text,
                        jd_text=job['jd_content']
                    )

                    if cv_data:
                        # 动态获取文件名信息
                        candidate_name = cv_data.get("name", "Candidate").replace(" ", "_")
                        company_name = job.get('company', 'UnknownCo').replace(" ", "_")
                        safe_title = "".join(c for c in job['title'] if c.isalnum() or c in " _-").strip().replace(" ", "_")
                        
                        # 组合文件名
                        date_tag = datetime.now().strftime('%m%d')
                        filename = f"[{score}分]_{candidate_name}_{company_name}_{safe_title}_{date_tag}.pdf"
                        output_path = os.path.join(OUTPUT_DIR, filename)
                        
                        # 渲染 PDF
                        await generate_pdf_cv(cv_data, output_path)
                        
                        # 存入历史记录
                        history.add_job(job['link'], job['title'], job['company'], status=f"GENERATED_{score}")
                        total_generated += 1
                        print(f"   ✅ [成功] 简历已生成: {filename}")
                    else:
                        print("   ❌ [错误] AI 生成 JSON 格式异常。")
                else:
                    # 记录未通过的原因
                    history.add_job(job['link'], job['title'], job['company'], status=f"LOW_SCORE_{score}")

        # 准备切换到下一个关键词
        keyword_index += 1
        
        # 简单休眠，保护目标网站
        await asyncio.sleep(2)

    print("\n" + "="*50)
    print(f"🎉 任务达成！已为候选人生成 {total_generated} 份高度匹配的简历资料。")
    print(f"📂 请前往查看: {OUTPUT_DIR}")
    print("="*50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 任务已由用户手动停止。")
    except Exception as e:
        print(f"❌ 运行过程中发生未知错误: {str(e)}")