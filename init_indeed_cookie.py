#!/usr/bin/env python3
"""
Indeed Cookie 导出脚本
使用真实 Chrome 浏览器（非自动化）绕过 Cloudflare 检测

步骤：
1. 打开真实 Chrome 访问 Indeed
2. 手动完成验证
3. 用这个脚本从 Chrome 导出 Cookie
4. 爬虫加载这些 Cookie
"""

import sys
import json
import sqlite3
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
import subprocess
import os

# Cookie 保存位置
COOKIE_FILE = Path(__file__).parent / "chrome_profile" / "indeed_cookies.json"


def get_chrome_cookie_path() -> Path:
    """获取 Chrome Cookie 数据库路径"""
    if sys.platform == "darwin":  # macOS
        return Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"
    elif sys.platform == "win32":  # Windows
        return Path.home() / "AppData/Local/Google/Chrome/User Data/Default/Network/Cookies"
    else:  # Linux
        return Path.home() / ".config/google-chrome/Default/Cookies"


def export_indeed_cookies():
    """从真实 Chrome 导出 Indeed Cookie"""

    print("=" * 60)
    print("🍪 Indeed Cookie 导出工具")
    print("=" * 60)
    print()

    cookie_db = get_chrome_cookie_path()

    if not cookie_db.exists():
        print(f"❌ Chrome Cookie 数据库不存在: {cookie_db}")
        print("   请确保已安装 Google Chrome")
        return False

    print("📋 步骤说明：")
    print()
    print("  1. 请先用真实 Chrome 浏览器访问:")
    print("     https://hk.indeed.com/jobs?q=data+analyst")
    print()
    print("  2. 完成 Cloudflare 人机验证")
    print()
    print("  3. 确认看到职位列表后，回到这里按 Enter")
    print()
    print("  ⚠️  注意：导出前请关闭 Chrome 浏览器！")
    print()

    input(">>> 完成验证并关闭 Chrome 后按 Enter: ")

    # 复制数据库（因为 Chrome 可能锁定）
    print("🔍 正在读取 Cookie...")

    try:
        # 创建临时副本
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            tmp_path = tmp.name

        shutil.copy2(cookie_db, tmp_path)

        # 连接数据库
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # 查询 Indeed 相关的 Cookie
        cursor.execute("""
            SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly
            FROM cookies
            WHERE host_key LIKE '%indeed.com%'
        """)

        rows = cursor.fetchall()
        conn.close()

        # 清理临时文件
        os.unlink(tmp_path)

        if not rows:
            print("❌ 未找到 Indeed Cookie")
            print("   请确保：")
            print("   1. 用 Chrome 访问过 Indeed")
            print("   2. 完成了验证")
            print("   3. 导出前关闭了 Chrome")
            return False

        # 转换为标准格式
        cookies = []
        for row in rows:
            host, name, value, path, expires, secure, httponly = row

            # Chrome 的 Cookie 可能是加密的
            if not value:
                continue

            cookies.append({
                "domain": host,
                "name": name,
                "value": value,
                "path": path,
                "expires": expires,
                "secure": bool(secure),
                "httpOnly": bool(httponly),
            })

        if not cookies:
            print("❌ Cookie 值为空（可能被加密）")
            print("   macOS 上 Chrome Cookie 是加密的，需要用其他方法")
            print()
            print("🔄 尝试备用方案：使用 Browser Cookie3...")
            return export_with_browser_cookie3()

        # 保存
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_FILE, 'w') as f:
            json.dump({
                "cookies": cookies,
                "exported_at": datetime.now().isoformat(),
                "count": len(cookies),
            }, f, indent=2)

        print(f"✅ 成功导出 {len(cookies)} 个 Cookie")
        print(f"📁 保存位置: {COOKIE_FILE}")
        return True

    except Exception as e:
        print(f"❌ 导出失败: {e}")
        return False


def export_with_browser_cookie3():
    """使用 browser_cookie3 库导出（可解密 macOS Cookie）"""

    try:
        import browser_cookie3
    except ImportError:
        print("📦 安装 browser_cookie3...")
        subprocess.run([sys.executable, "-m", "pip", "install", "browser_cookie3", "-q"])
        import browser_cookie3

    try:
        # 获取 Chrome Cookie
        cj = browser_cookie3.chrome(domain_name='.indeed.com')

        cookies = []
        for cookie in cj:
            cookies.append({
                "domain": cookie.domain,
                "name": cookie.name,
                "value": cookie.value,
                "path": cookie.path,
                "expires": cookie.expires,
                "secure": cookie.secure,
                "httpOnly": bool(cookie.has_nonstandard_attr('HttpOnly')),
            })

        if not cookies:
            print("❌ 未找到 Indeed Cookie")
            return False

        # 保存
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_FILE, 'w') as f:
            json.dump({
                "cookies": cookies,
                "exported_at": datetime.now().isoformat(),
                "count": len(cookies),
            }, f, indent=2)

        print(f"✅ 成功导出 {len(cookies)} 个 Cookie")
        print(f"📁 保存位置: {COOKIE_FILE}")
        print()
        print("🎉 现在可以运行爬虫了！")
        return True

    except Exception as e:
        print(f"❌ browser_cookie3 导出失败: {e}")
        print()
        print("💡 备用方案：手动导出 Cookie")
        print()
        print("  1. 在 Chrome 中打开 Indeed")
        print("  2. 按 F12 打开开发者工具")
        print("  3. 切换到 Application > Cookies")
        print("  4. 找到 cf_clearance 的值")
        print("  5. 手动创建 Cookie 文件")
        return False


def open_chrome_indeed():
    """打开真实 Chrome 访问 Indeed"""
    url = "https://hk.indeed.com/jobs?q=data+analyst"

    print(f"🌐 正在打开 Chrome: {url}")

    if sys.platform == "darwin":
        subprocess.run(["open", "-a", "Google Chrome", url])
    elif sys.platform == "win32":
        subprocess.run(["start", "chrome", url], shell=True)
    else:
        subprocess.run(["google-chrome", url])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "open":
        open_chrome_indeed()
    else:
        # 先打开 Chrome
        print("🚀 正在打开真实 Chrome 浏览器...")
        open_chrome_indeed()
        print()

        # 然后导出
        export_indeed_cookies()
