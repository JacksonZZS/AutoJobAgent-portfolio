# core/indeed_bota.py
"""
Indeed 爬虫 - 使用 Botasaurus 绕过 Cloudflare
Botasaurus 专门为绕过反爬设计，声称比 undetected-chromedriver 更强
"""

import time
import random
from typing import List, Optional
from dataclasses import dataclass
from urllib.parse import urlencode
from pathlib import Path

from botasaurus.browser import browser, Driver
from botasaurus.soupify import soupify

from core.history_manager import HistoryManager

# Indeed 国家站点 URL 映射
INDEED_COUNTRY_URLS = {
    "us": "https://www.indeed.com",
    "hk": "https://hk.indeed.com",
    "uk": "https://uk.indeed.com",
    "ca": "https://ca.indeed.com",
    "au": "https://au.indeed.com",
    "sg": "https://sg.indeed.com",
}


@dataclass
class IndeedJob:
    """Indeed 职位信息"""
    job_id: str
    title: str
    company: str
    location: str
    job_url: str
    salary: Optional[str] = None
    jd_content: str = ""
    is_easy_apply: bool = False
    source: str = "indeed"


class IndeedBotaScraper:
    """
    Indeed 爬虫 - 使用 Botasaurus
    专门绕过 Cloudflare、DataDome 等反爬系统
    """

    def __init__(
        self,
        user_id: str,
        headless: bool = False,
        country: str = "hk",
    ):
        self.user_id = user_id
        self.headless = headless
        self.country = country
        self.base_url = INDEED_COUNTRY_URLS.get(country, "https://www.indeed.com")
        self.history = HistoryManager(user_id=user_id)

        # Profile 目录
        self.profile_dir = Path(__file__).parent.parent / "chrome_profile" / f"indeed_bota_{country}"
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    def search_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        page: int = 1,
    ) -> List[IndeedJob]:
        """搜索 Indeed 职位"""

        # 构建搜索 URL
        params = {
            "q": keyword,
            "start": (page - 1) * 10,
        }
        if location:
            params["l"] = location

        search_url = f"{self.base_url}/jobs?{urlencode(params)}"
        print(f"   🔍 Indeed Bota: {search_url}")

        # 使用 Botasaurus 的 browser 装饰器
        @browser(
            headless=self.headless,
            block_images=True,  # 加速加载
            reuse_driver=True,  # 复用浏览器
        )
        def scrape_jobs(driver: Driver, url: str) -> List[dict]:
            jobs_data = []

            try:
                # 访问搜索页
                driver.get(url)
                print("   ⏳ 等待页面加载...")

                # Botasaurus 会自动处理 Cloudflare
                time.sleep(random.uniform(3, 5))

                # 检查是否通过了 Cloudflare
                title = driver.title.lower()
                if "just a moment" in title or "cloudflare" in title:
                    print("   ⏳ Cloudflare 验证中，等待30秒...")
                    time.sleep(30)  # 等待更长时间让用户手动验证

                # 模拟滚动 - 使用正确的 API
                driver.run_js("window.scrollBy(0, 500)")
                time.sleep(1)
                driver.run_js("window.scrollBy(0, 500)")
                time.sleep(1)

                # 获取页面 HTML
                html = driver.page_html
                soup = soupify(html)

                # 解析职位卡片
                job_cards = soup.select('.jobsearch-ResultsList > li, [data-jk], .job_seen_beacon')
                print(f"   📦 找到 {len(job_cards)} 个职位卡片")

                for card in job_cards:
                    try:
                        job_data = self._parse_card_soup(card)
                        if job_data:
                            jobs_data.append(job_data)
                    except Exception as e:
                        continue

            except Exception as e:
                print(f"   ❌ 爬取失败: {e}")

            return jobs_data

        # 执行爬取
        try:
            jobs_data = scrape_jobs(search_url)

            # 转换为 IndeedJob 对象
            jobs = []
            for data in jobs_data:
                if not self.history.is_duplicate(data.get("job_id", "")):
                    jobs.append(IndeedJob(**data))

            print(f"   ✅ Indeed Bota 找到 {len(jobs)} 个有效职位")
            return jobs

        except Exception as e:
            print(f"   ❌ 搜索失败: {e}")
            return []

    def _parse_card_soup(self, card) -> Optional[dict]:
        """使用 BeautifulSoup 解析职位卡片"""
        try:
            # 获取职位标题
            title_elem = card.select_one('.jobTitle span, h2.jobTitle a, a.jcs-JobTitle')
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)
            if not title:
                return None

            # 获取 job_id
            job_id = None
            jk_elem = card.select_one('[data-jk]')
            if jk_elem:
                job_id = jk_elem.get('data-jk')

            link_elem = card.select_one('a[data-jk]')
            if link_elem and not job_id:
                job_id = link_elem.get('data-jk')

            if not job_id:
                import hashlib
                job_id = hashlib.md5(title.encode()).hexdigest()[:16]

            # 获取公司名称
            company = "Unknown Company"
            company_elem = card.select_one('[data-testid="company-name"], .companyName')
            if company_elem:
                company = company_elem.get_text(strip=True)

            # 获取地点
            location = ""
            location_elem = card.select_one('[data-testid="text-location"], .companyLocation')
            if location_elem:
                location = location_elem.get_text(strip=True)

            # 获取薪资
            salary = None
            salary_elem = card.select_one('.salary-snippet, [data-testid="attribute_snippet_testid"]')
            if salary_elem:
                salary = salary_elem.get_text(strip=True)

            # 构建职位 URL
            job_url = f"{self.base_url}/viewjob?jk={job_id}"

            return {
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "job_url": job_url,
                "salary": salary,
            }

        except Exception:
            return None

    def get_job_details(self, job_url: str) -> str:
        """获取职位详情 (JD)"""

        @browser(
            headless=self.headless,
            reuse_driver=True,
        )
        def scrape_jd(driver: Driver, url: str) -> str:
            try:
                driver.get(url)
                time.sleep(random.uniform(2, 3))

                html = driver.page_html
                soup = soupify(html)

                jd_elem = soup.select_one('#jobDescriptionText, .jobsearch-jobDescriptionText')
                if jd_elem:
                    return jd_elem.get_text(strip=True)

            except Exception as e:
                print(f"   ⚠️ 获取 JD 失败: {e}")

            return ""

        try:
            return scrape_jd(job_url)
        except Exception:
            return ""

    def close(self):
        """关闭（Botasaurus 自动管理浏览器）"""
        print("   🔒 Indeed Bota 已关闭")


# 测试函数
def test_indeed_bota():
    """测试 Indeed Bota 爬虫"""
    print("\n🚀 测试 Indeed Bota 爬虫 (Botasaurus)")
    print("=" * 50)

    scraper = IndeedBotaScraper(
        user_id="test",
        headless=False,
        country="hk",
    )

    try:
        jobs = scraper.search_jobs("data analyst", page=1)
        print(f"\n📊 找到 {len(jobs)} 个职位")

        for i, job in enumerate(jobs[:5], 1):
            print(f"\n{i}. {job.title}")
            print(f"   公司: {job.company}")
            print(f"   地点: {job.location}")
            print(f"   链接: {job.job_url}")

        if jobs:
            print(f"\n📖 获取第一个职位的 JD...")
            jd = scraper.get_job_details(jobs[0].job_url)
            print(f"   JD 长度: {len(jd)} 字符")
            if jd:
                print(f"   预览: {jd[:200]}...")

    finally:
        scraper.close()

    print("\n✅ 测试完成")


if __name__ == "__main__":
    test_indeed_bota()
