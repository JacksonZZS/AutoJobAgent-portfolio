#!/usr/bin/env python3
"""
LinkedIn 选择器探测脚本
用于找出 LinkedIn 2024/2025 新的 DOM 结构
"""

import time
import json
import re
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions

# Cookie 文件
COOKIES_FILE = Path(__file__).parent.parent / "linkedin_cookies.json"
OUTPUT_DIR = Path("/tmp/visual_test")
OUTPUT_DIR.mkdir(exist_ok=True)


def create_browser():
    """创建浏览器"""
    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--window-size=1920,1080')
    co.set_argument('--window-position=100,100')
    co.set_argument('--disable-blink-features', 'AutomationControlled')
    return ChromiumPage(co)


def load_cookies(page):
    """加载 cookies"""
    if not COOKIES_FILE.exists():
        print(f"❌ Cookie 文件不存在: {COOKIES_FILE}")
        return False

    with open(COOKIES_FILE) as f:
        cookies = json.load(f)

    page.get("https://www.linkedin.com")
    time.sleep(2)

    for cookie in cookies:
        try:
            domain = cookie.get('domain', '.linkedin.com')
            if domain.startswith('.www.'):
                domain = domain.replace('.www.', '.')
            page.set.cookies({
                'name': cookie['name'],
                'value': cookie['value'],
                'domain': domain,
                'path': cookie.get('path', '/'),
            })
        except:
            pass

    page.get("https://www.linkedin.com")
    time.sleep(2)
    return True


def find_selectors(page):
    """在页面上测试各种选择器"""

    # 访问搜索页
    search_url = "https://www.linkedin.com/jobs/search/?keywords=Data+Analyst&location=Hong+Kong&f_AL=true"
    print(f"\n📡 访问: {search_url}")
    page.get(search_url)
    time.sleep(5)

    # 滚动加载
    for _ in range(3):
        page.scroll.down(500)
        time.sleep(1)

    print("\n🔍 测试选择器...\n")

    # 要测试的选择器列表
    selectors_to_test = {
        # 职位卡片容器
        "job_cards": [
            'li.scaffold-layout__list-item',
            'div[data-occludable-job-id]',
            '.job-card-container',
            '.jobs-search-results__list-item',
            'li[data-occludable-job-id]',
            '.job-card-list__entity-lockup',
            '.jobs-search-two-pane__job-card-container',
            'li.jobs-search-results__list-item',
            '.ember-view.job-card-container',
            'div.job-card-container--clickable',
        ],
        # 职位标题
        "job_title": [
            '.job-card-list__title',
            '.job-card-container__link',
            'a.job-card-list__title',
            '.job-card-container__company-name + a',
            'a[href*="/jobs/view/"]',
            '.artdeco-entity-lockup__title',
            '.job-card-list__title--link',
        ],
        # 公司名称
        "company": [
            '.job-card-container__primary-description',
            '.job-card-container__company-name',
            '.artdeco-entity-lockup__subtitle',
            '.job-card-list__company-name',
            'span.job-card-container__primary-description',
            '.job-card-container__subtitle',
            '.artdeco-entity-lockup__subtitle span',
            'a[data-tracking-control-name*="company"]',
            '.job-card-container__headline',
        ],
        # 地点
        "location": [
            '.job-card-container__metadata-item',
            '.artdeco-entity-lockup__caption',
            '.job-card-container__metadata-wrapper li',
            '.job-card-list__location',
            'span.job-card-container__metadata-item',
            '.artdeco-entity-lockup__caption span',
            '.job-card-container__metadata-item--workplace-type',
        ],
    }

    results = {}

    for category, selectors in selectors_to_test.items():
        print(f"\n=== {category.upper()} ===")
        results[category] = []

        for selector in selectors:
            try:
                elements = page.eles(f'css:{selector}')
                count = len(elements) if elements else 0

                if count > 0:
                    # 获取第一个元素的文本
                    first_text = ""
                    try:
                        first_text = elements[0].text[:50] if elements[0].text else ""
                    except:
                        pass

                    print(f"  ✅ {selector}: {count} 个元素")
                    if first_text:
                        print(f"      示例: {first_text}")

                    results[category].append({
                        "selector": selector,
                        "count": count,
                        "sample": first_text,
                    })
                else:
                    print(f"  ❌ {selector}: 0")
            except Exception as e:
                print(f"  ❌ {selector}: 错误 - {e}")

    # 用 JavaScript 获取更多信息
    print("\n\n=== JavaScript 分析 ===")

    js_analysis = page.run_js('''
        const results = {
            all_classes: [],
            job_links: [],
            potential_company: [],
            potential_location: [],
        };

        // 找所有职位链接
        document.querySelectorAll('a[href*="/jobs/view/"]').forEach(a => {
            const li = a.closest('li') || a.closest('div[class*="job"]');
            if (li) {
                const classes = li.className;
                results.all_classes.push(classes);

                // 在同一容器内找公司和地点
                const spans = li.querySelectorAll('span');
                spans.forEach((span, i) => {
                    const text = span.textContent?.trim();
                    if (text && text.length > 2 && text.length < 100) {
                        if (i < 5) {
                            results.potential_company.push({
                                class: span.className,
                                text: text.substring(0, 50)
                            });
                        }
                    }
                });
            }
        });

        // 去重
        results.all_classes = [...new Set(results.all_classes)].slice(0, 10);
        results.potential_company = results.potential_company.slice(0, 20);

        return results;
    ''')

    print("\n职位容器的 class 名称:")
    for cls in js_analysis.get('all_classes', []):
        print(f"  - {cls[:100]}")

    print("\n潜在的公司/地点元素:")
    for item in js_analysis.get('potential_company', []):
        print(f"  class: {item.get('class', 'N/A')[:50]}")
        print(f"  text: {item.get('text', '')}")
        print()

    # 保存完整的 DOM 快照
    print("\n\n=== 保存渲染后的 DOM ===")

    rendered_html = page.run_js('''
        // 只获取职位列表区域的 HTML
        const jobList = document.querySelector('.jobs-search-results-list, .scaffold-layout__list-container, [class*="jobs-search"]');
        if (jobList) {
            return jobList.outerHTML;
        }
        return document.body.innerHTML.substring(0, 100000);
    ''')

    html_file = OUTPUT_DIR / "linkedin_rendered_dom.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(rendered_html)
    print(f"✅ 已保存到: {html_file}")

    # 保存结果
    result_file = OUTPUT_DIR / "selector_test_results.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"✅ 测试结果: {result_file}")

    # 截图
    page.get_screenshot(path=str(OUTPUT_DIR / "selector_test.png"))
    print(f"✅ 截图: {OUTPUT_DIR / 'selector_test.png'}")

    return results


def main():
    print("=" * 60)
    print("LinkedIn 选择器探测工具")
    print("=" * 60)

    page = create_browser()

    try:
        if not load_cookies(page):
            print("⚠️ 无法加载 cookies，可能需要手动登录")

        results = find_selectors(page)

        print("\n\n" + "=" * 60)
        print("📊 总结")
        print("=" * 60)

        for category, items in results.items():
            working = [x for x in items if x.get('count', 0) > 0]
            if working:
                print(f"\n{category}:")
                for item in working[:3]:
                    print(f"  ✅ {item['selector']} ({item['count']})")

        print("\n\n按 Enter 关闭浏览器...")
        input()

    finally:
        page.quit()


if __name__ == "__main__":
    main()
