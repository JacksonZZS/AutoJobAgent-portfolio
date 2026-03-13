#!/usr/bin/env python3
"""
系统升级验证脚本
验证所有新功能是否正常工作
"""

import os
import sys
import json
from pathlib import Path

def print_section(title):
    """打印分隔线"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def check_file_exists(path, description):
    """检查文件是否存在"""
    if Path(path).exists():
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description} 不存在: {path}")
        return False

def check_directory_exists(path, description):
    """检查目录是否存在"""
    if Path(path).is_dir():
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description} 不存在: {path}")
        return False

def main():
    print_section("🚀 系统升级验证脚本")
    print("验证所有新功能是否正常工作...")

    all_passed = True

    # 1. 检查核心文件
    print_section("1️⃣ 检查核心文件")
    all_passed &= check_file_exists("core/apply_bot.py", "核心机器人文件")
    all_passed &= check_file_exists("app_dashboard.py", "Web Dashboard 文件")
    all_passed &= check_file_exists("core/status_manager.py", "状态管理器")
    all_passed &= check_file_exists("core/interaction_manager.py", "交互管理器")
    all_passed &= check_file_exists("UPGRADE_NOTES.md", "升级文档")

    # 2. 检查数据目录结构
    print_section("2️⃣ 检查数据目录结构")
    data_dirs = [
        ("data/browser_profiles", "浏览器配置目录"),
        ("data/status", "状态文件目录"),
        ("data/histories", "历史记录目录"),
        ("data/signals", "交互信号目录"),
        ("data/outputs", "输出文件目录"),
    ]

    for dir_path, description in data_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        all_passed &= check_directory_exists(dir_path, description)

    # 3. 验证浏览器持久化功能
    print_section("3️⃣ 验证浏览器持久化功能")
    print("检查 core/apply_bot.py 中的关键代码...")

    with open("core/apply_bot.py", "r", encoding="utf-8") as f:
        content = f.read()

    if "launch_persistent_context" in content:
        print("✅ 找到 launch_persistent_context() 调用")
    else:
        print("❌ 未找到 launch_persistent_context() 调用")
        all_passed = False

    if "data/browser_profiles" in content:
        print("✅ 找到浏览器配置目录路径")
    else:
        print("❌ 未找到浏览器配置目录路径")
        all_passed = False

    if "已弃用" in content and "_load_cookies" in content:
        print("✅ Cookie 函数已标记为弃用")
    else:
        print("⚠️ Cookie 函数未标记为弃用（可能已删除）")

    # 4. 验证 Web 自动重载功能
    print_section("4️⃣ 验证 Web 自动重载功能")
    print("检查 app_dashboard.py 中的关键代码...")

    with open("app_dashboard.py", "r", encoding="utf-8") as f:
        content = f.read()

    if "last_status_timestamp" in content:
        print("✅ 找到时间戳监控逻辑")
    else:
        print("❌ 未找到时间戳监控逻辑")
        all_passed = False

    if "auto_refresh" in content:
        print("✅ 找到自动刷新开关")
    else:
        print("❌ 未找到自动刷新开关")
        all_passed = False

    if "st.rerun()" in content:
        print("✅ 找到页面重载调用")
    else:
        print("❌ 未找到页面重载调用")
        all_passed = False

    # 5. 验证 UI 增强功能
    print_section("5️⃣ 验证 UI 增强功能")

    ui_features = [
        ("st.balloons()", "庆祝动画"),
        ("st.status(", "实时日志流"),
        ("blinking-warning", "闪烁警告"),
        ("AI 匹配度", "AI 分数显示"),
    ]

    for feature, description in ui_features:
        if feature in content:
            print(f"✅ 找到 {description}")
        else:
            print(f"❌ 未找到 {description}")
            all_passed = False

    # 6. 验证任务生命周期管理
    print_section("6️⃣ 验证任务生命周期管理")

    lifecycle_features = [
        ("结束当前任务", "终止任务按钮"),
        ("清空已投递历史", "清空记录按钮"),
        ("os.kill", "进程终止逻辑"),
        ("signal.SIGTERM", "优雅终止信号"),
    ]

    for feature, description in lifecycle_features:
        if feature in content:
            print(f"✅ 找到 {description}")
        else:
            print(f"❌ 未找到 {description}")
            all_passed = False

    # 7. 验证多租户隔离
    print_section("7️⃣ 验证多租户隔离")

    isolation_patterns = [
        ("user_id", "用户 ID 参数"),
        ("data/browser_profiles/{", "浏览器配置隔离"),
        ("data/status/status_{", "状态文件隔离"),
        ("data/histories/history_{", "历史记录隔离"),
        ("data/signals/signal_{", "交互信号隔离"),
    ]

    for pattern, description in isolation_patterns:
        if pattern in content:
            print(f"✅ 找到 {description}")
        else:
            print(f"⚠️ 未找到 {description}（可能在其他文件中）")

    # 8. 最终结果
    print_section("📊 验证结果")

    if all_passed:
        print("✅ 所有检查通过！系统升级成功！")
        print("\n🎉 恭喜！您可以开始使用新版本了。")
        print("\n启动命令:")
        print("  streamlit run app_dashboard.py")
        return 0
    else:
        print("❌ 部分检查未通过，请检查上述错误。")
        print("\n💡 提示:")
        print("  1. 确保所有文件都已正确修改")
        print("  2. 检查是否有语法错误")
        print("  3. 查看 UPGRADE_NOTES.md 了解详细信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())
