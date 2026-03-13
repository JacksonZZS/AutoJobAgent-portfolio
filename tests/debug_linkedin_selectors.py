#!/usr/bin/env python3
"""
调试 LinkedIn 选择器 - 找出正确的 DOM 结构
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from DrissionPage import ChromiumPage, ChromiumOptions

def debug_selectors():
    """调试 LinkedIn 页面选择器"""

    print("🔍 调试 LinkedIn 选择器")
    print("=" * 60)

    # 创建浏览器
    co = ChromiumOptions()
    co.set_argument('--disable-blink-features', 'AutomationControlled')
    co.set_argument('--window-size=1920,1080')
    page = ChromiumPage(co)

    # 加载 cookies
    cookies_file = Path(__file__).parent.parent / "linkedin_cookies.json"
    with open(cookies_file) as f:
        cookies = json.load(f)

    page.get("https://www.linkedin.com")
    time.sleep(2)

    for cookie in cookies:
        try:
            page.set.cookies({
                'name': cookie['name'],
                'value': cookie['value'],
                'domain': cookie.get('domain', '.linkedin.com').replace('.www.', '.'),
                'path': cookie.get('path', '/'),
            })
        except:
            pass

    # 访问搜索页
    page.get("https://www.linkedin.com/jobs/search/?keywords=Data+Analyst&location=Hong+Kong")
    time.sleep(5)

    print("\n📋 页面 URL:", page.url)
    print("📋 页面标题:", page.title)

    # 找职位卡片
    print("\n🔍 尝试不同的选择器...")

    selectors_to_try = [
        # 职位卡片容器
        ('li.scaffold-layout__list-item', '职位卡片 li'),
        ('div[data-occludable-job-id]', '职位卡片 div'),
        ('.job-card-container', '职位容器'),
        ('.jobs-search-results__list-item', '搜索结果项'),

        # 公司名
        ('.job-card-container__company-name', '公司名1'),
        ('.artdeco-entity-lockup__subtitle', '公司名2'),
        ('.job-card-container__primary-description', '公司名3'),
        ('span[data-test-job-card-company-name]', '公司名4'),

        # 地点
        ('.job-card-container__metadata-item', '地点1'),
        ('.artdeco-entity-lockup__caption', '地点2'),
        ('.job-card-container__metadata-wrapper', '地点3'),
    ]

    for selector, desc in selectors_to_try:
        try:
            elems = page.eles(f'css:{selector}')
            if elems:
                print(f"  ✅ {desc} ({selector}): 找到 {len(elems)} 个")
                if len(elems) > 0:
                    text = elems[0].text[:100] if elems[0].text else "(空)"
                    print(f"      首个元素文本: {text}")
            else:
                print(f"  ❌ {desc} ({selector}): 未找到")
        except Exception as e:
            print(f"  ❌ {desc} ({selector}): 错误 - {e}")

    # 直接找第一个职位链接，打印其父元素结构
    print("\n🔍 分析第一个职位链接的 DOM 结构...")
    job_link = page.ele('css:a[href*="/jobs/view/"]')
    if job_link:
        print(f"  链接文本: {job_link.text[:50] if job_link.text else '(空)'}")
        print(f"  链接 href: {job_link.attr('href')}")

        # 向上遍历父元素
        current = job_link
        for i in range(5):
            try:
                parent = current.parent()
                if parent:
                    tag = parent.tag
                    classes = parent.attr('class') or ''
                    print(f"  父级 {i+1}: <{tag}> class=\"{classes[:80]}\"")

                    # 在这个父级中找公司和地点
                    for sel in ['.artdeco-entity-lockup__subtitle', 'span', '.job-card-container__primary-description']:
                        try:
                            el = parent.ele(f'css:{sel}', timeout=0.2)
                            if el and el.text and len(el.text) > 2:
                                print(f"       → 找到 {sel}: {el.text[:50]}")
                        except:
                            pass

                    current = parent
                else:
                    break
            except:
                break

    # 截图
    page.get_screenshot(path="/tmp/visual_test/debug_linkedin.png")
    print(f"\n📸 截图保存: /tmp/visual_test/debug_linkedin.png")

    # 保存页面 HTML 片段
    try:
        html = page.html[:50000]
        with open("/tmp/visual_test/debug_linkedin.html", "w") as f:
            f.write(html)
        print(f"📄 HTML 保存: /tmp/visual_test/debug_linkedin.html")
    except:
        pass

    page.quit()
    print("\n✅ 调试完成")


if __name__ == "__main__":
    debug_selectors()
