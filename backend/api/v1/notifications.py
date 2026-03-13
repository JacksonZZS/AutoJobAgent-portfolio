"""
通知 API 路由
提供通知偏好设置和 Web Push 订阅功能
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pathlib import Path
import json
from typing import Optional

# 导入认证依赖
from backend.api.v1.auth import get_current_user
from backend.models.schemas import (
    UserInfo,
    NotificationPreferences,
    UpdateNotificationPreferencesRequest,
    WebPushSubscription,
    MessageResponse
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# 通知偏好存储路径
PREFERENCES_DIR = Path("data/preferences")
PREFERENCES_DIR.mkdir(parents=True, exist_ok=True)


def get_preferences_path(user_id: str) -> Path:
    """获取用户通知偏好文件路径"""
    return PREFERENCES_DIR / f"notification_{user_id}.json"


def load_preferences(user_id: str) -> dict:
    """加载用户通知偏好"""
    path = get_preferences_path(user_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    # 返回默认设置
    return {
        "push_enabled": True,
        "email_enabled": False,
        "email_address": None,
        "high_score_threshold": 80,
        "notify_on_complete": True,
        "notify_on_error": True,
        "push_subscription": None
    }


def save_preferences(user_id: str, data: dict):
    """保存用户通知偏好"""
    path = get_preferences_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取通知偏好设置

    **功能**：
    - 返回用户的通知偏好设置
    - 包括推送开关、邮件开关、高分阈值等
    """

    prefs = load_preferences(str(current_user.id))

    return NotificationPreferences(
        push_enabled=prefs.get("push_enabled", True),
        email_enabled=prefs.get("email_enabled", False),
        email_address=prefs.get("email_address"),
        high_score_threshold=prefs.get("high_score_threshold", 80),
        notify_on_complete=prefs.get("notify_on_complete", True),
        notify_on_error=prefs.get("notify_on_error", True)
    )


@router.put("/preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    request: UpdateNotificationPreferencesRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    更新通知偏好设置

    **功能**：
    - 更新用户的通知偏好设置
    - 只更新传入的字段，其他字段保持不变
    """

    prefs = load_preferences(str(current_user.id))

    # 更新传入的字段
    if request.push_enabled is not None:
        prefs["push_enabled"] = request.push_enabled
    if request.email_enabled is not None:
        prefs["email_enabled"] = request.email_enabled
    if request.email_address is not None:
        prefs["email_address"] = request.email_address
    if request.high_score_threshold is not None:
        prefs["high_score_threshold"] = request.high_score_threshold
    if request.notify_on_complete is not None:
        prefs["notify_on_complete"] = request.notify_on_complete
    if request.notify_on_error is not None:
        prefs["notify_on_error"] = request.notify_on_error

    save_preferences(str(current_user.id), prefs)

    return NotificationPreferences(
        push_enabled=prefs.get("push_enabled", True),
        email_enabled=prefs.get("email_enabled", False),
        email_address=prefs.get("email_address"),
        high_score_threshold=prefs.get("high_score_threshold", 80),
        notify_on_complete=prefs.get("notify_on_complete", True),
        notify_on_error=prefs.get("notify_on_error", True)
    )


@router.post("/subscribe-push", response_model=MessageResponse)
async def subscribe_web_push(
    subscription: WebPushSubscription,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    订阅 Web Push 通知

    **功能**：
    - 保存用户的 Web Push 订阅信息
    - 用于后续发送浏览器推送通知
    """

    prefs = load_preferences(str(current_user.id))
    prefs["push_subscription"] = {
        "endpoint": subscription.endpoint,
        "keys": subscription.keys
    }
    save_preferences(str(current_user.id), prefs)

    return MessageResponse(
        message="Web Push 订阅成功",
        status="success",
        data={"endpoint": subscription.endpoint[:50] + "..."}
    )


@router.delete("/unsubscribe-push", response_model=MessageResponse)
async def unsubscribe_web_push(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    取消 Web Push 订阅

    **功能**：
    - 移除用户的 Web Push 订阅信息
    """

    prefs = load_preferences(str(current_user.id))
    prefs["push_subscription"] = None
    save_preferences(str(current_user.id), prefs)

    return MessageResponse(
        message="已取消 Web Push 订阅",
        status="success"
    )
