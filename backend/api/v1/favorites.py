"""
收藏 API 路由
提供职位收藏管理功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pathlib import Path
import json
from datetime import datetime
from typing import Optional

# 导入认证依赖
from backend.api.v1.auth import get_current_user
from backend.models.schemas import (
    UserInfo,
    FavoriteJob,
    AddFavoriteRequest,
    FavoritesListResponse,
    MessageResponse
)

router = APIRouter(prefix="/favorites", tags=["Favorites"])

# 收藏数据存储路径
FAVORITES_DIR = Path("data/favorites")
FAVORITES_DIR.mkdir(parents=True, exist_ok=True)


def get_favorites_path(user_id: str) -> Path:
    """获取用户收藏文件路径"""
    return FAVORITES_DIR / f"favorites_{user_id}.json"


def load_favorites(user_id: str) -> dict:
    """加载用户收藏数据"""
    path = get_favorites_path(user_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_favorites(user_id: str, data: dict):
    """保存用户收藏数据"""
    path = get_favorites_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


@router.get("/", response_model=FavoritesListResponse)
async def get_favorites(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取收藏列表

    **功能**：
    - 分页返回用户收藏的职位列表
    - 按收藏时间倒序排列
    """

    favorites_data = load_favorites(str(current_user.id))

    # 转换为列表并解析时间
    items = []
    for job_id, record in favorites_data.items():
        try:
            favorited_at = datetime.fromisoformat(record.get("favorited_at", ""))
        except (ValueError, TypeError):  # 🔴 修复: 具体异常类型
            favorited_at = datetime.now()

        items.append(FavoriteJob(
            job_id=job_id,
            title=record.get("title", ""),
            company=record.get("company", ""),
            link=record.get("link", ""),
            score=record.get("score"),
            platform=record.get("platform"),
            notes=record.get("notes"),
            favorited_at=favorited_at
        ))

    # 按收藏时间倒序排列
    items.sort(key=lambda x: x.favorited_at, reverse=True)

    # 分页
    total = len(items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = items[start_idx:end_idx]

    return FavoritesListResponse(
        total=total,
        items=paginated_items
    )


@router.post("/{job_id}", response_model=MessageResponse)
async def add_to_favorites(
    job_id: str,
    request: AddFavoriteRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    添加职位到收藏

    **功能**：
    - 将指定职位添加到用户收藏列表
    - 如果已存在则更新信息
    """

    favorites_data = load_favorites(str(current_user.id))

    # 添加或更新收藏
    favorites_data[job_id] = {
        "title": request.title,
        "company": request.company,
        "link": request.link,
        "score": request.score,
        "platform": request.platform,
        "notes": request.notes,
        "favorited_at": datetime.now().isoformat()
    }

    save_favorites(str(current_user.id), favorites_data)

    return MessageResponse(
        message=f"已收藏: {request.title}",
        status="success",
        data={"job_id": job_id}
    )


@router.delete("/{job_id}", response_model=MessageResponse)
async def remove_from_favorites(
    job_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    从收藏中移除职位

    **功能**：
    - 将指定职位从用户收藏列表中移除
    """

    favorites_data = load_favorites(str(current_user.id))

    if job_id not in favorites_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found"
        )

    job_title = favorites_data[job_id].get("title", "Unknown")
    del favorites_data[job_id]
    save_favorites(str(current_user.id), favorites_data)

    return MessageResponse(
        message=f"已取消收藏: {job_title}",
        status="success",
        data={"job_id": job_id}
    )


@router.put("/{job_id}/notes", response_model=MessageResponse)
async def update_favorite_notes(
    job_id: str,
    notes: str = Query(..., max_length=1000, description="备注内容"),  # 🔴 修复: 添加长度限制
    current_user: UserInfo = Depends(get_current_user)
):
    """
    更新收藏备注

    **功能**：
    - 更新收藏职位的备注信息
    """

    favorites_data = load_favorites(str(current_user.id))

    if job_id not in favorites_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found"
        )

    favorites_data[job_id]["notes"] = notes
    save_favorites(str(current_user.id), favorites_data)

    return MessageResponse(
        message="备注已更新",
        status="success",
        data={"job_id": job_id, "notes": notes}
    )
