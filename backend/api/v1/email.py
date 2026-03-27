"""
邮件 API - AI 生成跟进邮件/感谢信
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import os

from backend.api.v1.auth import get_current_user
from backend.models.schemas import UserInfo
from backend.services.email_service import email_service

router = APIRouter(prefix="/email", tags=["Email"])


# ==================== 数据模型 ====================

class GenerateEmailRequest(BaseModel):
    """生成邮件请求"""
    email_type: str = Field(..., description="邮件类型: follow_up / thank_you")
    job_title: str = Field(..., description="职位名称")
    company: str = Field(..., description="公司名称")
    recipient_name: str = Field("HR", description="收件人称呼")
    additional_context: Optional[str] = Field(None, description="额外上下文")


class GenerateEmailResponse(BaseModel):
    """生成邮件响应"""
    subject: str
    content: str


class SendEmailRequest(BaseModel):
    """发送邮件请求"""
    email_type: str = Field(..., description="邮件类型")
    recipient_email: EmailStr = Field(..., description="收件人邮箱")
    recipient_name: str = Field("HR", description="收件人称呼")
    job_title: str
    company: str
    content: str = Field(..., description="邮件正文")


class SendEmailResponse(BaseModel):
    """发送邮件响应"""
    success: bool
    message: str


# ==================== AI 生成函数 ====================

async def generate_follow_up_content(
    job_title: str,
    company: str,
    recipient_name: str,
    user_name: str,
    additional_context: Optional[str] = None
) -> str:
    """
    AI 生成跟进邮件内容
    TODO: 集成 Claude/GPT API
    """
    # 临时模板，后续可替换为 AI 生成
    content = f"""我是近期申请贵公司 {job_title} 职位的候选人。

我非常期待能够加入 {company}，并为团队贡献我的技能和经验。

我想跟进一下我的申请状态，不知道是否方便了解一下目前的招聘进度？

如果需要任何补充材料或有任何问题，我随时可以配合。

期待您的回复，祝工作顺利！"""

    if additional_context:
        content = f"{additional_context}\n\n{content}"
    
    return content


async def generate_thank_you_content(
    job_title: str,
    company: str,
    recipient_name: str,
    user_name: str,
    additional_context: Optional[str] = None
) -> str:
    """
    AI 生成感谢信内容
    TODO: 集成 Claude/GPT API
    """
    content = f"""非常感谢您今天抽出宝贵时间与我就 {job_title} 职位进行沟通。

通过今天的交流，我对 {company} 有了更深入的了解，也更加期待能够加入贵公司的团队。

我们讨论的项目和团队文化都让我印象深刻，我相信我的技能和经验能够为团队带来价值。

再次感谢您的时间和考虑，期待收到您的好消息！"""

    if additional_context:
        content = f"{additional_context}\n\n{content}"
    
    return content


# ==================== API 端点 ====================

@router.post("/generate", response_model=GenerateEmailResponse)
async def generate_email(
    request: GenerateEmailRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    AI 生成邮件内容
    """
    user_name = current_user.name or "申请人"
    
    if request.email_type == "follow_up":
        content = await generate_follow_up_content(
            job_title=request.job_title,
            company=request.company,
            recipient_name=request.recipient_name,
            user_name=user_name,
            additional_context=request.additional_context
        )
        subject = f"关于 {request.job_title} 职位申请跟进 - {user_name}"
    
    elif request.email_type == "thank_you":
        content = await generate_thank_you_content(
            job_title=request.job_title,
            company=request.company,
            recipient_name=request.recipient_name,
            user_name=user_name,
            additional_context=request.additional_context
        )
        subject = f"感谢信 - {request.job_title} 职位沟通 - {user_name}"
    
    else:
        raise HTTPException(status_code=400, detail="不支持的邮件类型")
    
    return GenerateEmailResponse(
        subject=subject,
        content=content
    )


@router.post("/send", response_model=SendEmailResponse)
async def send_email(
    request: SendEmailRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    发送邮件
    """
    user_name = current_user.name or "申请人"
    user_email = current_user.email
    
    job = {
        "title": request.job_title,
        "company": request.company
    }
    
    if request.email_type == "follow_up":
        success = await email_service.send_follow_up(
            user_email=user_email,
            user_name=user_name,
            job=job,
            content=request.content,
            recipient_email=request.recipient_email,
            recipient_name=request.recipient_name
        )
    elif request.email_type == "thank_you":
        success = await email_service.send_thank_you(
            user_email=user_email,
            user_name=user_name,
            job=job,
            content=request.content,
            recipient_email=request.recipient_email,
            recipient_name=request.recipient_name
        )
    else:
        raise HTTPException(status_code=400, detail="不支持的邮件类型")
    
    if success:
        return SendEmailResponse(success=True, message="邮件发送成功")
    else:
        return SendEmailResponse(success=False, message="邮件发送失败，请检查配置")


@router.get("/config")
async def get_email_config(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取邮件配置状态
    """
    return {
        "enabled": email_service.enabled,
        "smtp_configured": bool(email_service.smtp_user and email_service.smtp_password),
        "from_name": email_service.from_name
    }
