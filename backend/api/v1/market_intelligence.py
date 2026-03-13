# backend/api/v1/market_intelligence.py
"""
Market Intelligence API
Provides aggregated job market analysis: skill demand, salary distribution,
company activity, title trends, location distribution, score distribution, daily trends.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from core.history_manager import HistoryManager
from core.market_analyzer import analyze_market, aggregate_skill_demand, aggregate_salary_distribution
from backend.api.v1.auth import get_current_user
from backend.models.schemas import (
    UserInfo,
    MarketIntelligenceResponse,
)

router = APIRouter(prefix="/market-intelligence", tags=["Market Intelligence"])


@router.get("/overview", response_model=MarketIntelligenceResponse)
async def get_market_overview(
    days: Optional[int] = Query(None, ge=1, le=365, description="Filter to recent N days"),
    current_user: UserInfo = Depends(get_current_user),
):
    """Full market intelligence analysis across all historical job data."""
    history_mgr = HistoryManager(user_id=str(current_user.id))
    result = analyze_market(history_mgr.history, days=days)
    return result


@router.get("/skills")
async def get_skill_demand(
    top_n: int = Query(20, ge=1, le=50, description="Number of top skills to return"),
    current_user: UserInfo = Depends(get_current_user),
):
    """Top N in-demand skills extracted from job descriptions."""
    history_mgr = HistoryManager(user_id=str(current_user.id))
    jobs = list(history_mgr.history.values())
    skills = aggregate_skill_demand(jobs)
    return {"skills": skills[:top_n], "total_jobs": len(jobs)}


@router.get("/salary")
async def get_salary_distribution(
    current_user: UserInfo = Depends(get_current_user),
):
    """Salary distribution grouped by job type."""
    history_mgr = HistoryManager(user_id=str(current_user.id))
    jobs = list(history_mgr.history.values())
    salary = aggregate_salary_distribution(jobs)
    return {"salary_distribution": salary, "total_jobs": len(jobs)}
