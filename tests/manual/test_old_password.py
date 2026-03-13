#!/usr/bin/env python3
"""
测试旧账号登录脚本
可以安全地测试密码是否正确，不会修改数据库
"""

import sys
import hashlib
import sqlite3
from pathlib import Path

def test_login(username, password):
    """
    测试账号密码是否正确

    Args:
        username: 用户名
        password: 密码

    Returns:
        True if login successful, False otherwise
    """
    # 使用与 core/auth_manager.py 相同的哈希算法
    salt = "autojobagent_salt_2026"
    salted_password = f"{password}{salt}"
    password_hash = hashlib.sha256(salted_password.encode()).hexdigest()

    # 连接数据库
    db_path = Path("data/users.db")
    if not db_path.exists():
        print(f"❌ 错误: 数据库文件不存在: {db_path}")
        return False

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 查询用户
    cursor.execute(
        "SELECT id, username, password_hash, email FROM users WHERE username = ?",
        (username,)
    )

    result = cursor.fetchone()
    conn.close()

    if not result:
        print(f"❌ 用户不存在: {username}")
        return False

    user_id, db_username, db_password_hash, email = result

    print(f"\n🔍 测试结果:")
    print(f"   用户 ID: {user_id}")
    print(f"   用户名: {db_username}")
    print(f"   邮箱: {email or '(未设置)'}")
    print(f"\n🔐 密码验证:")
    print(f"   输入的密码: {password}")
    print(f"   计算的哈希: {password_hash[:32]}...")
    print(f"   数据库哈希: {db_password_hash[:32]}...")

    if password_hash == db_password_hash:
        print(f"\n✅ 密码正确！可以使用此账号登录")
        print(f"\n📝 登录凭据:")
        print(f"   用户名: {username}")
        print(f"   密码: {password}")
        return True
    else:
        print(f"\n❌ 密码错误！")
        print(f"\n💡 提示:")
        print(f"   1. 请确认密码是否正确")
        print(f"   2. 密码可能在之前被修改过")
        print(f"   3. 建议重置密码或注册新账号")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🔐 AutoJobAgent 旧账号登录测试工具")
    print("=" * 60)

    # 从命令行参数获取，或者交互式输入
    if len(sys.argv) >= 3:
        username = sys.argv[1]
        password = sys.argv[2]
    else:
        username = input("\n请输入用户名: ").strip()
        password = input("请输入密码: ").strip()

    if not username or not password:
        print("❌ 错误: 用户名和密码不能为空")
        sys.exit(1)

    success = test_login(username, password)

    print("\n" + "=" * 60)
    if success:
        print("✅ 测试成功！您可以使用上述凭据登录新系统")
    else:
        print("❌ 测试失败！建议重置密码或注册新账号")
    print("=" * 60)

    sys.exit(0 if success else 1)
