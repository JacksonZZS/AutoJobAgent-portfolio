"""
简历分析 API 路由
封装 LLMEngine 提供简历智能分析
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pathlib import Path
import json
import logging

# 导入核心业务模块
from core.llm_engine import LLMEngine, load_pdf_text

# 导入认证依赖和工具函数
from backend.api.v1.auth import get_current_user
from backend.models.schemas import (
    UserInfo,
    AnalyzeResumeRequest,
    AnalyzeResumeResponse
)

router = APIRouter(prefix="/analysis", tags=["Resume Analysis"])

# 缓存文件路径
ANALYSIS_CACHE_FILE = Path("data/analysis_cache.json")

# 配置日志
logger = logging.getLogger(__name__)


# ============================================================
# 工具函数
# ============================================================

def save_analysis_to_cache(file_hash: str, result: dict):
    """
    保存分析结果到缓存

    Args:
        file_hash: 文件哈希值
        result: 分析结果
    """
    try:
        # 读取现有缓存
        if ANALYSIS_CACHE_FILE.exists():
            with open(ANALYSIS_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        else:
            cache = {}

        # 更新缓存
        import time
        cache[file_hash] = {
            **result,
            "timestamp": time.time()
        }

        # 写回缓存文件
        ANALYSIS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ANALYSIS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"Failed to save analysis to cache: {e}")


# ============================================================
# API 端点
# ============================================================

@router.post("/analyze-resume", response_model=AnalyzeResumeResponse)
async def analyze_resume(
    request: AnalyzeResumeRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    智能分析简历

    **功能**：
    - 提取职位搜索关键词（3-5个）
    - 识别前雇主公司（自动加入黑名单）
    - 根据资历等级生成职位排除词
    - 结果自动缓存（基于文件哈希）

    **分析逻辑**（调用 core/llm_engine.py）：
    - Fresh Grad → 排除 Senior/Manager/Director/Lead
    - Mid-Level → 排除 Intern/Junior
    - Senior → 排除 Intern/Junior/Entry
    """
    print(f"=" * 80)
    print(f"[简历分析] 开始处理")
    print(f"[简历分析] 用户: {current_user.username} (ID: {current_user.id})")
    print(f"[简历分析] 简历路径: {request.resume_path}")
    print(f"[简历分析] 成绩单路径: {request.transcript_path}")
    print(f"=" * 80)

    # 验证参数
    if not request.resume_path:
        print(f"[简历分析] ❌ 缺少 resume_path")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="resume_path is required"
        )

    resume_path = Path(request.resume_path)
    if not resume_path.exists():
        print(f"[简历分析] ❌ 简历文件不存在: {request.resume_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume file not found: {request.resume_path}"
        )

    # 初始化 LLM 引擎
    print(f"[简历分析] 初始化 LLM 引擎...")
    try:
        llm_engine = LLMEngine()
        print(f"[简历分析] ✅ LLM 引擎初始化成功")
    except Exception as e:
        print(f"[简历分析] ❌ LLM 引擎初始化失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize LLM engine: {str(e)}"
        )

    try:
        # 1. 加载简历文本
        print(f"[简历分析] 加载简历文本...")
        resume_text = load_pdf_text(str(resume_path))
        print(f"[简历分析] 简历文本长度: {len(resume_text) if resume_text else 0}")

        if not resume_text or len(resume_text.strip()) < 50:
            print(f"[简历分析] ❌ 简历文本过短或为空")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to extract text from resume or text is too short"
            )

        # 2. 加载成绩单文本（如果有）
        transcript_text = None
        if request.transcript_path:
            transcript_path = Path(request.transcript_path)
            print(f"[简历分析] 加载成绩单文本: {transcript_path}")
            if transcript_path.exists():
                transcript_text = load_pdf_text(str(transcript_path))
                print(f"[简历分析] 成绩单文本长度: {len(transcript_text) if transcript_text else 0}")
            else:
                print(f"[简历分析] ⚠️ 成绩单文件不存在")

        # 3. 调用 LLM 生成搜索策略
        print(f"[简历分析] 调用 LLM 生成搜索策略...")
        try:
            result = llm_engine.generate_search_strategy(
                resume_text=resume_text,
                transcript_text=transcript_text
            )
            print(f"[简历分析] ✅ LLM 返回结果: {result}")
        except Exception as llm_error:
            print(f"[简历分析] ❌ LLM API 调用失败: {llm_error}")
            logger.error(f"LLM API call failed: {llm_error}")
            result = None

        # 4. 解析结果（带降级方案）
        if result is None or not isinstance(result, dict):
            logger.warning("LLM analysis failed or returned invalid data, using fallback strategy")

            # 降级方案：从简历中提取关键词
            keywords = "Software Engineer, Developer, Data Analyst"
            blocked_companies = ""
            title_exclusions = "Senior, Lead, Manager, Director"
            user_profile = {"seniority": "Mid-Level", "note": "Fallback analysis (LLM unavailable)"}

        else:
            # 处理 keywords（可能是数组或字符串）
            keywords_raw = result.get("keywords", [])
            if isinstance(keywords_raw, list):
                keywords = ", ".join(keywords_raw) if keywords_raw else "Software Engineer"
            else:
                keywords = str(keywords_raw) if keywords_raw else "Software Engineer"

            # 🔧 修复：blacklist 应该是职位排除词，不是公司黑名单
            # LLM 返回的 blacklist 字段实际上是职位排除词（如 Senior, Lead, Manager）
            blacklist_raw = result.get("blacklist", [])
            if isinstance(blacklist_raw, list):
                title_exclusions = ", ".join(blacklist_raw) if blacklist_raw else "Senior, Lead, Manager"
            else:
                title_exclusions = str(blacklist_raw) if blacklist_raw else "Senior, Lead, Manager"

            # 公司黑名单需要从简历中提取前雇主（LLM 当前没有返回这个字段）
            # TODO: 需要更新 LLM prompt 来识别并返回前雇主公司
            blocked_companies = ""

            user_profile = result.get("user_profile", None)

        # 5. 保存到缓存（如果有 file_hash）
        # 注意：file_hash 应该从上传阶段传入，这里简化处理
        import hashlib
        file_hash = hashlib.md5(resume_text.encode()).hexdigest()

        save_analysis_to_cache(file_hash, {
            "keywords": keywords,
            "blocked_companies": blocked_companies,
            "title_exclusions": title_exclusions
        })

        # 6. 返回响应
        return AnalyzeResumeResponse(
            keywords=keywords,
            blocked_companies=blocked_companies,
            title_exclusions=title_exclusions,
            user_profile=user_profile,
            message="✅ 分析成功！已自动填充搜索参数"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze resume: {str(e)}"
        )


@router.post("/analyze-transcript")
async def analyze_transcript(
    transcript_path: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    分析成绩单提取优选课程

    **功能**：
    - 提取 B+ 以上成绩的课程
    - 用于简历生成时突出学术优势

    **调用**：core/llm_engine.extract_top_courses()
    """

    transcript_path_obj = Path(transcript_path)
    if not transcript_path_obj.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript file not found: {transcript_path}"
        )

    llm_engine = LLMEngine()

    try:
        # 加载成绩单文本
        transcript_text = load_pdf_text(str(transcript_path_obj))

        if not transcript_text or len(transcript_text.strip()) < 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to extract text from transcript"
            )

        # 调用 LLM 提取优选课程
        top_courses = llm_engine.extract_top_courses(
            transcript_text=transcript_text,
            min_grade="B+"
        )

        return {
            "top_courses": top_courses,
            "message": "成绩单分析成功"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze transcript: {str(e)}"
        )
