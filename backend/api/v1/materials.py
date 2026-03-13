"""
物料中心 API 路由
提供生成的简历、求职信下载和预览功能
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pathlib import Path
import base64

# 导入核心业务模块
from core.status_manager import get_status_manager

# 导入认证依赖
from backend.api.v1.auth import get_current_user
from backend.models.schemas import (
    UserInfo,
    PendingMaterialResponse,
    ManualReviewData,
    DimensionScore,
    UpdateCoverLetterRequest,
    UpdateCoverLetterResponse,
    MessageResponse
)

router = APIRouter(prefix="/materials", tags=["Material Center"])


# ============================================================
# API 端点
# ============================================================

@router.get("/pending", response_model=PendingMaterialResponse)
async def get_pending_materials(current_user: UserInfo = Depends(get_current_user)):
    """
    获取待审核的物料

    **功能**：
    - 检查是否有待人工复核的职位
    - 返回生成的简历和求职信信息
    - 前端用于显示人工复核弹窗
    """

    status_mgr = get_status_manager(str(current_user.id))
    status_data = status_mgr.read_status()

    # 检查是否有待审核任务
    if status_data.get("status") != "manual_review":
        return PendingMaterialResponse(
            has_pending=False,
            material_data=None
        )

    # 获取人工复核数据
    review_data = status_data.get("manual_review_data")
    if not review_data:
        return PendingMaterialResponse(
            has_pending=False,
            material_data=None
        )

    # 转换 dimensions
    dimensions = []
    for dim in review_data.get("dimensions", []):
        dimensions.append(DimensionScore(**dim))

    material_data = ManualReviewData(
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

    return PendingMaterialResponse(
        has_pending=True,
        material_data=material_data
    )


@router.get("/download/{file_type}/{filename}")
async def download_material(
    file_type: str,
    filename: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    下载生成的物料文件

    **参数**：
    - file_type: resume (简历) 或 cover_letter (求职信)
    - filename: 文件名

    **安全性**：
    - 仅允许下载当前用户的文件
    - 验证文件路径，防止路径遍历攻击
    """

    # 验证文件类型
    if file_type not in ["resume", "cover_letter"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Must be 'resume' or 'cover_letter'"
        )

    # 🔴 安全修复: 清洗 filename 防止路径遍历
    # 允许中文、空格、常见字符，但禁止 .. 和 / \
    import re
    import urllib.parse

    # 先 URL 解码
    filename = urllib.parse.unquote(filename)

    # 检查危险字符
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename: path traversal detected")

    if not filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid filename: must be PDF")

    # 构造用户目录路径（使用用户名，不是 user_id）
    base_dir = Path("data/outputs") / current_user.username

    # 🔴 修复：递归搜索用户目录下的文件
    file_path = None
    if base_dir.exists():
        for found_file in base_dir.rglob(filename):
            file_path = found_file
            break

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {filename}"
        )

    # 验证文件路径（防止路径遍历攻击）
    try:
        file_path = file_path.resolve()
        base_dir_resolved = base_dir.resolve()

        if not str(file_path).startswith(str(base_dir_resolved)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Path traversal detected"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path"
        )

    # 返回文件
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/pdf"
    )


@router.get("/preview/{file_type}/{filename}")
async def preview_material(
    file_type: str,
    filename: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    预览物料文件（直接返回 PDF 文件流）

    **用途**：
    - 前端 react-pdf 可直接渲染
    - 在浏览器中内嵌显示 PDF
    """
    import urllib.parse

    # 验证文件类型
    if file_type not in ["resume", "cover_letter"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type"
        )

    # URL 解码文件名
    filename = urllib.parse.unquote(filename)

    # 检查危险字符
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename: path traversal detected")

    # 构造用户目录路径（使用用户名）
    base_dir = Path("data/outputs") / current_user.username

    # 递归搜索用户目录下的文件
    file_path = None
    if base_dir.exists():
        for found_file in base_dir.rglob(filename):
            file_path = found_file
            break

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {filename}"
        )

    # 验证文件路径（防止路径遍历攻击）
    try:
        file_path = file_path.resolve()
        base_dir_resolved = base_dir.resolve()

        if not str(file_path).startswith(str(base_dir_resolved)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Path traversal detected"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path"
        )

    # 🔴 修复：直接返回 PDF 文件流，让 react-pdf 可以渲染
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"}  # inline 而不是 attachment
    )


# ============================================================
# 简历反馈重新生成 API
# ============================================================

from pydantic import BaseModel

class RegenerateResumeRequest(BaseModel):
    feedback: str

class RegenerateResumeResponse(BaseModel):
    message: str
    new_resume_path: str

@router.post("/regenerate-resume", response_model=RegenerateResumeResponse)
async def regenerate_resume(
    request: RegenerateResumeRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    根据用户反馈重新生成简历

    **功能**：
    - 接收用户反馈
    - 调用 LLM 重新生成简历
    - 生成新的 PDF
    - 返回新的简历路径
    """
    from core.resume_generator import regenerate_resume_with_feedback

    status_mgr = get_status_manager(str(current_user.id))
    status_data = status_mgr.read_status()

    review_data = status_data.get("manual_review_data", {})

    if not review_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending review data"
        )

    old_resume_path = review_data.get("resume_path", "")
    if not old_resume_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume path found"
        )

    try:
        # 调用 LLM 重新生成简历
        new_resume_path = await regenerate_resume_with_feedback(
            user_id=str(current_user.id),
            username=current_user.username,
            feedback=request.feedback,
            old_resume_path=old_resume_path,
            job_info={
                "title": review_data.get("job_title", ""),
                "company": review_data.get("company_name", ""),
                "url": review_data.get("job_url", "")
            }
        )

        # 更新状态中的 resume_path
        review_data["resume_path"] = new_resume_path
        status_data["manual_review_data"] = review_data
        status_mgr._write_status(status_data)

        return RegenerateResumeResponse(
            message="简历已根据反馈重新生成",
            new_resume_path=new_resume_path
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重新生成简历失败: {str(e)}"
        )


# ============================================================
# Cover Letter 编辑 API
# ============================================================

@router.get("/cover-letter/{job_id}")
async def get_cover_letter_text(
    job_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取求职信文本内容

    **功能**：
    - 返回指定职位的求职信文本
    - 用于前端编辑器预加载
    """
    status_mgr = get_status_manager(str(current_user.id))
    status_data = status_mgr.read_status()

    review_data = status_data.get("manual_review_data", {})

    if review_data.get("job_id") != job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover letter not found for this job"
        )

    return {
        "job_id": job_id,
        "cl_text": review_data.get("cl_text", ""),
        "cl_path": review_data.get("cl_path", "")
    }


@router.put("/cover-letter/{job_id}", response_model=UpdateCoverLetterResponse)
async def update_cover_letter(
    job_id: str,
    request: UpdateCoverLetterRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    更新求职信内容

    **功能**：
    - 更新求职信文本
    - 重新生成 PDF
    - 返回新的 PDF 路径
    """
    from core.pdf_generator import generate_cover_letter_pdf

    status_mgr = get_status_manager(str(current_user.id))
    status_data = status_mgr.read_status()

    review_data = status_data.get("manual_review_data", {})

    if not review_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending review data"
        )

    # 获取原始 CL 路径
    old_cl_path = review_data.get("cl_path", "")

    if not old_cl_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cover letter path found"
        )

    try:
        # 重新生成 PDF (异步调用)
        await generate_cover_letter_pdf(
            cover_letter_text=request.cl_text,
            output_path=old_cl_path  # 覆盖原文件
        )
        new_cl_path = old_cl_path

        # 更新状态中的 cl_text
        review_data["cl_text"] = request.cl_text
        status_data["manual_review_data"] = review_data
        status_mgr._write_status(status_data)

        return UpdateCoverLetterResponse(
            message="求职信已更新",
            new_cl_path=new_cl_path
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update cover letter: {str(e)}"
        )
