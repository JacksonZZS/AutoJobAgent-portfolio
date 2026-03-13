import os
import sys
import asyncio
import random
from urllib.parse import quote
from pathlib import Path
from playwright.async_api import async_playwright

# 把根目录加入路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.history_manager import HistoryManager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

async def search_and_crawl_jobs(
    keyword: str,
    max_count: int = 200,  # 🔴 [修复] 提高默认值，抓取整页职位
    blacklist: list = None,
    title_exclusions: list = None,
    start_page: int = 1,
    user_id: str = None
):
    """
    【修正版】单页爬虫：
    1. 移除自动翻页 while 循环，只抓取 start_page 这一页
    2. 移除 "点击下一页" 的动作，配合主程序的步进式逻辑
    3. 保留所有高级反爬、多用户隔离和过滤逻辑
    """
    # ✅ 确保参数初始化
    if blacklist is None: blacklist = []
    if title_exclusions is None: title_exclusions = []

    # 🔴 强制要求 user_id：确保历史记录隔离
    if not user_id:
        raise ValueError("user_id is required for search_and_crawl_jobs to ensure history isolation")

    # 🔴 使用用户专属的 HistoryManager
    history = HistoryManager(user_id=user_id)

    # 🔴 [DEBUG] 打印调试信息
    print(f"DEBUG: 启动 Chrome (目标页码: {start_page})")
    print(f"DEBUG: 用户 ID: {user_id}")
    print(f"DEBUG: max_count 参数: {max_count}")  # 总目标数量（用于控制抓取页数）
    print(f"DEBUG: 预期行为: 本页抓取所有符合条件的职位")

    async with async_playwright() as p:
        context = None
        try:
            # 🔴 Master Profile 策略
            master_profile_dir = Path(BASE_DIR) / "data" / "browser_profiles" / "master"
            master_profile_dir.mkdir(parents=True, exist_ok=True)

            # 🔴 清理锁文件
            singleton_lock = master_profile_dir / "SingletonLock"
            singleton_socket = master_profile_dir / "SingletonSocket"
            if singleton_lock.exists():
                try:
                    singleton_lock.unlink()
                except: pass
            if singleton_socket.exists():
                try:
                    singleton_socket.unlink()
                except: pass

            print("🛡️ Using MASTER profile for shared search capability")
            
            # 启动浏览器上下文（使用 Playwright 自带的 Chromium，不影响系统 Chrome）
            context = await p.chromium.launch_persistent_context(
                str(master_profile_dir),
                # channel="chrome",  # 🔴 移除！不再使用系统 Chrome，避免冲突
                headless=False,
                devtools=False,
                args=[
                    '--headless=new',
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--remote-debugging-port=0',
                    '--disable-gpu',
                    '--disable-extensions'
                ],
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
                ignore_https_errors=True
            )

            # 注入反检测脚本
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            # 确保只有一个页面
            while len(context.pages) > 1:
                await context.pages[-1].close()
            page = context.pages[0]

            # 2. 导航逻辑
            print(f"🔍 正在抓取第 {start_page} 页: {keyword}")

            # 构造搜索 URL
            encoded_keyword = quote(keyword)
            base_url = f"https://hk.jobsdb.com/jobs?keywords={encoded_keyword}"
            search_url = f"{base_url}&page={start_page}" if start_page > 1 else base_url

            print(f"   📍 目标 URL: {search_url}")

            # 跳转
            try:
                await page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
                await asyncio.sleep(3)
            except Exception as e:
                print(f"   ❌ 页面加载失败: {str(e)[:100]}")
                await context.close()
                return []

            # 验证结果加载
            try:
                await page.wait_for_selector('article, [data-automation="jobCard"]', state="attached", timeout=15000)
            except:
                print(f"   ⚠️ 第 {start_page} 页似乎没有职位卡片或加载超时")
                await context.close()
                return []

            # ==================================================
            # 核心抓取逻辑 (仅针对当前页)
            # ==================================================
            results = []
            processed_links = set()
            
            # A. 抓取卡片
            articles = await page.locator('article').all()
            print(f"   - 本页发现 {len(articles)} 个职位卡片")
            print(f"   - 将抓取所有符合条件的职位（无单页限制）")

            for article in articles:
                try:
                    # 抓取链接
                    link_el = article.locator('h1 a, a[data-automation="jobTitle"]').first
                    raw_link = await link_el.get_attribute('href')
                    if not raw_link: continue

                    link = "https://hk.jobsdb.com" + raw_link if raw_link.startswith('/') else raw_link

                    # 1. 链接去重 (内存 + 历史记录)
                    if link in processed_links or history.is_processed(link):
                        processed_links.add(link)
                        continue

                    # 抓取标题
                    title_el = article.locator('h1, h3, [data-automation="jobTitle"]').first
                    title = await title_el.inner_text()

                    # 2. 标题排除词过滤
                    if title_exclusions:
                        if any(ex.lower() in title.lower() for ex in title_exclusions):
                            processed_links.add(link)
                            # print(f"   🚫 标题预筛掉: {title}")
                            continue

                    # 3. 黑名单过滤
                    if any(bad.lower() in title.lower() for bad in blacklist):
                        processed_links.add(link)
                        print(f"   🗑️ [过滤] 命中黑名单: {title}")
                        continue
                        
                    # 抓取公司名称
                    company = "Unknown"
                    try:
                        company_selectors = [
                            '[data-automation="jobCardCompanyLink"]',
                            'h2[class*="company"]',
                            'span[class*="company"]',
                            'a[data-automation="company-link"]',
                            '[data-automation="jobCompany"]'
                        ]
                        for selector in company_selectors:
                            co_el = article.locator(selector).first
                            if await co_el.count() > 0:
                                company = (await co_el.inner_text()).strip()
                                break
                    except: pass

                    results.append({"id": len(results)+1, "title": title, "company": company, "link": link})
                    processed_links.add(link)
                    print(f"   ✨ 入选: {title}")
                except: continue
            
            # ==================================================
            # 抓取 JD (深入详情页)
            # ==================================================
            if results:
                print(f"📊 本页有效职位 {len(results)} 个。开始抓取 JD...")
                for index, job in enumerate(results):
                    print(f"📖 [{index+1}/{len(results)}] 读取: {job['title']}...")
                    try:
                        await page.goto(job['link'], wait_until="domcontentloaded")
                        await page.wait_for_selector('[data-automation="jobAdDetails"], main', timeout=10000)
                        
                        jd_element = page.locator('[data-automation="jobAdDetails"], main').first
                        if await jd_element.count() > 0:
                            job['jd_content'] = await jd_element.inner_text()
                        else:
                            job['jd_content'] = ""
                        
                        await asyncio.sleep(random.uniform(1.5, 3)) # 稍微快一点
                    except Exception as e:
                        print(f"   ❌ 抓取 JD 失败: {e}")
                        job['jd_content'] = ""
            else:
                print("⚠️ 本页所有职位均已被过滤或去重。")

            print("🎉 本页任务结束！")
            await context.close()
            return results # 直接返回，不翻页
            
        except Exception as e:
            print(f"❌ 系统错误: {str(e)}")
            if context: await context.close()
            return []