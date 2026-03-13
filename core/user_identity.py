"""
用户身份管理模块 - 多租户身份解耦
支持从数据库动态提取用户真实信息，用于简历和求职信生成
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class UserIdentity:
    """用户身份信息"""
    user_id: str
    username: str
    real_name: str
    email: str
    phone: str
    created_at: str
    updated_at: str

    # 可选字段
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    location: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserIdentity':
        """从字典创建实例"""
        return cls(**data)


class UserIdentityManager:
    """
    用户身份管理器

    负责：
    1. 从数据库（JSON 文件模拟）读取用户真实信息
    2. 提供用户身份查询接口
    3. 确保简历生成时使用正确的用户信息
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化用户身份管理器

        Args:
            db_path: 用户数据库文件路径（默认为 data/users_db.json）
        """
        if db_path is None:
            # 🔴 使用绝对路径，防止 Streamlit 环境下路径偏离
            import os
            project_root = Path(__file__).parent.parent
            db_path = project_root / "data" / "users_db.json"
            # 转换为绝对路径
            db_path = db_path.resolve()

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 确保数据库文件存在
        if not self.db_path.exists():
            self._initialize_db()

        logger.info(f"UserIdentityManager initialized with db: {self.db_path}")

    def _initialize_db(self):
        """初始化数据库（创建默认用户）"""
        default_users = {
            "jacksonzhang1221": {
                "user_id": "jacksonzhang1221",
                "username": "jacksonzhang1221",
                "real_name": "Jackson Zhang",
                "email": "jackson.zhang@example.com",
                "phone": "+852 1234 5678",
                "linkedin": "https://linkedin.com/in/jacksonzhang",
                "github": "https://github.com/jacksonzhang",
                "location": "Hong Kong",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        }

        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(default_users, f, indent=2, ensure_ascii=False)

        logger.info(f"Initialized user database with {len(default_users)} default users")

    def _read_db(self, max_retries: int = 3, retry_delay: float = 0.2) -> Dict[str, Dict]:
        """
        读取数据库（带重试机制）

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）

        Returns:
            用户数据字典
        """
        import time

        for attempt in range(max_retries):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.debug(f"Successfully read user database (attempt {attempt + 1}/{max_retries})")
                    return data
            except FileNotFoundError:
                logger.error(f"User database file not found: {self.db_path}")
                return {}
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse user database JSON (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return {}
            except Exception as e:
                logger.error(f"Failed to read user database (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return {}

        logger.error(f"Failed to read user database after {max_retries} attempts")
        return {}

    def _write_db(self, data: Dict[str, Dict]):
        """写入数据库"""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to write user database: {e}")

    def get_user_identity(self, user_id: str) -> Optional[UserIdentity]:
        """
        获取用户身份信息（带动态重载）

        Args:
            user_id: 用户 ID

        Returns:
            UserIdentity 对象，如果用户不存在则返回 None
        """
        # 🔴 强制类型转换：统一为字符串
        user_id = str(user_id)

        # 🔴 第一次尝试：从数据库读取
        db = self._read_db()

        if user_id not in db:
            # 🔴 强制重载：立即重新读取物理文件
            logger.info(f"User {user_id} not found in cache, forcing reload from disk...")
            db = self._read_db()

            if user_id not in db:
                logger.warning(f"User not found after reload: {user_id}")
                logger.warning(f"Available users in database: {list(db.keys())}")
                return None

        try:
            user_identity = UserIdentity.from_dict(db[user_id])
            logger.debug(f"Successfully loaded user identity: {user_id} ({user_identity.username})")
            return user_identity
        except Exception as e:
            logger.error(f"Failed to parse user identity for {user_id}: {e}")
            return None

    def create_user(
        self,
        user_id: str,
        username: str,
        real_name: str,
        email: str,
        phone: str,
        **kwargs
    ) -> UserIdentity:
        """
        创建新用户

        Args:
            user_id: 用户 ID
            username: 用户名
            real_name: 真实姓名
            email: 邮箱
            phone: 电话
            **kwargs: 其他可选字段（linkedin, github, portfolio, location）

        Returns:
            创建的 UserIdentity 对象
        """
        # 🔴 强制类型转换：统一为字符串
        user_id = str(user_id)

        db = self._read_db()

        if user_id in db:
            logger.warning(f"User already exists: {user_id}")
            return self.get_user_identity(user_id)

        now = datetime.now().isoformat()

        user_data = {
            "user_id": user_id,
            "username": username,
            "real_name": real_name,
            "email": email,
            "phone": phone,
            "created_at": now,
            "updated_at": now,
            **kwargs
        }

        db[user_id] = user_data
        self._write_db(db)

        logger.info(f"Created new user: {user_id} ({real_name})")

        return UserIdentity.from_dict(user_data)

    def update_user(self, user_id: str, **updates) -> Optional[UserIdentity]:
        """
        更新用户信息

        Args:
            user_id: 用户 ID
            **updates: 要更新的字段

        Returns:
            更新后的 UserIdentity 对象，如果用户不存在则返回 None
        """
        # 🔴 强制类型转换：统一为字符串
        user_id = str(user_id)

        db = self._read_db()

        if user_id not in db:
            logger.warning(f"User not found: {user_id}")
            return None

        db[user_id].update(updates)
        db[user_id]["updated_at"] = datetime.now().isoformat()

        self._write_db(db)

        logger.info(f"Updated user: {user_id}")

        return UserIdentity.from_dict(db[user_id])

    def delete_user(self, user_id: str) -> bool:
        """
        删除用户

        Args:
            user_id: 用户 ID

        Returns:
            是否删除成功
        """
        # 🔴 强制类型转换：统一为字符串
        user_id = str(user_id)

        db = self._read_db()

        if user_id not in db:
            logger.warning(f"User not found: {user_id}")
            return False

        del db[user_id]
        self._write_db(db)

        logger.info(f"Deleted user: {user_id}")

        return True

    def list_all_users(self) -> Dict[str, UserIdentity]:
        """
        列出所有用户

        Returns:
            用户 ID 到 UserIdentity 的映射
        """
        db = self._read_db()

        users = {}
        for user_id, user_data in db.items():
            try:
                users[user_id] = UserIdentity.from_dict(user_data)
            except Exception as e:
                logger.error(f"Failed to parse user {user_id}: {e}")

        return users

    def get_username_by_id(self, user_id: str) -> str:
        """
        根据 user_id 获取 username（用于 UI 显示）

        Args:
            user_id: 用户 ID

        Returns:
            用户名，如果不存在则返回 user_id 本身
        """
        identity = self.get_user_identity(user_id)
        return identity.username if identity else user_id

    def get_real_name_by_id(self, user_id: str) -> str:
        """
        根据 user_id 获取真实姓名（用于简历生成）

        Args:
            user_id: 用户 ID

        Returns:
            真实姓名，如果不存在则返回 "Unknown User"
        """
        identity = self.get_user_identity(user_id)
        return identity.real_name if identity else "Unknown User"

    def validate_user_for_cv_generation(self, user_id: str) -> bool:
        """
        验证用户信息是否完整，可以用于简历生成

        Args:
            user_id: 用户 ID

        Returns:
            是否可以生成简历
        """
        identity = self.get_user_identity(user_id)

        if not identity:
            logger.error(f"User not found: {user_id}")
            return False

        # 检查必填字段
        required_fields = ["real_name", "email", "phone"]
        missing_fields = [f for f in required_fields if not getattr(identity, f, None)]

        if missing_fields:
            logger.error(f"User {user_id} missing required fields: {missing_fields}")
            return False

        return True


# 全局单例实例
_user_identity_manager: Optional[UserIdentityManager] = None


def get_user_identity_manager() -> UserIdentityManager:
    """
    获取用户身份管理器单例

    Returns:
        UserIdentityManager 实例
    """
    global _user_identity_manager

    if _user_identity_manager is None:
        _user_identity_manager = UserIdentityManager()

    return _user_identity_manager


# 便捷函数
def get_user_identity(user_id: str) -> Optional[UserIdentity]:
    """获取用户身份信息（便捷函数）"""
    return get_user_identity_manager().get_user_identity(user_id)


def get_username(user_id: str) -> str:
    """获取用户名（便捷函数）"""
    return get_user_identity_manager().get_username_by_id(user_id)


def get_real_name(user_id: str) -> str:
    """获取真实姓名（便捷函数）"""
    return get_user_identity_manager().get_real_name_by_id(user_id)


def validate_user_for_cv(user_id: str) -> bool:
    """验证用户是否可以生成简历（便捷函数）"""
    return get_user_identity_manager().validate_user_for_cv_generation(user_id)
