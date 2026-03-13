"""
历史记录 API 路由
提供投递历史查询、统计、导出功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from pathlib import Path
import csv
import io
from datetime import datetime, date
from typing import Optional, List

# 导入核心业务模块
from core.history_manager import HistoryManager

# 导入认证依赖
from backend.api.v1.auth import get_current_user
from backend.models.schemas import (
    UserInfo,
    JobHistoryItem,
    HistoryListResponse,
    HistoryStatisticsResponse,
    MessageResponse
)

router = APIRouter(prefix="/history", tags=["Job History"])


# ============================================================
# API 端点
# ============================================================

@router.get("/", response_model=HistoryListResponse)
async def get_job_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    status_filter: Optional[str] = Query(None, description="状态筛选：success/skipped/failed"),
    sort_by: str = Query("time", description="排序方式：time/score"),
    # 🔴 新增搜索过滤参数
    search: Optional[str] = Query(None, description="搜索关键词（匹配公司名或职位标题）"),
    company: Optional[str] = Query(None, description="按公司名精确筛选"),
    score_min: Optional[int] = Query(None, ge=0, le=100, description="最低分数"),
    score_max: Optional[int] = Query(None, ge=0, le=100, description="最高分数"),
    date_from: Optional[date] = Query(None, description="开始日期"),
    date_to: Optional[date] = Query(None, description="结束日期"),
    platform: Optional[str] = Query(None, description="平台筛选：jobsdb/indeed"),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取投递历史记录列表

    **功能**：
    - 分页查询历史记录
    - 按状态筛选（成功/跳过/失败）
    - 按时间或评分排序
    - 返回完整的职位信息和物料路径
    """

    history_mgr = HistoryManager(user_id=str(current_user.id))

    # 读取历史记录
    history_data = history_mgr.history

    # 转换为列表格式
    all_items = []
    for job_id, record in history_data.items():
        # 解析时间
        try:
            processed_at = datetime.fromisoformat(record.get("processed_at", datetime.now().isoformat()))
        except (ValueError, TypeError):  # 🔴 修复: 具体异常类型
            processed_at = datetime.now()

        item = JobHistoryItem(
            job_id=job_id,
            title=record.get("title", ""),
            company=record.get("company", ""),
            link=record.get("link", ""),
            status=record.get("status", ""),
            score=record.get("score"),
            reason=record.get("reason"),
            resume_path=record.get("resume_path"),
            cl_path=record.get("cl_path"),
            processed_at=processed_at
        )
        all_items.append(item)

    # 筛选（支持状态别名）
    if status_filter:
        # 状态别名映射：前端值 -> 后端可能的值
        status_aliases = {
            "applied": ["success", "applied"],  # "已投递" 匹配 success 或 applied
            "success": ["success", "applied"],
            "skipped_permanent": ["skipped_permanent"],  # 永久跳过
            "skip": ["skipped_temporary", "skipped_manual"],  # 暂时跳过
            "skipped": ["skipped_temporary", "skipped_manual"],
            "fail": ["fail", "failed", "error"],
            "failed": ["fail", "failed", "error"],
            "low_score": ["low_score", "skipped_low_score"],
        }
        filter_values = status_aliases.get(status_filter.lower(), [status_filter.lower()])
        all_items = [
            item for item in all_items
            if any(fv in item.status.lower() for fv in filter_values)
        ]

    # 🔴 新增：关键词搜索（匹配公司名或职位标题）
    if search:
        search_lower = search.lower()
        all_items = [
            item for item in all_items
            if search_lower in item.title.lower() or search_lower in item.company.lower()
        ]

    # 🔴 新增：按公司名精确筛选
    if company:
        company_lower = company.lower()
        all_items = [
            item for item in all_items
            if company_lower in item.company.lower()
        ]

    # 🔴 新增：按分数范围筛选
    if score_min is not None:
        all_items = [
            item for item in all_items
            if item.score is not None and item.score >= score_min
        ]
    if score_max is not None:
        all_items = [
            item for item in all_items
            if item.score is not None and item.score <= score_max
        ]

    # 🔴 新增：按日期范围筛选
    if date_from:
        date_from_dt = datetime.combine(date_from, datetime.min.time())
        all_items = [
            item for item in all_items
            if item.processed_at >= date_from_dt
        ]
    if date_to:
        date_to_dt = datetime.combine(date_to, datetime.max.time())
        all_items = [
            item for item in all_items
            if item.processed_at <= date_to_dt
        ]

    # 🔴 新增：按平台筛选
    if platform:
        platform_lower = platform.lower()
        all_items = [
            item for item in all_items
            if hasattr(item, 'platform') and item.platform and platform_lower in item.platform.lower()
        ]

    # 排序
    if sort_by == "score":
        all_items.sort(key=lambda x: x.score or 0, reverse=True)
    else:  # 默认按时间排序
        all_items.sort(key=lambda x: x.processed_at, reverse=True)

    # 分页
    total = len(all_items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = all_items[start_idx:end_idx]

    return HistoryListResponse(
        total=total,
        items=paginated_items,
        page=page,
        page_size=page_size
    )


@router.get("/statistics", response_model=HistoryStatisticsResponse)
async def get_statistics(current_user: UserInfo = Depends(get_current_user)):
    """
    获取投递历史统计数据

    **返回**：
    - 总计投递数
    - 成功投递数
    - 跳过数
    - 失败数
    """

    history_mgr = HistoryManager(user_id=str(current_user.id))
    stats = history_mgr.get_statistics()

    return HistoryStatisticsResponse(
        total=stats.get("total", 0),
        success=stats.get("success", 0),
        skipped=stats.get("skipped", 0),
        failed=stats.get("failed", 0)
    )


@router.delete("/clear", response_model=MessageResponse)
async def clear_history(
    status_filter: Optional[str] = Query(None, description="按状态清除：low_score/success/skip/fail，不传则清除全部"),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    清空投递历史记录

    **警告**：此操作不可逆！
    - 可按状态筛选清除（如只清除评分不足的记录）
    - 不传 status_filter 则清除全部
    - 不影响其他用户的数据
    """

    history_mgr = HistoryManager(user_id=str(current_user.id))

    original_count = len(history_mgr.history)

    if original_count == 0:
        return MessageResponse(
            message="历史记录已经是空的",
            status="success",
            data={"deleted_count": 0}
        )

    if status_filter:
        # 按状态筛选清除
        keys_to_delete = [
            job_id for job_id, record in history_mgr.history.items()
            if status_filter.lower() in record.get("status", "").lower()
        ]
        for job_id in keys_to_delete:
            del history_mgr.history[job_id]
        deleted_count = len(keys_to_delete)
        history_mgr._save_history()

        status_names = {
            "low_score": "评分不足",
            "success": "已投递",
            "applied": "已投递",
            "skip": "已跳过",
            "fail": "失败"
        }
        status_name = status_names.get(status_filter, status_filter)
        message = f"已清除 {deleted_count} 条「{status_name}」记录"
    else:
        # 清除全部
        deleted_count = original_count
        history_mgr.history = {}
        history_mgr._save_history()
        message = f"已清除全部 {deleted_count} 条记录"

    return MessageResponse(
        message=message,
        status="success",
        data={"deleted_count": deleted_count}
    )


@router.get("/export")
async def export_history_csv(
    status_filter: Optional[str] = Query(None, description="状态筛选"),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    导出历史记录为 CSV 文件

    **功能**：
    - 导出所有历史记录到 CSV 格式
    - 可选择性筛选状态
    - 包含完整的职位信息和评分
    """

    history_mgr = HistoryManager(user_id=str(current_user.id))
    history_data = history_mgr.history

    # 准备 CSV 数据
    output = io.StringIO()
    writer = csv.writer(output)

    # 写入表头
    writer.writerow([
        "Job ID",
        "Job Title",
        "Company",
        "Job URL",
        "Status",
        "Score",
        "Reason",
        "Processed At"
    ])

    # 🔴 安全修复: 防止 CSV 公式注入
    def sanitize_csv_value(value) -> str:
        """防止 Excel 公式注入，对特殊字符开头的值加前缀"""
        str_val = str(value) if value is not None else ""
        if str_val.startswith(('=', '+', '-', '@', '\t', '\r')):
            return "'" + str_val
        return str_val

    # 写入数据
    for job_id, record in history_data.items():
        # 状态筛选
        if status_filter and status_filter.lower() not in record.get("status", "").lower():
            continue

        writer.writerow([
            sanitize_csv_value(job_id),
            sanitize_csv_value(record.get("title", "")),
            sanitize_csv_value(record.get("company", "")),
            sanitize_csv_value(record.get("link", "")),
            sanitize_csv_value(record.get("status", "")),
            sanitize_csv_value(record.get("score", "")),
            sanitize_csv_value(record.get("reason", "")),
            sanitize_csv_value(record.get("processed_at", ""))
        ])

    # 返回 CSV 文件
    output.seek(0)
    filename = f"job_history_{current_user.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
