"""
Indeed 反检测爬虫 - DrissionPage 终极隐身版
解决无头模式被检测 + CAPTCHA 问题
"""

from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.common import By
import time
import random
import json
from pathlib import Path
from typing import List, Dict, Optional


class IndeedStealthScraper:
    """Indeed 反检测爬虫"""
    
    def __init__(self, headless: bool = False, use_undetected: bool = True):
        """
        初始化爬虫
        
        Args:
            headless: 是否无头模式（建议先用 False 调试）
            use_undetected: 是否使用反检测模式（强烈建议 True）
        """
        self.headless = headless
        self.use_undetected = use_undetected
        self.page = None
        self._init_browser()
    
    def _init_browser(self):
        """配置反检测浏览器"""
        co = ChromiumOptions()
        
        # ========== 核心反检测参数 ==========
        
        # 1. 隐藏自动化特征
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--no-sandbox')
        
        # 2. 真实浏览器伪装
        co.set_user_agent(
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/131.0.0.0 Safari/537.36'
        )
        
        # 3. 窗口大小（模拟真实用户）
        co.set_argument('--window-size=1920,1080')
        co.set_argument('--start-maximized')
        
        # 4. 语言和时区
        co.set_argument('--lang=en-US')
        co.set_pref('intl.accept_languages', 'en-US,en')
        
        # 5. WebRTC 泄露防护
        co.set_argument('--disable-webrtc')
        co.set_pref('webrtc.ip_handling_policy', 'disable_non_proxied_udp')
        
        # 6. 硬件加速（模拟真实浏览器）
        co.set_argument('--enable-features=NetworkService,NetworkServiceInProcess')
        
        # 7. 插件和扩展模拟
        co.set_argument('--disable-plugins-discovery')
        co.set_pref('plugins.always_open_pdf_externally', True)
        
        # ========== 无头模式特殊处理 ==========
        if self.headless:
            # 使用新版无头模式（更难检测）
            co.set_argument('--headless=new')
            
            # 隐藏无头模式特征
            co.set_argument('--disable-gpu')
            co.set_argument('--disable-software-rasterizer')
            
            # 后台运行但不弹窗
            co.set_argument('--window-position=-2000,-2000')
            co.set_argument('--silent')
            co.set_argument('--log-level=3')
        
        # ========== 反检测核心：注入 JavaScript ==========
        # 移除 webdriver 标识
        co.set_argument('--disable-blink-features=AutomationControlled')
        
        # 创建浏览器实例
        self.page = ChromiumPage(addr_or_opts=co)
        
        # 注入反检测脚本
        self._inject_stealth_scripts()
    
    def _inject_stealth_scripts(self):
        """注入反检测 JavaScript 代码"""
        
        stealth_js = """
        // ========== 1. 隐藏 WebDriver ==========
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // ========== 2. 模拟 Chrome 对象 ==========
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        // ========== 3. 真实插件列表 ==========
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                    {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                    {name: 'Native Client', filename: 'internal-nacl-plugin'}
                ];
                return plugins;
            }
        });
        
        // ========== 4. 语言列表 ==========
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        // ========== 5. 权限查询伪装 ==========
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({state: Notification.permission}) :
                originalQuery(parameters)
        );
        
        // ========== 6. 硬件信息模拟 ==========
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8
        });
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8
        });
        
        // ========== 7. 连接信息模拟 ==========
        Object.defineProperty(navigator, 'connection', {
            get: () => ({
                effectiveType: '4g',
                rtt: 50,
                downlink: 10
            })
        });
        
        // ========== 8. Canvas 指纹噪声 ==========
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            if (type === 'image/png' && this.width === 280 && this.height === 60) {
                // 检测到指纹检测，添加噪声
                const ctx = this.getContext('2d');
                const imageData = ctx.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] += Math.floor(Math.random() * 3) - 1;
                }
                ctx.putImageData(imageData, 0, 0);
            }
            return originalToDataURL.apply(this, arguments);
        };
        
        // ========== 9. WebGL 指纹混淆 ==========
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter.call(this, parameter);
        };
        
        // ========== 10. 删除自动化框架痕迹 ==========
        delete window.__playwright;
        delete window.__puppeteer;
        delete window.emit;
        delete window.Mocha;
        delete window.Cypress;
        delete window._Selenium_IDE_Recorder;
        
        console.log('✅ Stealth scripts injected');
        """
        
        # 在每个页面加载前注入
        self.page.run_js(stealth_js)
    
    def search_jobs(
        self, 
        keyword: str, 
        location: str = "United States",
        max_results: int = 50
    ) -> List[Dict]:
        """
        搜索 Indeed 职位
        
        Args:
            keyword: 搜索关键词
            location: 地点
            max_results: 最大结果数
            
        Returns:
            职位列表
        """
        jobs = []
        
        try:
            # 1. 访问 Indeed 首页
            print("🌐 访问 Indeed...")
            self.page.get('https://www.indeed.com')
            
            # 人类行为模拟：随机等待
            self._human_delay(2, 4)
            
            # 2. 重新注入脚本（页面跳转后需要）
            self._inject_stealth_scripts()
            
            # 3. 检查是否有 CAPTCHA
            if self._check_captcha():
                print("⚠️ 检测到 CAPTCHA，等待人工处理...")
                if not self.headless:
                    input("请手动完成验证后按 Enter 继续...")
                else:
                    print("❌ 无头模式无法处理 CAPTCHA，请使用有头模式或验证码服务")
                    return []
            
            # 4. 填写搜索表单
            print(f"🔍 搜索: {keyword} @ {location}")
            
            # 定位搜索框（Indeed 的 HTML 结构）
            keyword_input = self.page.ele('css:#text-input-what')
            location_input = self.page.ele('css:.icl-TextInput')
            
            if keyword_input:
                keyword_input.clear()
                self._human_type(keyword_input, keyword)
            
            if location_input:
                location_input.clear()
                self._human_type(location_input, location)
            
            # 5. 点击搜索按钮
            search_btn = self.page.ele('css:.yosegi-InlineWhatWhere-primaryButton')
            if search_btn:
                self._human_delay(1, 2)
                search_btn.click()
            
            # 6. 等待结果加载
            self._human_delay(3, 5)
            
            # 7. 滚动页面（触发懒加载 + 模拟人类行为）
            self._smooth_scroll()
            
            # 8. 提取职位信息
            jobs = self._extract_jobs(max_results)
            
            print(f"✅ 成功抓取 {len(jobs)} 个职位")
            
        except Exception as e:
            print(f"❌ 爬取失败: {str(e)}")
            # 保存截图用于调试
            self._save_debug_screenshot()
        
        return jobs
    
    def _extract_jobs(self, max_results: int) -> List[Dict]:
        """提取职位信息"""
        jobs = []
        
        # Indeed 职位卡片选择器（可能需要根据实际页面调整）
        job_cards = self.page.eles('css:.job_seen_beacon')
        
        for card in job_cards[:max_results]:
            try:
                # 提取信息
                title_elem = card.ele('css:h2.jobTitle')
                company_elem = card.ele('css:.companyName')
                location_elem = card.ele('css:.companyLocation')
                salary_elem = card.ele('css:.salary-snippet')
                link_elem = card.ele('css:h2.jobTitle a')
                
                job = {
                    'title': title_elem.text if title_elem else 'N/A',
                    'company': company_elem.text if company_elem else 'N/A',
                    'location': location_elem.text if location_elem else 'N/A',
                    'salary': salary_elem.text if salary_elem else 'Not specified',
                    'url': 'https://www.indeed.com' + link_elem.attr('href') if link_elem else None,
                    'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                jobs.append(job)
                
                # 模拟人类浏览节奏
                self._human_delay(0.3, 0.8)
                
            except Exception as e:
                print(f"⚠️ 提取职位失败: {str(e)}")
                continue
        
        return jobs
    
    def _check_captcha(self) -> bool:
        """检测是否有 CAPTCHA"""
        captcha_selectors = [
            'css:#captcha-form',
            'css:.g-recaptcha',
            'css:iframe[src*="recaptcha"]',
            'text:I\'m not a robot'
        ]
        
        for selector in captcha_selectors:
            if self.page.ele(selector):
                return True
        return False
    
    def _human_type(self, element, text: str):
        """模拟人类打字（随机延迟）"""
        element.clear()
        for char in text:
            element.input(char)
            time.sleep(random.uniform(0.05, 0.15))
    
    def _human_delay(self, min_sec: float, max_sec: float):
        """随机等待（模拟人类思考时间）"""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def _smooth_scroll(self):
        """平滑滚动（模拟人类浏览）"""
        total_height = self.page.run_js('return document.body.scrollHeight')
        viewport_height = self.page.run_js('return window.innerHeight')
        
        current_position = 0
        while current_position < total_height:
            # 随机滚动距离
            scroll_distance = random.randint(300, 600)
            current_position += scroll_distance
            
            self.page.scroll.to_location(0, current_position)
            
            # 随机停顿（模拟阅读）
            time.sleep(random.uniform(0.5, 1.5))
    
    def _save_debug_screenshot(self):
        """保存调试截图"""
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        filename = f'debug_indeed_{timestamp}.png'
        self.page.get_screenshot(path=filename)
        print(f"📸 调试截图已保存: {filename}")
    
    def close(self):
        """关闭浏览器"""
        if self.page:
            self.page.quit()
            print("🔒 浏览器已关闭")


# ========== 使用示例 ==========

if __name__ == '__main__':
    # 方案 1：有头模式（首次测试）
    print("=== 方案 1：有头模式测试 ===")
    scraper = IndeedStealthScraper(headless=False)
    jobs = scraper.search_jobs(
        keyword='Python Developer',
        location='New York, NY',
        max_results=20
    )
    
    # 打印结果
    for i, job in enumerate(jobs, 1):
        print(f"\n{i}. {job['title']}")
        print(f"   公司: {job['company']}")
        print(f"   地点: {job['location']}")
        print(f"   薪资: {job['salary']}")
        print(f"   链接: {job['url']}")
    
    scraper.close()
    
    # 方案 2：无头模式（确认有头模式成功后）
    print("\n=== 方案 2：无头模式测试 ===")
    scraper_headless = IndeedStealthScraper(headless=True)
    jobs_headless = scraper_headless.search_jobs(
        keyword='Python Developer',
        location='Remote',
        max_results=10
    )
    print(f"无头模式抓取: {len(jobs_headless)} 个职位")
    scraper_headless.close()
