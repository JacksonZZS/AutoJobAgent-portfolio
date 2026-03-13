import os
import json
import asyncio
import random
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

mcp = FastMCP("CareerAgent")

# 使用 Chrome 真实配置
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile")

@mcp.tool()
async def search_and_crawl_jobs(keyword: str, max_count: int = 5) -> str:
    """
    搜索并抓取职位详情 (修复公司名抓取逻辑 + 确保列表顺序)。
    """
    print(f"DEBUG: 启动 Chrome 抓取 (Profile: {USER_DATA_DIR})")

    async with async_playwright() as p:
        try:
            print("🚀 Launching Chrome...")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                channel="chrome",
                headless=False,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
                viewport={'width': 1280, 'height': 800}
            )
            
            while len(context.pages) > 1:
                await context.pages[-1].close()
            page = context.pages[0]
            
            print("🌍 打开首页...")
            await page.goto("https://hk.jobsdb.com/hk")
            await asyncio.sleep(2)

            # 2. 寻找输入框
            search_input = None
            possible_inputs = [
                'input[name="keywords"]',
                'input[id="searchKeywordsField"]',
                'input[data-automation="searchKeywordsField"]'
            ]
            
            for selector in possible_inputs:
                if await page.locator(selector).count() > 0:
                    search_input = page.locator(selector).first
                    break
            
            if not search_input:
                await context.close()
                return "Error: 找不到搜索框。"

            # 清空并输入
            await search_input.click()
            await search_input.fill("")
            await asyncio.sleep(0.5)
            
            print(f"⌨️ 输入关键词: {keyword}")
            await page.keyboard.type(keyword, delay=100)
            await asyncio.sleep(1)

            # 3. 点击搜索
            print("👆 点击搜索...")
            search_button = None
            button_selectors = [
                'button[data-automation="searchButton"]',
                'button[type="submit"]',
                'button:has-text("Seek")'
            ]
            
            for selector in button_selectors:
                if await page.locator(selector).count() > 0:
                    search_button = page.locator(selector).first
                    break

            if search_button:
                await search_button.click()
            else:
                await page.keyboard.press("Enter")
            
            # 4. 强制等待结果页加载
            print("⏳ 等待搜索结果...")
            try:
                # 确保进入 search-jobs 模式
                await page.wait_for_url("**/jobs?**", timeout=15000, wait_until="domcontentloaded")
                # 等待主要结果容器出现 (这是关键，防止抓到推荐位)
                await page.wait_for_selector('article', timeout=15000)
            except:
                print("⚠️ 页面跳转可能超时，尝试继续抓取...")

            await asyncio.sleep(2)

            # 5. 自动滚屏
            print("📜 正在滚动页面...")
            for _ in range(3):
                await page.mouse.wheel(0, 500)
                await asyncio.sleep(1)
            
            # 6. 提取列表数据
            # 改进：先定位到结果区域，避免抓到 sidebar 里的推荐广告
            results = []
            
            # 尝试定位主要结果容器，如果找不到就兜底找所有 article
            # data-automation="searchResults" 是 JobsDB 的标准容器
            target_container = page.locator('[data-automation="searchResults"]')
            if await target_container.count() > 0:
                print("🎯 已锁定精准搜索结果区域")
                articles = await target_container.locator('article').all()
            else:
                print("⚠️ 未找到精准区域，使用通用抓取")
                articles = await page.locator('article').all()
            
            print(f"✅ 发现了 {len(articles)} 个职位卡片")
            
            for i, article in enumerate(articles[:max_count]):
                try:
                    # 1. 抓标题
                    title = "No Title"
                    title_selectors = ['h1', 'h3', '[data-automation="jobTitle"]']
                    for sel in title_selectors:
                        if await article.locator(sel).count() > 0:
                            title = await article.locator(sel).first.inner_text()
                            break
                    
                    # 2. 👇 核心修复：更强的公司名抓取逻辑
                    company = "Unknown Company"
                    company_selectors = [
                        '[data-automation="jobCardCompanyLink"]', # 带链接的公司名
                        '[data-automation="jobCompany"]',         # 纯文本公司名 (SmartHire 等)
                        'a[data-automation="jobCardCompanyLink"]',
                        '.job-card-company'
                    ]
                    
                    for sel in company_selectors:
                        if await article.locator(sel).count() > 0:
                            company = await article.locator(sel).first.inner_text()
                            break
                    
                    # 3. 抓链接
                    link = "No Link"
                    # 优先找标题里的链接
                    if await article.locator('h1 a, h3 a').count() > 0:
                        raw_link = await article.locator('h1 a, h3 a').first.get_attribute('href')
                        if raw_link:
                            link = "https://hk.jobsdb.com" + raw_link if raw_link.startswith('/') else raw_link
                    elif await article.locator('a').count() > 0:
                        raw_link = await article.locator('a').first.get_attribute('href')
                        if raw_link:
                            link = "https://hk.jobsdb.com" + raw_link if raw_link.startswith('/') else raw_link
                    
                    print(f"   📋 [{i+1}] {title} --- {company}")

                    results.append({
                        "id": i + 1, 
                        "title": title, 
                        "company": company, 
                        "link": link
                    })
                except Exception as e:
                    print(f"提取第 {i} 个链接时出错: {e}")
                    continue
            
            print(f"📊 列表提取完毕，准备深入抓取 {len(results)} 个 JD...")

            # 7. 深入抓取 JD
            for index, job in enumerate(results):
                print(f"📖 [{index+1}/{len(results)}] 正在读取详情: {job['title']}...")
                try:
                    await page.goto(job['link'])
                    
                    try:
                        await page.wait_for_selector('[data-automation="jobAdDetails"]', timeout=8000)
                    except:
                        pass 

                    jd_text = ""
                    # 优先抓取标准 JD 区域
                    if await page.locator('[data-automation="jobAdDetails"]').count() > 0:
                        jd_text = await page.locator('[data-automation="jobAdDetails"]').inner_text()
                    # 备选：抓取描述部分
                    elif await page.locator('#jobAdDetails').count() > 0:
                        jd_text = await page.locator('#jobAdDetails').inner_text()
                    else:
                        # 最后的兜底
                        jd_text = await page.locator('main').inner_text()
                    
                    job['jd_content'] = jd_text
                    print(f"   ✅ 获取成功 ({len(jd_text)} 字符)")

                    sleep_time = random.uniform(2, 4)
                    print(f"   💤 休息 {sleep_time:.1f} 秒...")
                    await asyncio.sleep(sleep_time)

                except Exception as e:
                    print(f"   ❌ 抓取失败: {e}")
                    job['jd_content'] = "Error extracting content"
            
            print("🎉 所有任务完成！")
            await context.close()
            return json.dumps(results, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return f"System Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()