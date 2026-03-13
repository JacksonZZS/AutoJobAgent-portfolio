"""
简历反馈重新生成模块
根据用户反馈调用 LLM 重新生成简历
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def regenerate_resume_with_feedback(
    user_id: str,
    username: str,
    feedback: str,
    old_resume_path: str,
    job_info: Dict[str, Any]
) -> str:
    """
    根据用户反馈重新生成简历

    Args:
        user_id: 用户 ID
        username: 用户名
        feedback: 用户反馈内容
        old_resume_path: 原简历 PDF 路径
        job_info: 职位信息 (title, company, url)

    Returns:
        新简历 PDF 路径
    """
    from core.llm_engine import LLMEngine
    from core.pdf_generator import generate_resume_pdf
    from core.pdf_parser import extract_text_from_pdf

    logger.info(f"[ResumeGenerator] 开始根据反馈重新生成简历")
    logger.info(f"[ResumeGenerator] 反馈内容: {feedback[:100]}...")

    # 1. 读取原简历 PDF 内容
    old_resume_text = ""
    if Path(old_resume_path).exists():
        old_resume_text = extract_text_from_pdf(old_resume_path)
        logger.info(f"[ResumeGenerator] 读取原简历成功，长度: {len(old_resume_text)}")

    # 2. 读取用户原始简历数据（如果有缓存）
    cache_path = Path(f"data/resume_cache/{username}_resume_data.json")
    original_resume_data = {}
    if cache_path.exists():
        with open(cache_path, 'r', encoding='utf-8') as f:
            original_resume_data = json.load(f)
        logger.info(f"[ResumeGenerator] 读取缓存简历数据成功")

    # 3. 调用 LLM 根据反馈修改简历
    llm = LLMEngine()

    prompt = f"""你是一个专业的简历优化专家。用户对他们的简历提供了以下反馈，请根据反馈修改简历。

## 原简历内容：
{old_resume_text[:3000]}

## 目标职位：
- 职位：{job_info.get('title', 'N/A')}
- 公司：{job_info.get('company', 'N/A')}

## 用户反馈：
{feedback}

## 任务：
根据用户反馈修改简历内容。返回修改后的简历数据（JSON格式）。

重要：
1. 只修改用户反馈中提到的部分
2. 保持其他部分不变
3. 确保信息真实，不要编造

返回 JSON 格式：
{{
    "header": {{
        "name": "姓名",
        "phone": "电话",
        "email": "邮箱",
        "linkedin": "LinkedIn URL"
    }},
    "summary": "个人简介（2-3句话）",
    "experience": [
        {{
            "title": "职位",
            "company": "公司",
            "period": "时间段",
            "bullets": ["职责1", "职责2"]
        }}
    ],
    "education": [
        {{
            "degree": "学位",
            "school": "学校",
            "period": "时间"
        }}
    ],
    "skills": ["技能1", "技能2"]
}}
"""

    try:
        response = llm.call_llm(prompt, max_tokens=4000)

        # 解析 JSON 响应
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            modified_resume_data = json.loads(json_match.group())
        else:
            # 如果解析失败，使用原数据
            logger.warning("[ResumeGenerator] JSON 解析失败，使用原数据")
            modified_resume_data = original_resume_data

    except Exception as e:
        logger.error(f"[ResumeGenerator] LLM 调用失败: {e}")
        modified_resume_data = original_resume_data

    # 4. 生成新的 PDF
    output_dir = Path(old_resume_path).parent
    new_resume_path = str(output_dir / f"Resume_{job_info.get('company', 'Unknown')}_{job_info.get('title', 'Unknown')}_v2.pdf")

    try:
        await generate_resume_pdf(
            resume_data=modified_resume_data,
            output_path=new_resume_path
        )
        logger.info(f"[ResumeGenerator] 新简历生成成功: {new_resume_path}")
    except Exception as e:
        logger.error(f"[ResumeGenerator] PDF 生成失败: {e}")
        # 如果生成失败，返回原路径
        return old_resume_path

    return new_resume_path
