#!/usr/bin/env python3
"""
Indeed 爬虫 - 接管真实 Chrome（绕过 TLS 指纹检测）

🔴 原理：
1. 用户用调试模式启动真实 Chrome
2. DrissionPage 通过 CDP 接管这个 Chrome
3. TLS 指纹是真实的，Cloudflare 无法检测

使用方法：
1. 先关闭所有 Chrome 窗口
2. 运行: python init_chrome_debug.py
3. 在打开的 Chrome 中完成一次 Cloudflare 验证
4. 然后运行爬虫，不再需要验证
"""

import subprocess
import sys
import time
import os
from pathlib import Path


def start_chrome_debug():
    """启动调试模式的 Chrome"""

    print("=" * 60)
    print("🚀 启动调试模式 Chrome")
    print("=" * 60)
    print()

    # Chrome 路径
    if sys.platform == "darwin":
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    elif sys.platform == "win32":
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    else:
        chrome_path = "google-chrome"

    # 用户数据目录（保持登录状态）
    user_data_dir = Path.home() / ".chrome_debug_profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    # 调试端口
    debug_port = 9222

    print(f"📁 Profile 目录: {user_data_dir}")
    print(f"🔌 调试端口: {debug_port}")
    print()

    # 检查端口是否已被占用
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', debug_port))
    sock.close()

    if result == 0:
        print("✅ Chrome 调试模式已在运行！")
        print()
        print("现在可以运行爬虫了：")
        print("   python -c \"from core.indeed_takeover import test_indeed_takeover; test_indeed_takeover()\"")
        return True

    # 启动 Chrome
    cmd = [
        chrome_path,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://hk.indeed.com/jobs?q=data+analyst",
    ]

    print("🌐 正在启动 Chrome...")
    print()

    try:
        # 非阻塞启动
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)

        print("✅ Chrome 已启动！")
        print()
        print("=" * 60)
        print("📋 接下来请：")
        print("=" * 60)
        print()
        print("  1. 在打开的 Chrome 中完成 Cloudflare 验证（如果有）")
        print("  2. 确认看到职位列表")
        print("  3. 保持 Chrome 打开，不要关闭！")
        print()
        print("  然后运行爬虫：")
        print("  python -c \"from core.indeed_takeover import test_indeed_takeover; test_indeed_takeover()\"")
        print()

        return True

    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False


if __name__ == "__main__":
    start_chrome_debug()
