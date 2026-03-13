#!/usr/bin/env python3
"""
系统初始化脚本 - 创建必要的目录和数据库

功能：
1. 创建所有必要的数据目录
2. 初始化 SQLite 数据库
3. 创建演示账号
4. 验证系统配置
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.auth_manager import get_auth_manager


def create_directories():
    """创建所有必要的目录"""
    print("\n" + "="*60)
    print("📁 创建目录结构")
    print("="*60)

    directories = [
        "data/uploads",
        "data/histories",
        "data/status",
        "data/signals",
        "data/sessions",
        "data/outputs",
        "data/logs",
        "data/templates",
    ]

    for directory in directories:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ {directory}")

    print("\n✅ 目录结构创建完成")


def init_database():
    """初始化数据库"""
    print("\n" + "="*60)
    print("🗄️ 初始化数据库")
    print("="*60)

    try:
        auth_manager = get_auth_manager()
        print("✅ 数据库初始化成功")
        print(f"📍 数据库路径: {auth_manager.db_path}")
        return auth_manager
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return None


def create_demo_account(auth_manager):
    """创建演示账号"""
    print("\n" + "="*60)
    print("👤 创建演示账号")
    print("="*60)

    demo_username = "demo"
    demo_password = "demo123"
    demo_email = "demo@autojobagent.com"

    # 检查演示账号是否已存在
    if auth_manager.user_exists(demo_username):
        print(f"ℹ️ 演示账号已存在: {demo_username}")
        return

    # 创建演示账号
    success, message = auth_manager.register(
        username=demo_username,
        password=demo_password,
        email=demo_email
    )

    if success:
        print(f"✅ {message}")
        print(f"   用户名: {demo_username}")
        print(f"   密码: {demo_password}")
        print(f"   邮箱: {demo_email}")
    else:
        print(f"❌ {message}")


def verify_system():
    """验证系统配置"""
    print("\n" + "="*60)
    print("🔍 验证系统配置")
    print("="*60)

    checks = []

    # 检查数据库
    db_path = Path("data/users.db")
    checks.append(("数据库文件", db_path.exists()))

    # 检查关键目录
    key_dirs = [
        "data/uploads",
        "data/histories",
        "data/status",
        "data/signals",
        "data/sessions",
        "data/outputs"
    ]

    for directory in key_dirs:
        path = Path(directory)
        checks.append((directory, path.exists()))

    # 显示检查结果
    all_passed = True
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✅ 系统配置验证通过")
    else:
        print("\n⚠️ 部分检查未通过，请检查配置")

    return all_passed


def show_usage_info():
    """显示使用说明"""
    print("\n" + "="*60)
    print("🚀 系统初始化完成")
    print("="*60)

    print("""
📋 **使用说明**：

1. **启动 Dashboard**：
   streamlit run app_dashboard.py

2. **登录系统**：
   - 演示账号：demo / demo123
   - 或注册新账号

3. **多用户隔离**：
   - 每个用户拥有独立的数据目录
   - 历史记录：data/histories/history_{user_id}.json
   - 运行状态：data/status/status_{user_id}.json
   - 信号文件：data/signals/signal_{user_id}.json
   - 会话 Cookies：data/sessions/cookies_{user_id}.json
   - 输出文件：data/outputs/{user_id}/

4. **命令行使用**：
   python run_auto_apply.py \\
       --user_id {user_id} \\
       --resume_path data/inputs/resume.pdf \\
       --keywords "Python Developer" \\
       --limit 5

5. **管理用户**：
   - 使用 core/auth_manager.py 中的 AuthManager
   - 支持注册、登录、密码修改等功能

📖 **详细文档**：
   - 查看 MULTI_USER_ISOLATION_REPORT.md
   - 查看 ARCHITECTURE_UPGRADE_REPORT.md

🆘 **技术支持**：
   - 查看日志：data/logs/auto_apply.log
   - 运行测试：python test_multi_user_isolation.py
""")


def main():
    """主函数"""
    print("\n" + "🚀 "*30)
    print("AutoJobAgent - 系统初始化")
    print("🚀 "*30)

    try:
        # 1. 创建目录
        create_directories()

        # 2. 初始化数据库
        auth_manager = init_database()
        if not auth_manager:
            print("\n❌ 初始化失败：数据库初始化错误")
            return 1

        # 3. 创建演示账号
        create_demo_account(auth_manager)

        # 4. 验证系统
        if not verify_system():
            print("\n⚠️ 系统验证未完全通过，但可以继续使用")

        # 5. 显示使用说明
        show_usage_info()

        return 0

    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
