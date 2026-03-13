# core/jobspy_scraper.py
"""
JobSpy 集成模块 - 多平台职位爬取
支持 LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from jobspy import scrape_jobs

from core.history_manager import HistoryManager

logger = logging.getLogger(__name__)


@dataclass
class UnifiedJob:
    """统一的职位数据模型"""
    job_id: str
    title: str
    company: str
    location: str
    job_url: str
    source: str  # linkedin, indeed, glassdoor, google, ziprecruiter
    salary: Optional[str] = None
    description: Optional[str] = None
    date_posted: Optional[str] = None
    job_type: Optional[str] = None
    is_remote: bool = False
    scraped_at: str = ""

    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class JobSpyScraper:
    """
    JobSpy 多平台爬虫

    使用协议层逆向技术，不需要浏览器：
    - LinkedIn: Guest API
    - Indeed: GraphQL API
    - Glassdoor: Graph API + CSRF
    - ZipRecruiter: REST API
    """

    SUPPORTED_SITES = ["linkedin", "indeed", "glassdoor", "google", "zip_recruiter"]

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.history = HistoryManager(user_id=user_id)

    def search_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        sites: Optional[List[str]] = None,
        results_wanted: int = 50,
        hours_old: int = 72,
        country: str = "Hong Kong",
        easy_apply: bool = False,
        fetch_description: bool = True,
    ) -> List[UnifiedJob]:
        """
        搜索多平台职位

        Args:
            keyword: 搜索关键词
            location: 工作地点
            sites: 要搜索的平台列表，默认全部
            results_wanted: 每个平台想要的结果数
            hours_old: 只获取多少小时内的职位
            country: 国家（用于 Indeed/Glassdoor）
            easy_apply: 只获取一键投递职位
            fetch_description: 是否获取完整 JD（会慢一些）

        Returns:
            统一格式的职位列表
        """
        sites = sites or ["linkedin", "indeed"]

        logger.info(f"搜索职位: {keyword} @ {location}, 平台: {sites}")
        print(f"🔍 搜索: {keyword} @ {location or 'Any'}")
        print(f"📡 平台: {', '.join(sites)}")

        try:
            # 调用 JobSpy
            df = scrape_jobs(
                site_name=sites,
                search_term=keyword,
                location=location or "",
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed=country,
                easy_apply=easy_apply,
                linkedin_fetch_description=fetch_description,
                verbose=0,  # 减少输出
            )

            if df is None or df.empty:
                logger.warning("JobSpy 没有返回结果")
                print("❌ 没有找到职位")
                return []

            # 转换为统一格式
            jobs = []
            for _, row in df.iterrows():
                job_id = str(row.get("id", ""))

                # 跳过已投递的职位
                if self.history.is_processed(job_id):
                    continue

                # 处理薪资
                salary = None
                if row.get("min_amount") and row.get("max_amount"):
                    interval = row.get("interval", "yearly")
                    currency = row.get("currency", "USD")
                    salary = f"{currency} {row['min_amount']}-{row['max_amount']}/{interval}"

                # 处理地点
                location_str = ""
                if row.get("location"):
                    loc = row["location"]
                    if hasattr(loc, "city") and loc.city:
                        location_str = f"{loc.city}, {loc.state or ''}"
                    else:
                        location_str = str(loc)

                job = UnifiedJob(
                    job_id=job_id,
                    title=str(row.get("title", "")),
                    company=str(row.get("company", "")),
                    location=location_str,
                    job_url=str(row.get("job_url", "")),
                    source=str(row.get("site", "")),
                    salary=salary,
                    description=str(row.get("description", "")) if row.get("description") else None,
                    date_posted=str(row.get("date_posted", "")) if row.get("date_posted") else None,
                    job_type=str(row.get("job_type", "")) if row.get("job_type") else None,
                    is_remote=bool(row.get("is_remote", False)),
                )
                jobs.append(job)

            print(f"✅ 找到 {len(jobs)} 个职位")
            logger.info(f"找到 {len(jobs)} 个职位")
            return jobs

        except Exception as e:
            logger.error(f"JobSpy 爬取失败: {e}")
            print(f"❌ 爬取失败: {e}")
            return []

    def search_linkedin(
        self,
        keyword: str,
        location: Optional[str] = None,
        results_wanted: int = 50,
        hours_old: int = 72,
    ) -> List[UnifiedJob]:
        """只搜索 LinkedIn"""
        return self.search_jobs(
            keyword=keyword,
            location=location,
            sites=["linkedin"],
            results_wanted=results_wanted,
            hours_old=hours_old,
        )

    def search_indeed(
        self,
        keyword: str,
        location: Optional[str] = None,
        results_wanted: int = 50,
        hours_old: int = 72,
        country: str = "Hong Kong",
    ) -> List[UnifiedJob]:
        """只搜索 Indeed"""
        return self.search_jobs(
            keyword=keyword,
            location=location,
            sites=["indeed"],
            results_wanted=results_wanted,
            hours_old=hours_old,
            country=country,
        )

    def search_all(
        self,
        keyword: str,
        location: Optional[str] = None,
        results_wanted: int = 25,
        hours_old: int = 72,
    ) -> List[UnifiedJob]:
        """搜索所有平台"""
        return self.search_jobs(
            keyword=keyword,
            location=location,
            sites=["linkedin", "indeed", "glassdoor", "google"],
            results_wanted=results_wanted,
            hours_old=hours_old,
        )


# 便捷函数
def search_jobs_multi(
    keyword: str,
    user_id: str = "default",
    location: Optional[str] = None,
    sites: Optional[List[str]] = None,
    results_wanted: int = 50,
) -> List[UnifiedJob]:
    """多平台职位搜索（便捷函数）"""
    scraper = JobSpyScraper(user_id=user_id)
    return scraper.search_jobs(
        keyword=keyword,
        location=location,
        sites=sites,
        results_wanted=results_wanted,
    )


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)
    print("=== JobSpy 多平台爬虫测试 ===\n")

    scraper = JobSpyScraper(user_id="test")

    # 测试 LinkedIn
    print("\n--- LinkedIn ---")
    jobs = scraper.search_linkedin(
        keyword="Data Analyst",
        location="Hong Kong",
        results_wanted=5,
    )

    for i, job in enumerate(jobs, 1):
        print(f"\n{i}. {job.title}")
        print(f"   公司: {job.company}")
        print(f"   地点: {job.location}")
        print(f"   来源: {job.source}")
        print(f"   链接: {job.job_url[:60]}...")
