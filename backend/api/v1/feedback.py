"""
反馈 API - PDF 预览反馈和重新生成
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import json
import os
from pathlib import Path

from backend.api.v1.auth import get_current_user
from backend.models.schemas import UserInfo

router = APIRouter(prefix="/feedback", tags=["Feedback"])

# 数据存储路径
FEEDBACK_DIR = Path("data/feedback")
VERSIONS_DIR = Path("data/versions")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
VERSIONS_DIR.mkdir(parents=True, exist_ok=True)


# ==================== 数据模型 ====================

class FeedbackRequest(BaseModel):
    """反馈请求"""
    resume_id: str = Field(..., description="简历 ID")
    job_id: Optional[str] = Field(None, description="职位 ID")
    feedback: str = Field(..., min_length=1, max_length=2000, description="反馈内容")
    selected_text: Optional[str] = Field(None, description="选中的文本")
    feedback_type: str = Field("general", description="反馈类型: content/format/language/general")


class FeedbackResponse(BaseModel):
    """反馈响应"""
    success: bool
    message: str
    new_version: Optional[int] = None
    pdf_url: Optional[str] = None


class VersionInfo(BaseModel):
    """版本信息"""
    version: int
    created_at: str
    feedback: Optional[str] = None


class VersionListResponse(BaseModel):
    """版本列表响应"""
    resume_id: str
    current_version: int
    versions: List[VersionInfo]


# ==================== 辅助函数 ====================

def get_feedback_path(user_id: str, resume_id: str) -> Path:
    """获取反馈历史文件路径"""
    return FEEDBACK_DIR / f"feedback_{user_id}_{resume_id}.json"


def get_versions_path(user_id: str, resume_id: str) -> Path:
    """获取版本历史文件路径"""
    return VERSIONS_DIR / f"versions_{user_id}_{resume_id}.json"


def load_feedback_history(user_id: str, resume_id: str) -> List[dict]:
    """加载反馈历史"""
    path = get_feedback_path(user_id, resume_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_feedback_history(user_id: str, resume_id: str, history: List[dict]):
    """保存反馈历史"""
    path = get_feedback_path(user_id, resume_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def load_versions(user_id: str, resume_id: str) -> dict:
    """加载版本信息"""
    path = get_versions_path(user_id, resume_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"current_version": 1, "versions": [{"version": 1, "created_at": datetime.now().isoformat()}]}


def save_versions(user_id: str, resume_id: str, versions: dict):
    """保存版本信息"""
    path = get_versions_path(user_id, resume_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)


async def regenerate_resume_with_feedback(
    user_id: str,
    resume_id: str,
    feedback: str,
    job_id: Optional[str] = None
) -> dict:
    """
    根据反馈重新生成简历
    TODO: 集成 AI 服务实现真正的重新生成
    """
    # 加载版本信息
    versions_data = load_versions(user_id, resume_id)
    current_version = versions_data.get("current_version", 1)
    new_version = current_version + 1
    
    # 创建新版本记录
    new_version_info = {
        "version": new_version,
        "created_at": datetime.now().isoformat(),
        "feedback": feedback[:200] if feedback else None  # 截取前200字符
    }
    
    versions_data["versions"].append(new_version_info)
    versions_data["current_version"] = new_version
    
    # 保存版本信息
    save_versions(user_id, resume_id, versions_data)
    
    # TODO: 调用 AI 服务重新生成简历
    # new_content = await ai_service.regenerate_resume(original_content, feedback)
    # pdf_path = await pdf_service.generate_pdf(new_content, f"v{new_version}")
    
    # 临时返回模拟结果
    pdf_url = f"/api/materials/resume/{resume_id}/pdf?version={new_version}"
    
    return {
        "new_version": new_version,
        "pdf_url": pdf_url
    }


# ==================== API 端点 ====================

@router.post("/regenerate", response_model=FeedbackResponse)
async def regenerate_with_feedback(
    request: FeedbackRequest,
    background_tasks: BackgroundTasks,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    根据反馈重新生成简历
    
    - 接收用户反馈
    - 调用 AI 重新生成
    - 返回新版本 PDF
    """
    user_id = str(current_user.id)
    
    try:
        # 保存反馈记录
        history = load_feedback_history(user_id, request.resume_id)
        history.append({
            "timestamp": datetime.now().isoformat(),
            "feedback": request.feedback,
            "selected_text": request.selected_text,
            "feedback_type": request.feedback_type,
            "job_id": request.job_id
        })
        save_feedback_history(user_id, request.resume_id, history)
        
        # 重新生成简历
        result = await regenerate_resume_with_feedback(
            user_id=user_id,
            resume_id=request.resume_id,
            feedback=request.feedback,
            job_id=request.job_id
        )
        
        return FeedbackResponse(
            success=True,
            message="简历已根据反馈重新生成",
            new_version=result["new_version"],
            pdf_url=result["pdf_url"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新生成失败: {str(e)}")


@router.get("/versions/{resume_id}", response_model=VersionListResponse)
async def get_versions(
    resume_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取简历的版本历史
    """
    user_id = str(current_user.id)
    
    versions_data = load_versions(user_id, resume_id)
    
    return VersionListResponse(
        resume_id=resume_id,
        current_version=versions_data.get("current_version", 1),
        versions=[
            VersionInfo(
                version=v["version"],
                created_at=v["created_at"],
                feedback=v.get("feedback")
            )
            for v in versions_data.get("versions", [])
        ]
    )


@router.get("/history/{resume_id}")
async def get_feedback_history(
    resume_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取反馈历史记录
    """
    user_id = str(current_user.id)
    history = load_feedback_history(user_id, resume_id)
    
    return {
        "resume_id": resume_id,
        "total": len(history),
        "history": history
    }


@router.delete("/history/{resume_id}")
async def clear_feedback_history(
    resume_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    清除反馈历史
    """
    user_id = str(current_user.id)
    path = get_feedback_path(user_id, resume_id)
    
    if path.exists():
        os.remove(path)
    
    return {"success": True, "message": "反馈历史已清除"}
