"""
会话管理器 - 持久化登录状态
支持"记住我"功能，用户无需每次打开应用都登录
"""

import json
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """
    会话管理器

    功能：
    - 创建和保存登录会话
    - 验证会话令牌
    - 自动清理过期会话
    """

    def __init__(self, session_dir: str = "data/sessions"):
        """
        初始化会话管理器

        Args:
            session_dir: 会话文件存储目录
        """
        self.base_dir = Path(__file__).parent.parent
        self.session_dir = self.base_dir / session_dir

        # 确保会话目录存在
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # 默认会话有效期：30 天
        self.default_expiry_days = 30

        logger.info(f"SessionManager initialized with directory: {self.session_dir}")

    def create_session(
        self,
        user_id: int,
        username: str,
        email: str = "",
        expiry_days: int = None
    ) -> str:
        """
        创建新的登录会话并保存到文件

        Args:
            user_id: 用户 ID
            username: 用户名
            email: 邮箱
            expiry_days: 会话有效期（天），默认 30 天

        Returns:
            会话令牌（用于后续验证）
        """
        try:
            # 生成安全的会话令牌
            token = secrets.token_urlsafe(32)

            # 计算过期时间
            if expiry_days is None:
                expiry_days = self.default_expiry_days

            expiry_time = datetime.now() + timedelta(days=expiry_days)

            # 创建会话数据
            session_data = {
                "token": token,
                "user_id": user_id,
                "username": username,
                "email": email,
                "created_at": datetime.now().isoformat(),
                "expires_at": expiry_time.isoformat(),
                "last_accessed": datetime.now().isoformat()
            }

            # 保存到文件（使用 user_id 作为文件名）
            session_file = self.session_dir / f"session_{user_id}.json"
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Session created for user {username} (ID: {user_id}), expires at {expiry_time}")
            return token

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return None

    def verify_session(self, user_id: int, token: str) -> Optional[Dict]:
        """
        验证会话令牌是否有效

        Args:
            user_id: 用户 ID
            token: 会话令牌

        Returns:
            如果有效返回用户信息字典，否则返回 None
        """
        try:
            session_file = self.session_dir / f"session_{user_id}.json"

            # 检查会话文件是否存在
            if not session_file.exists():
                logger.debug(f"Session file not found for user {user_id}")
                return None

            # 读取会话数据
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            # 验证令牌
            if session_data.get("token") != token:
                logger.warning(f"Invalid token for user {user_id}")
                return None

            # 检查是否过期
            expires_at = datetime.fromisoformat(session_data["expires_at"])
            if datetime.now() > expires_at:
                logger.info(f"Session expired for user {user_id}")
                # 删除过期的会话文件
                session_file.unlink()
                return None

            # 更新最后访问时间
            session_data["last_accessed"] = datetime.now().isoformat()
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            # 返回用户信息
            user_info = {
                "id": session_data["user_id"],
                "username": session_data["username"],
                "email": session_data.get("email", "")
            }

            logger.debug(f"Session verified for user {session_data['username']}")
            return user_info

        except Exception as e:
            logger.error(f"Failed to verify session: {e}")
            return None

    def delete_session(self, user_id: int):
        """
        删除用户的会话（登出时调用）

        Args:
            user_id: 用户 ID
        """
        try:
            session_file = self.session_dir / f"session_{user_id}.json"

            if session_file.exists():
                session_file.unlink()
                logger.info(f"Session deleted for user {user_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

    def cleanup_expired_sessions(self):
        """
        清理所有过期的会话文件
        """
        try:
            cleaned_count = 0

            for session_file in self.session_dir.glob("session_*.json"):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)

                    expires_at = datetime.fromisoformat(session_data["expires_at"])
                    if datetime.now() > expires_at:
                        session_file.unlink()
                        cleaned_count += 1
                        logger.debug(f"Cleaned expired session: {session_file.name}")

                except Exception as e:
                    logger.warning(f"Failed to process {session_file.name}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(f"Cleaned {cleaned_count} expired sessions")

            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
            return 0


# 全局单例实例
_session_manager_instance: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    获取全局会话管理器实例（单例模式）

    Returns:
        SessionManager 实例
    """
    global _session_manager_instance
    if _session_manager_instance is None:
        _session_manager_instance = SessionManager()
    return _session_manager_instance
