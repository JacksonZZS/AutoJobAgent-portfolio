# core/nodriver_stealth.py
"""
Nodriver 反爬浏览器 - 绕过 Cloudflare 2025
Nodriver 不使用 CDP 协议，更难被检测

支持功能：
- 绕过 Cloudflare
- 翻页抓取
- 职位详情获取
"""

import asyncio
import random
import logging
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

import nodriver as uc

logger = logging.getLogger(__name__)


class IndeedNodriverScraper:
    """
    Indeed 爬虫 - 基于 Nodriver
    支持翻页、职位列表、详情获取
    """

    def __init__(
        self,
        user_id: str = "default",
        country: str = "hk",
        headless: bool = False,
    ):
        self.user_id = user_id
        self.country = country
        self.headless = headless

        # Indeed 国家站点 URL
        self.country_urls = {
            "us": "https://www.indeed.com",
            "hk": "https://hk.indeed.com",
            "uk": "https://uk.indeed.com",
            "ca": "https://ca.indeed.com",
            "au": "https://au.indeed.com",
            "sg": "https://sg.indeed.com",
        }
        self.base_url = self.country_urls.get(country, "https://hk.indeed.com")

        # 浏览器配置
        self.profile_dir = Path.home() / ".nodriver_profile"
        self.browser = None
        self.page = None

    async def start(self):
        """启动浏览器"""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        config = uc.Config()
        config.headless = self.headless
        config.user_data_dir = str(self.profile_dir)

        self.browser = await uc.start(config)
        logger.info(f"[IndeedScraper] Browser started, profile: {self.profile_dir}")
        return self.browser

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.stop()
            logger.info("[IndeedScraper] Browser closed")

    async def search_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        搜索 Indeed 职位（单页）

        Args:
            keyword: 搜索关键词
            location: 工作地点（可选）
            page: 页码（从 1 开始）

        Returns:
            职位列表
        """
        if not self.browser:
            await self.start()

        jobs = []

        # Indeed 分页：start=0 是第1页，start=10 是第2页（每页约10-15个）
        start_offset = (page - 1) * 10

        # 构造搜索 URL
        search_url = f"{self.base_url}/jobs?q={keyword}"
        if location:
            search_url += f"&l={location}"
        if start_offset > 0:
            search_url += f"&start={start_offset}"

        logger.info(f"[IndeedScraper] 搜索第 {page} 页: {search_url}")

        try:
            # 访问搜索页
            self.page = await self.browser.get(search_url)
            await asyncio.sleep(5)

            # 等待 Cloudflare
            passed = await self._wait_for_cloudflare()
            if not passed:
                logger.warning("[IndeedScraper] Cloudflare 验证失败")
                return []

            # 获取职位数量
            job_count = await self.page.evaluate("document.querySelectorAll('[data-jk]').length")
            logger.info(f"[IndeedScraper] 第 {page} 页找到 {job_count} 个职位")

            if job_count == 0:
                return []

            # 提取职位信息
            for i in range(job_count):
                try:
                    job = await self._extract_job(i)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"[IndeedScraper] 提取职位 {i} 失败: {e}")

            logger.info(f"[IndeedScraper] 第 {page} 页成功提取 {len(jobs)} 个职位")

        except Exception as e:
            logger.error(f"[IndeedScraper] 搜索失败: {e}")

        return jobs

    async def _extract_job(self, index: int) -> Optional[Dict[str, Any]]:
        """提取单个职位信息"""
        try:
            # 职位 ID
            job_id = await self.page.evaluate(
                f"document.querySelectorAll('[data-jk]')[{index}].getAttribute('data-jk')"
            )

            # 标题
            title = await self.page.evaluate(f"""
                document.querySelectorAll('[data-jk]')[{index}].querySelector('span')?.innerText ||
                document.querySelectorAll('[data-jk]')[{index}].innerText ||
                'N/A'
            """)

            # 公司 - 从父级容器找
            company = await self.page.evaluate(f"""
                (function() {{
                    const link = document.querySelectorAll('[data-jk]')[{index}];
                    const card = link.closest('.job_seen_beacon, .cardOutline, .result, li, .css-1m4cuuf');
                    if (!card) return 'N/A';
                    const el = card.querySelector('[data-testid="company-name"], .company_location [data-testid="company-name"], .companyName');
                    return el ? el.innerText.trim() : 'N/A';
                }})()
            """)

            # 地点
            location = await self.page.evaluate(f"""
                (function() {{
                    const link = document.querySelectorAll('[data-jk]')[{index}];
                    const card = link.closest('.job_seen_beacon, .cardOutline, .result, li, .css-1m4cuuf');
                    if (!card) return 'N/A';
                    const el = card.querySelector('[data-testid="text-location"], .companyLocation');
                    return el ? el.innerText.trim() : 'N/A';
                }})()
            """)

            # 薪资
            salary = await self.page.evaluate(f"""
                (function() {{
                    const link = document.querySelectorAll('[data-jk]')[{index}];
                    const card = link.closest('.job_seen_beacon, .cardOutline, .result, li, .css-1m4cuuf');
                    if (!card) return null;
                    const el = card.querySelector('.salary-snippet-container, [class*="salary"]');
                    return el ? el.innerText.trim() : null;
                }})()
            """)

            job_url = f"{self.base_url}/viewjob?jk={job_id}"

            return {
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "job_url": job_url,
                "source": "indeed",
            }

        except Exception as e:
            logger.warning(f"[IndeedScraper] 提取职位失败: {e}")
            return None

    async def get_job_details(self, job_id: str) -> Optional[str]:
        """获取职位详情（JD）"""
        if not self.browser:
            await self.start()

        try:
            detail_url = f"{self.base_url}/viewjob?jk={job_id}"
            self.page = await self.browser.get(detail_url)
            await asyncio.sleep(3)

            jd_content = await self.page.evaluate("""
                (function() {
                    const jdEl = document.querySelector('#jobDescriptionText, .jobsearch-jobDescriptionText, [class*="jobDescription"]');
                    return jdEl ? jdEl.innerText.trim() : null;
                })()
            """)

            return jd_content

        except Exception as e:
            logger.error(f"[IndeedScraper] 获取详情失败: {e}")
            return None

    async def _wait_for_cloudflare(self, max_wait: int = 30) -> bool:
        """等待 Cloudflare 验证"""
        for i in range(max_wait):
            try:
                title = await self.page.evaluate("document.title")
                content = await self.page.evaluate("document.body.innerText.substring(0, 500)")

                cf_indicators = ["just a moment", "checking your browser", "cloudflare", "please wait", "verifying"]
                is_cf = any(ind in str(title).lower() or ind in str(content).lower() for ind in cf_indicators)

                if not is_cf:
                    return True
            except:
                pass
            await asyncio.sleep(1)

        return False


# ============================================================
# 测试函数
# ============================================================

async def manual_login():
    """手动登录 Indeed，保存 profile"""
    print("=" * 60)
    print("🔐 Indeed Manual Login - Save Profile")
    print("=" * 60)

    profile_dir = Path.home() / ".nodriver_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    config = uc.Config()
    config.headless = False
    config.user_data_dir = str(profile_dir)

    print(f"\n📂 Profile dir: {profile_dir}")
    print("🚀 Starting browser...")

    browser = await uc.start(config)

    print("📌 Opening Indeed login page...")
    page = await browser.get("https://secure.indeed.com/account/login")
    await asyncio.sleep(3)

    print("\n" + "=" * 60)
    print("👆 Please login manually in the browser!")
    print("   After login, press ENTER here to continue...")
    print("=" * 60)

    input("\n>>> Press ENTER after you logged in: ")

    print("\n🔍 Verifying login status...")
    page = await browser.get("https://hk.indeed.com/")
    await asyncio.sleep(3)

    try:
        title = await page.evaluate("document.title")
        print(f"   Page title: {title}")
        print("\n✅ Profile saved!")
        print(f"   Location: {profile_dir}")
        print("\n   Now run: python -m core.nodriver_stealth")
    except Exception as e:
        print(f"\n⚠️ Error: {e}")
        print("   Profile saved anyway. Try running the test.")

    await asyncio.sleep(2)
    browser.stop()


async def test_pagination():
    """测试翻页功能"""
    print("=" * 60)
    print("🚀 Indeed Pagination Test")
    print("=" * 60)

    profile_dir = Path.home() / ".nodriver_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    config = uc.Config()
    config.headless = False
    config.user_data_dir = str(profile_dir)

    print(f"\n📂 Profile dir: {profile_dir}")
    print("🚀 Starting browser...")

    browser = await uc.start(config)
    print("✅ Browser started")

    try:
        all_jobs = []
        base_url = "https://hk.indeed.com"

        # 测试前 3 页
        for page_num in range(1, 4):
            print(f"\n📄 第 {page_num} 页:")
            print("-" * 40)

            # Indeed 分页：start=0 是第1页，start=10 是第2页
            start_offset = (page_num - 1) * 10
            search_url = f"{base_url}/jobs?q=data+analyst&l=Hong+Kong"
            if start_offset > 0:
                search_url += f"&start={start_offset}"

            print(f"   URL: {search_url}")

            # 访问搜索页
            page = await browser.get(search_url)
            await asyncio.sleep(5)

            # 等待 Cloudflare
            passed = False
            for i in range(15):
                try:
                    title = await page.evaluate("document.title")
                    if "indeed" in title.lower() and "moment" not in title.lower():
                        passed = True
                        break
                except:
                    pass
                await asyncio.sleep(1)

            if not passed:
                print(f"   ⚠️ Cloudflare 验证失败")
                continue

            # 获取职位数量
            job_count = await page.evaluate("document.querySelectorAll('[data-jk]').length")
            print(f"   找到 {job_count} 个职位")

            if job_count == 0:
                print(f"   ⚠️ 第 {page_num} 页无更多职位，停止翻页")
                break

            # 提取职位信息
            jobs = []
            for i in range(min(job_count, 15)):
                try:
                    job_id = await page.evaluate(f"document.querySelectorAll('[data-jk]')[{i}].getAttribute('data-jk')")

                    title = await page.evaluate(f"""
                        document.querySelectorAll('[data-jk]')[{i}].querySelector('span')?.innerText ||
                        document.querySelectorAll('[data-jk]')[{i}].innerText || 'N/A'
                    """)

                    company = await page.evaluate(f"""
                        (function() {{
                            const link = document.querySelectorAll('[data-jk]')[{i}];
                            const card = link.closest('.job_seen_beacon, .cardOutline, li');
                            if (!card) return 'N/A';
                            const el = card.querySelector('[data-testid="company-name"], .companyName');
                            return el ? el.innerText.trim() : 'N/A';
                        }})()
                    """)

                    location = await page.evaluate(f"""
                        (function() {{
                            const link = document.querySelectorAll('[data-jk]')[{i}];
                            const card = link.closest('.job_seen_beacon, .cardOutline, li');
                            if (!card) return 'N/A';
                            const el = card.querySelector('[data-testid="text-location"], .companyLocation');
                            return el ? el.innerText.trim() : 'N/A';
                        }})()
                    """)

                    jobs.append({
                        'job_id': job_id,
                        'title': title,
                        'company': company,
                        'location': location,
                    })
                except Exception as e:
                    print(f"   ⚠️ 提取职位 {i} 失败: {e}")

            # 显示前 5 个
            for job in jobs[:5]:
                print(f"   • {job['title']}")
                print(f"     🏢 {job['company']} | 📍 {job['location']}")

            all_jobs.extend(jobs)

            # 页间延迟
            await asyncio.sleep(2)

        print("\n" + "=" * 60)
        print(f"✅ 总计抓取 {len(all_jobs)} 个职位")
        print("=" * 60)

        # 显示所有职位 ID（去重检查）
        job_ids = [j['job_id'] for j in all_jobs]
        unique_ids = set(job_ids)
        print(f"   唯一职位 ID: {len(unique_ids)} 个")
        if len(job_ids) != len(unique_ids):
            print(f"   ⚠️ 有 {len(job_ids) - len(unique_ids)} 个重复")

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        browser.stop()


async def test_nodriver():
    """测试 Nodriver（保留原有测试）"""
    print("=" * 60)
    print("🚀 Nodriver Stealth Test - Debug Mode")
    print("=" * 60)

    scraper = IndeedNodriverScraper(country="hk", headless=False)

    try:
        await scraper.start()

        print("\n[1/3] 搜索职位...")
        jobs = await scraper.search_jobs("data analyst", "Hong Kong", page=1)

        print(f"\n[2/3] 找到 {len(jobs)} 个职位:")
        print("-" * 60)
        for i, job in enumerate(jobs[:10], 1):
            print(f"   {i}. {job['title']}")
            print(f"      🏢 {job['company']}")
            print(f"      📍 {job['location']}")
            print(f"      💰 {job['salary'] or 'Not listed'}")
            print(f"      🔗 {job['job_url']}")
            print()

        # 获取前 3 个职位的详情
        if jobs:
            print("\n[3/3] 获取职位详情 (前 3 个):")
            print("=" * 60)
            for job in jobs[:3]:
                print(f"\n📌 {job['title']}")
                print(f"   🏢 {job['company']} | 📍 {job['location']}")
                print("-" * 60)

                jd = await scraper.get_job_details(job['job_id'])
                if jd:
                    for line in jd.split('\n')[:15]:
                        if line.strip():
                            print(f"   {line.strip()}")
                    print("   ... (truncated)")
                else:
                    print("   ⚠️ Could not extract JD")

        print("\n" + "=" * 60)
        print("✅ Test completed!")

    finally:
        await scraper.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "login":
            uc.loop().run_until_complete(manual_login())
        elif sys.argv[1] == "pages":
            uc.loop().run_until_complete(test_pagination())
        else:
            print("Usage: python -m core.nodriver_stealth [login|pages]")
    else:
        uc.loop().run_until_complete(test_nodriver())
