"""
简历优化 API 路由
提供简历优化服务，符合香港HR要求
"""

import json
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import logging
from pathlib import Path
from datetime import datetime

from backend.api.v1.auth import get_current_user
from core.llm_engine import LLMEngine, load_pdf_text
from core.pdf_generator import generate_resume_pdf

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Resume Optimizer"])


# ============================================================
# Pydantic Models
# ============================================================

class OptimizeResumeResponse(BaseModel):
    """简历优化响应"""
    success: bool
    message: str
    pdf_path: str
    optimized_data: Optional[dict] = None


def _parse_edit_instructions(raw_value: str) -> list[dict]:
    """Parse structured edit instructions from form payload."""
    if not raw_value.strip():
        return []

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="edit_instructions 格式错误，必须是 JSON") from exc

    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="edit_instructions 必须是数组")

    normalized: list[dict] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail=f"edit_instructions[{index}] 必须是对象")

        action = str(item.get("action", "")).strip().lower()
        target = str(item.get("target", "")).strip()
        content = str(item.get("content", "")).strip()

        if action not in {"delete", "add", "modify"}:
            raise HTTPException(status_code=400, detail=f"edit_instructions[{index}].action 不合法")
        if not target:
            raise HTTPException(status_code=400, detail=f"edit_instructions[{index}].target 不能为空")
        if action in {"add", "modify"} and not content:
            raise HTTPException(status_code=400, detail=f"edit_instructions[{index}].content 不能为空")

        normalized.append({
            "action": action,
            "target": target,
            "content": content,
        })

    return normalized


# ============================================================
# API Endpoints
# ============================================================

@router.post("/resume/optimize", response_model=OptimizeResumeResponse)
async def optimize_resume(
    resume_file: UploadFile = File(..., description="原始简历PDF文件"),
    permanent_resident: bool = Form(False, description="是否为香港永久居民"),
    available_immediately: bool = Form(False, description="是否可以立即上班"),
    linkedin_url: str = Form("", description="LinkedIn地址"),
    github_url: str = Form("", description="GitHub地址"),
    portfolio_url: str = Form("", description="个人网站/作品集地址"),
    target_profile: str = Form("general", description="目标版本，如 general / qa / fintech / da"),
    edit_instructions: str = Form("[]", description="结构化编辑指令 JSON"),
    additional_notes: str = Form("", description="其他补充信息"),
    current_user: dict = Depends(get_current_user)
):
    """
    优化简历以符合香港HR要求

    **功能**：
    - 上传原始简历PDF
    - 添加额外信息（永久居民、可立即上班、LinkedIn等）
    - AI优化简历格式和内容
    - 生成优化后的PDF文件

    **参数**：
    - `resume_file`: 原始简历PDF文件
    - `permanent_resident`: 是否为香港永久居民
    - `available_immediately`: 是否可以立即上班
    - `linkedin_url`: LinkedIn地址（可选）
    - `github_url`: GitHub地址（可选）
    - `portfolio_url`: 个人网站/作品集地址（可选）
    - `additional_notes`: 其他补充信息（可选）

    **返回**：
    ```json
    {
      "success": true,
      "message": "简历优化成功",
      "pdf_path": "path/to/optimized_resume.pdf"
    }
    ```
    """
    try:
        user_id = current_user.id
        username = current_user.username
        print(f"=" * 80)
        print(f"[简历优化] 开始处理")
        print(f"[简历优化] 用户: {username} (ID: {user_id})")
        print(f"[简历优化] 文件名: {resume_file.filename}")
        print(f"[简历优化] 永久居民: {permanent_resident}")
        print(f"[简历优化] 立即上班: {available_immediately}")
        print(f"=" * 80)
        parsed_edit_instructions = _parse_edit_instructions(edit_instructions)
        logger.info(f"[User {username}] 开始优化简历: {resume_file.filename}")

        # ============================================================
        # 1. 验证文件格式
        # ============================================================
        print(f"[步骤 1/7] 验证文件格式...")
        if not resume_file.filename.endswith('.pdf'):
            print(f"[错误] 文件格式不正确: {resume_file.filename}")
            raise HTTPException(
                status_code=400,
                detail="仅支持PDF格式的简历文件"
            )
        print(f"[步骤 1/7] ✅ 文件格式验证通过")

        # ============================================================
        # 2. 保存上传的简历文件
        # ============================================================
        print(f"[步骤 2/7] 保存上传的文件...")
        import tempfile

        # 创建临时文件
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_file_path = temp_dir / f"resume_temp_{user_id}.pdf"

        # 保存文件
        with open(temp_file_path, "wb") as f:
            content = await resume_file.read()
            f.write(content)

        print(f"[步骤 2/7] ✅ 文件已保存: {temp_file_path}")
        print(f"[步骤 2/7] 文件大小: {len(content)} 字节")
        logger.info(f"[User {username}] 简历文件已保存: {temp_file_path}")

        # ============================================================
        # 3. 提取简历文本
        # ============================================================
        print(f"[步骤 3/7] 提取简历文本...")
        try:
            resume_text = load_pdf_text(str(temp_file_path))
            print(f"[步骤 3/7] ✅ 文本提取成功")
            print(f"[步骤 3/7] 提取文本长度: {len(resume_text)} 字符")
            print(f"[步骤 3/7] 文本预览 (前200字符): {resume_text[:200]}")
            logger.info(f"[User {username}] 简历文本提取成功 (长度: {len(resume_text)} 字符)")
        except Exception as e:
            print(f"[步骤 3/7] ❌ 文本提取失败: {e}")
            logger.error(f"[User {username}] 简历文本提取失败: {e}")
            # 清理临时文件
            temp_file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail=f"无法读取简历内容: {str(e)}"
            )

        # ============================================================
        # 4. 调用 LLM 优化简历
        # ============================================================
        print(f"[步骤 4/7] 调用 LLM 优化简历...")
        try:
            llm_engine = LLMEngine()
            print(f"[步骤 4/7] LLM 引擎已初始化")
            print(f"[步骤 4/7] 开始调用 optimize_resume_for_hk_hr...")

            optimized_data = llm_engine.optimize_resume_for_hk_hr(
                resume_text=resume_text,
                permanent_resident=permanent_resident,
                available_immediately=available_immediately,
                linkedin_url=linkedin_url,
                github_url=github_url,
                portfolio_url=portfolio_url,
                target_profile=target_profile,
                edit_instructions=parsed_edit_instructions,
                additional_notes=additional_notes
            )

            if not optimized_data:
                print(f"[步骤 4/7] ❌ LLM 返回空数据")
                raise ValueError("LLM 优化失败，返回空数据")

            print(f"[步骤 4/7] ✅ LLM 优化成功")
            print(f"[步骤 4/7] 优化数据 keys: {list(optimized_data.keys())}")
            print(f"[步骤 4/7] 候选人姓名: {optimized_data.get('name', 'N/A')}")
            logger.info(f"[User {username}] 简历优化成功")

        except Exception as e:
            print(f"[步骤 4/7] ❌ LLM 优化失败: {e}")
            print(f"[步骤 4/7] 错误类型: {type(e).__name__}")
            import traceback
            print(f"[步骤 4/7] 错误堆栈:\n{traceback.format_exc()}")
            logger.error(f"[User {username}] LLM 优化失败: {e}")
            # 清理临时文件
            temp_file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=500,
                detail=f"简历优化失败: {str(e)}"
            )

        # ============================================================
        # 5. 生成优化后的 PDF
        # ============================================================
        print(f"[步骤 5/7] 生成优化后的 PDF...")
        try:
            # 创建输出目录
            output_dir = Path("data/outputs") / username / "optimized_resumes"
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[步骤 5/7] 输出目录: {output_dir}")

            # 生成文件名：简化命名，移除重复前缀
            original_name = Path(resume_file.filename).stem  # 去掉 .pdf 后缀
            # 🔴 移除已有的 Optimized_Resume_ 前缀，避免叠加
            clean_name = original_name
            while clean_name.startswith("Optimized_Resume_"):
                clean_name = clean_name[17:]  # len("Optimized_Resume_") = 17
            # 进一步清理：只保留核心名称（去除时间戳）
            import re
            clean_name = re.sub(r'_\d{8}_\d{4}$', '', clean_name)  # 移除 _20260205_0359 格式
            if not clean_name:
                clean_name = "Resume"
            timestamp = datetime.now().strftime("%m%d_%H%M")
            pdf_filename = f"Resume_{clean_name}_{timestamp}.pdf"
            pdf_path = output_dir / pdf_filename
            print(f"[步骤 5/7] PDF 路径: {pdf_path}")

            # 生成 PDF (异步调用)
            print(f"[步骤 5/7] 调用 generate_resume_pdf...")
            await generate_resume_pdf(
                resume_data=optimized_data,
                output_path=str(pdf_path)
            )

            print(f"[步骤 5/7] ✅ PDF 生成成功: {pdf_path}")
            logger.info(f"[User {username}] PDF 生成成功: {pdf_path}")

        except Exception as e:
            print(f"[步骤 5/7] ❌ PDF 生成失败: {e}")
            print(f"[步骤 5/7] 错误类型: {type(e).__name__}")
            import traceback
            print(f"[步骤 5/7] 错误堆栈:\n{traceback.format_exc()}")
            logger.error(f"[User {username}] PDF 生成失败: {e}")
            # 清理临时文件
            temp_file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=500,
                detail=f"PDF 生成失败: {str(e)}"
            )

        # ============================================================
        # 6. 保存优化历史记录
        # ============================================================
        print(f"[步骤 6/7] 保存优化历史记录...")
        try:
            from core.optimizer_history_manager import OptimizerHistoryManager

            history_mgr = OptimizerHistoryManager(user_id=user_id)
            history_mgr.add_record(
                original_filename=resume_file.filename,
                optimized_pdf_path=str(pdf_path),
                permanent_resident=permanent_resident,
                available_immediately=available_immediately,
                linkedin_url=linkedin_url,
                github_url=github_url,
                portfolio_url=portfolio_url,
                target_profile=target_profile,
                edit_instructions=parsed_edit_instructions,
                additional_notes=additional_notes
            )
            print(f"[步骤 6/7] ✅ 优化历史已保存")
            logger.info(f"[User {username}] 优化历史已保存")

        except Exception as e:
            print(f"[步骤 6/7] ⚠️ 保存优化历史失败: {e}")
            logger.warning(f"[User {username}] 保存优化历史失败: {e}")
            # 不影响主流程，继续执行

        # ============================================================
        # 7. 清理临时文件
        # ============================================================
        print(f"[步骤 7/7] 清理临时文件...")
        temp_file_path.unlink(missing_ok=True)
        print(f"[步骤 7/7] ✅ 临时文件已清理")
        logger.info(f"[User {username}] 临时文件已清理")

        # ============================================================
        # 8. 返回优化结果
        # ============================================================
        print(f"[完成] 简历优化全部完成")
        print(f"[完成] PDF 路径: {pdf_path}")
        print(f"=" * 80)
        return OptimizeResumeResponse(
            success=True,
            message="简历优化成功",
            pdf_path=str(pdf_path),
            optimized_data=optimized_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[User {current_user.username}] 简历优化异常")
        raise HTTPException(
            status_code=500,
            detail=f"简历优化过程中发生错误: {str(e)}"
        )


@router.get("/resume/download/{filename}")
async def download_optimized_resume(
    filename: str,
    current_user: dict = Depends(get_current_user)
):
    """
    下载优化后的简历PDF

    **参数**：
    - `filename`: PDF文件名

    **返回**：
    - PDF 文件流
    """
    try:
        username = current_user.username

        # 构建文件路径
        file_path = Path("data/outputs") / username / "optimized_resumes" / filename

        # 验证文件存在
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail="文件不存在"
            )

        # 返回文件
        return FileResponse(
            path=str(file_path),
            media_type="application/pdf",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[User {current_user.username}] 下载文件异常")
        raise HTTPException(
            status_code=500,
            detail=f"下载文件失败: {str(e)}"
        )
