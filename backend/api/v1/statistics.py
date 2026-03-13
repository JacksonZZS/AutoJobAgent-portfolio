"""
统计 API 路由
提供投递数据统计、趋势分析、平台分布功能
"""

from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

# 导入核心业务模块
from core.history_manager import HistoryManager

# 导入认证依赖
from backend.api.v1.auth import get_current_user
from backend.models.schemas import (
    UserInfo,
    DashboardStatisticsResponse,
    TrendsResponse,
    TrendDataPoint,
    PlatformBreakdownResponse,
    PlatformBreakdownItem,
    PlatformStats
)

router = APIRouter(prefix="/statistics", tags=["Statistics"])


@router.get("/dashboard", response_model=DashboardStatisticsResponse)
async def get_dashboard_statistics(
    period: str = Query("all", description="统计周期: today/week/month/all"),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取仪表盘统计数据

    **功能**：
    - 总投递数、成功数、跳过数、失败数
    - 今日/本周/本月投递数
    - 成功率和平均匹配分
    - 按平台分类统计
    """

    history_mgr = HistoryManager(user_id=str(current_user.id))
    history_data = history_mgr.history

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    # 初始化计数器
    total = 0
    success = 0
    skipped = 0
    failed = 0
    today_count = 0
    week_count = 0
    month_count = 0
    total_score = 0
    score_count = 0
    platform_data = defaultdict(lambda: {"total": 0, "success": 0, "scores": []})

    for job_id, record in history_data.items():
        total += 1
        status = record.get("status", "").lower()
        score = record.get("score")
        platform = record.get("platform", "unknown")

        # 解析时间
        try:
            processed_at = datetime.fromisoformat(record.get("processed_at", ""))
        except:
            processed_at = now

        # 状态统计
        if status in ["success", "applied"]:
            success += 1
            platform_data[platform]["success"] += 1
        elif "skip" in status:
            skipped += 1
        elif status in ["fail", "failed", "error", "low_score"]:
            failed += 1

        # 时间段统计
        if processed_at >= today_start:
            today_count += 1
        if processed_at >= week_start:
            week_count += 1
        if processed_at >= month_start:
            month_count += 1

        # 分数统计
        if score is not None:
            total_score += score
            score_count += 1
            platform_data[platform]["scores"].append(score)

        # 平台统计
        platform_data[platform]["total"] += 1

    # 计算成功率和平均分
    success_rate = (success / total * 100) if total > 0 else 0.0
    avg_score = (total_score / score_count) if score_count > 0 else 0.0

    # 构建平台统计
    platform_stats = {}
    for platform, data in platform_data.items():
        platform_avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0.0
        platform_stats[platform] = PlatformStats(
            total=data["total"],
            success=data["success"],
            avg_score=round(platform_avg, 1)
        )

    return DashboardStatisticsResponse(
        total_applications=total,
        success_count=success,
        skip_count=skipped,
        failed_count=failed,
        today_count=today_count,
        week_count=week_count,
        month_count=month_count,
        success_rate=round(success_rate, 1),
        avg_score=round(avg_score, 1),
        platform_stats=platform_stats
    )


@router.get("/trends", response_model=TrendsResponse)
async def get_application_trends(
    days: int = Query(30, ge=7, le=90, description="统计天数"),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取投递趋势数据

    **功能**：
    - 返回指定天数内的每日投递数和成功数
    - 用于绘制趋势图
    """

    history_mgr = HistoryManager(user_id=str(current_user.id))
    history_data = history_mgr.history

    now = datetime.now()
    start_date = now - timedelta(days=days)

    # 初始化每日数据
    daily_data = {}
    for i in range(days):
        date_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        daily_data[date_str] = {"applications": 0, "success": 0}

    # 统计每日数据
    for job_id, record in history_data.items():
        try:
            processed_at = datetime.fromisoformat(record.get("processed_at", ""))
            date_str = processed_at.strftime("%Y-%m-%d")
            if date_str in daily_data:
                daily_data[date_str]["applications"] += 1
                if record.get("status", "").lower() in ["success", "applied"]:
                    daily_data[date_str]["success"] += 1
        except:
            continue

    # 转换为列表格式
    trend_data = [
        TrendDataPoint(
            date=date_str,
            applications=data["applications"],
            success=data["success"]
        )
        for date_str, data in sorted(daily_data.items())
    ]

    return TrendsResponse(data=trend_data)


@router.get("/platform-breakdown", response_model=PlatformBreakdownResponse)
async def get_platform_breakdown(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取平台分布数据

    **功能**：
    - 返回各平台的投递数量和百分比
    - 用于绘制饼图
    """

    history_mgr = HistoryManager(user_id=str(current_user.id))
    history_data = history_mgr.history

    platform_counts = defaultdict(int)
    total = 0

    for job_id, record in history_data.items():
        platform = record.get("platform", "unknown")
        platform_counts[platform] += 1
        total += 1

    # 构建分布数据
    platforms = []
    for platform, count in platform_counts.items():
        percentage = (count / total * 100) if total > 0 else 0.0
        platforms.append(PlatformBreakdownItem(
            platform=platform,
            count=count,
            percentage=round(percentage, 1)
        ))

    # 按数量排序
    platforms.sort(key=lambda x: x.count, reverse=True)

    return PlatformBreakdownResponse(platforms=platforms)
