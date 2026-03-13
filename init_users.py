"""
用户数据库初始化脚本
创建默认用户并提供添加新用户的接口
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from core.user_identity import get_user_identity_manager


def initialize_users():
    """初始化用户数据库"""
    print("=" * 60)
    print("  用户数据库初始化")
    print("=" * 60)

    manager = get_user_identity_manager()

    # 创建默认用户（Jackson）
    print("\n创建默认用户...")

    jackson = manager.create_user(
        user_id="jacksonzhang1221",
        username="jacksonzhang1221",
        real_name="Jackson Zhang",
        email="jackson.zhang@example.com",
        phone="+852 1234 5678",
        linkedin="https://linkedin.com/in/jacksonzhang",
        github="https://github.com/jacksonzhang",
        location="Hong Kong"
    )

    print(f"✅ 创建用户: {jackson.username} ({jackson.real_name})")

    # 创建测试用户
    print("\n创建测试用户...")

    alice = manager.create_user(
        user_id="user_2",
        username="alice",
        real_name="Alice Chen",
        email="alice.chen@example.com",
        phone="+852 9876 5432",
        location="Hong Kong",
        linkedin="https://linkedin.com/in/alicechen"
    )

    print(f"✅ 创建用户: {alice.username} ({alice.real_name})")

    bob = manager.create_user(
        user_id="user_3",
        username="bob",
        real_name="Bob Li",
        email="bob.li@example.com",
        phone="+852 5555 1234",
        location="Hong Kong"
    )

    print(f"✅ 创建用户: {bob.username} ({bob.real_name})")

    # 列出所有用户
    print("\n" + "=" * 60)
    print("  所有用户列表")
    print("=" * 60)

    all_users = manager.list_all_users()

    for user_id, user in all_users.items():
        print(f"\n用户 ID: {user_id}")
        print(f"  用户名: {user.username}")
        print(f"  真实姓名: {user.real_name}")
        print(f"  邮箱: {user.email}")
        print(f"  电话: {user.phone}")
        if user.location:
            print(f"  位置: {user.location}")
        if user.linkedin:
            print(f"  LinkedIn: {user.linkedin}")

    print("\n" + "=" * 60)
    print("  初始化完成！")
    print("=" * 60)


if __name__ == "__main__":
    initialize_users()
