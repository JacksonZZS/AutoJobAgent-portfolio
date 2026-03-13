"""
用户数据同步脚本
将 SQLite 数据库中的用户同步到 users_db.json
用于修复历史数据不一致问题
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.auth_manager import get_auth_manager
from core.user_identity import get_user_identity_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_users():
    """
    同步 SQLite 数据库中的用户到 users_db.json
    """
    logger.info("=" * 60)
    logger.info("开始同步用户数据...")
    logger.info("=" * 60)

    # 获取管理器实例
    auth_manager = get_auth_manager()
    identity_manager = get_user_identity_manager()

    # 获取所有用户
    users = auth_manager.get_all_users()

    if not users:
        logger.warning("⚠️ SQLite 数据库中没有用户")
        return

    logger.info(f"📊 SQLite 数据库中找到 {len(users)} 个用户")

    synced_count = 0
    skipped_count = 0

    for user in users:
        user_id = str(user["id"])
        username = user["username"]
        email = user.get("email", f"{username}@example.com")

        # 检查是否已存在于 users_db.json
        existing_identity = identity_manager.get_user_identity(user_id)

        if existing_identity:
            logger.info(f"⏭️ 跳过用户 {username} (ID: {user_id}) - 已存在于 users_db.json")
            skipped_count += 1
            continue

        # 创建用户身份（使用默认值）
        try:
            identity_manager.create_user(
                user_id=user_id,
                username=username,
                real_name=username,  # 默认使用用户名
                email=email,
                phone="+852 0000 0000",  # 默认电话
                linkedin=None,
                github=None,
                location=None
            )

            logger.info(f"✅ 同步用户 {username} (ID: {user_id}) 到 users_db.json")
            synced_count += 1

        except Exception as e:
            logger.error(f"❌ 同步用户 {username} (ID: {user_id}) 失败: {e}")

    logger.info("=" * 60)
    logger.info(f"同步完成！")
    logger.info(f"  ✅ 成功同步: {synced_count} 个用户")
    logger.info(f"  ⏭️ 已存在跳过: {skipped_count} 个用户")
    logger.info(f"  📊 总计: {len(users)} 个用户")
    logger.info("=" * 60)

    # 显示所有用户列表
    logger.info("\n📋 当前所有用户:")
    logger.info("-" * 60)
    all_identities = identity_manager.get_all_users()
    for identity in all_identities:
        logger.info(f"  ID: {identity.user_id:3s} | 用户名: {identity.username:15s} | 真实姓名: {identity.real_name}")


if __name__ == "__main__":
    sync_users()
