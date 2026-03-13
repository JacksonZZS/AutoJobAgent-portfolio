"""
认证管理器 - 基于 SQLite 的多用户认证系统
支持用户注册、登录、密码加密存储
"""

import sqlite3
import hashlib
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class AuthManager:
    """
    认证管理器

    功能：
    - 用户注册（密码加密存储）
    - 用户登录验证
    - 用户信息查询
    - 密码修改
    """

    def __init__(self, db_path: str = "data/users.db"):
        """
        初始化认证管理器

        Args:
            db_path: 数据库文件路径
        """
        self.base_dir = Path(__file__).parent.parent
        self.db_path = self.base_dir / db_path

        # 确保数据库目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        logger.info(f"AuthManager initialized with database: {self.db_path}")

    def _init_database(self):
        """初始化数据库表结构"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建用户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email TEXT,
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_username
                ON users(username)
            """)

            conn.commit()
            conn.close()

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _hash_password(self, password: str) -> str:
        """
        密码加密

        使用 SHA-256 + Salt 进行密码加密

        Args:
            password: 明文密码

        Returns:
            加密后的密码哈希
        """
        # 使用固定的 salt（生产环境应该为每个用户生成随机 salt）
        salt = "autojobagent_salt_2026"
        salted_password = f"{password}{salt}"

        # SHA-256 加密
        password_hash = hashlib.sha256(salted_password.encode()).hexdigest()

        return password_hash

    def register(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        real_name: Optional[str] = None,
        phone: Optional[str] = None,
        linkedin: Optional[str] = None,
        github: Optional[str] = None,
        location: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        用户注册（同步写入 SQLite 和 users_db.json）

        Args:
            username: 用户名（唯一）
            password: 密码
            email: 邮箱（可选）
            real_name: 真实姓名（可选）
            phone: 电话（可选）
            linkedin: LinkedIn（可选）
            github: GitHub（可选）
            location: 位置（可选）

        Returns:
            (成功标志, 消息)
        """
        try:
            # 验证输入
            if not username or not password:
                return False, "用户名和密码不能为空"

            if len(username) < 3:
                return False, "用户名至少需要 3 个字符"

            if len(password) < 6:
                return False, "密码至少需要 6 个字符"

            # 检查用户名是否已存在
            if self.user_exists(username):
                return False, f"用户名 '{username}' 已被注册"

            # 加密密码
            password_hash = self._hash_password(password)
            print(f"[Register Debug] Creating user: {username}, db_path={self.db_path}")

            # 插入 SQLite 数据库
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO users (username, password_hash, email, created_at)
                VALUES (?, ?, ?, ?)
            """, (username, password_hash, email, datetime.now().isoformat()))

            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            print(f"[Register Debug] User created successfully: id={user_id}, username={username}")

            # 🔴 同步写入 users_db.json
            from core.user_identity import get_user_identity_manager

            identity_manager = get_user_identity_manager()
            identity_manager.create_user(
                user_id=str(user_id),
                username=username,
                real_name=real_name or username,
                email=email or f"{username}@example.com",
                phone=phone or "+852 0000 0000",
                linkedin=linkedin,
                github=github,
                location=location
            )

            logger.info(f"User registered successfully: {username} (ID: {user_id})")
            logger.info(f"User identity synced to users_db.json: {username}")
            return True, f"用户 '{username}' 注册成功"

        except sqlite3.IntegrityError as e:
            logger.error(f"Registration failed (integrity error): {e}")
            return False, "用户名已存在"
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return False, f"注册失败: {str(e)}"

    def login(self, username: str, password: str) -> Tuple[bool, Optional[Dict], str]:
        """
        用户登录验证

        Args:
            username: 用户名
            password: 密码

        Returns:
            (成功标志, 用户信息字典, 消息)
        """
        try:
            # 验证输入
            if not username or not password:
                return False, None, "用户名和密码不能为空"

            # 加密密码
            password_hash = self._hash_password(password)
            print(f"[Login Debug] username={username}, hash={password_hash[:16]}...")

            # 查询数据库
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 先检查用户是否存在
            cursor.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
            user_row = cursor.fetchone()
            if user_row:
                print(f"[Login Debug] User found: id={user_row[0]}, stored_hash={user_row[2][:16]}...")
            else:
                print(f"[Login Debug] User NOT FOUND: {username}")

            cursor.execute("""
                SELECT id, username, email, created_at, is_active
                FROM users
                WHERE username = ? AND password_hash = ?
            """, (username, password_hash))

            result = cursor.fetchone()

            if result:
                user_id, username, email, created_at, is_active = result

                # 检查账户是否激活
                if not is_active:
                    conn.close()
                    return False, None, "账户已被禁用"

                # 更新最后登录时间
                cursor.execute("""
                    UPDATE users
                    SET last_login = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), user_id))

                conn.commit()
                conn.close()

                # 返回用户信息
                user_info = {
                    "id": user_id,
                    "username": username,
                    "email": email,
                    "created_at": created_at
                }

                logger.info(f"User logged in successfully: {username}")
                return True, user_info, "登录成功"
            else:
                conn.close()
                return False, None, "用户名或密码错误"

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False, None, f"登录失败: {str(e)}"

    def user_exists(self, username: str) -> bool:
        """
        检查用户是否存在

        Args:
            username: 用户名

        Returns:
            True 如果用户存在，否则 False
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) FROM users WHERE username = ?
            """, (username,))

            count = cursor.fetchone()[0]
            conn.close()

            return count > 0

        except Exception as e:
            logger.error(f"Failed to check user existence: {e}")
            return False

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """
        根据用户 ID 获取用户信息

        Args:
            user_id: 用户 ID

        Returns:
            用户信息字典，如果不存在返回 None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, username, email, created_at, last_login
                FROM users
                WHERE id = ? AND is_active = 1
            """, (user_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                user_id, username, email, created_at, last_login = result
                return {
                    "id": user_id,
                    "username": username,
                    "email": email,
                    "created_at": created_at,
                    "last_login": last_login
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get user by ID: {e}")
            return None

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """
        根据用户名获取用户信息

        Args:
            username: 用户名

        Returns:
            用户信息字典，如果不存在返回 None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, username, email, created_at, last_login
                FROM users
                WHERE username = ? AND is_active = 1
            """, (username,))

            result = cursor.fetchone()
            conn.close()

            if result:
                user_id, username, email, created_at, last_login = result
                return {
                    "id": user_id,
                    "username": username,
                    "email": email,
                    "created_at": created_at,
                    "last_login": last_login
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get user by username: {e}")
            return None

    def change_password(
        self,
        username: str,
        old_password: str,
        new_password: str
    ) -> Tuple[bool, str]:
        """
        修改密码

        Args:
            username: 用户名
            old_password: 旧密码
            new_password: 新密码

        Returns:
            (成功标志, 消息)
        """
        try:
            # 验证旧密码
            success, user_info, message = self.login(username, old_password)
            if not success:
                return False, "旧密码错误"

            # 验证新密码
            if len(new_password) < 6:
                return False, "新密码至少需要 6 个字符"

            # 加密新密码
            new_password_hash = self._hash_password(new_password)

            # 更新数据库
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users
                SET password_hash = ?
                WHERE username = ?
            """, (new_password_hash, username))

            conn.commit()
            conn.close()

            logger.info(f"Password changed successfully for user: {username}")
            return True, "密码修改成功"

        except Exception as e:
            logger.error(f"Failed to change password: {e}")
            return False, f"密码修改失败: {str(e)}"

    def get_all_users(self) -> list:
        """
        获取所有用户列表（管理员功能）

        Returns:
            用户列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, username, email, created_at, last_login, is_active
                FROM users
                ORDER BY created_at DESC
            """)

            results = cursor.fetchall()
            conn.close()

            users = []
            for row in results:
                user_id, username, email, created_at, last_login, is_active = row
                users.append({
                    "id": user_id,
                    "username": username,
                    "email": email,
                    "created_at": created_at,
                    "last_login": last_login,
                    "is_active": bool(is_active)
                })

            return users

        except Exception as e:
            logger.error(f"Failed to get all users: {e}")
            return []


# 全局单例实例
_auth_manager_instance: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """
    获取全局认证管理器实例（单例模式）

    Returns:
        AuthManager 实例
    """
    global _auth_manager_instance
    if _auth_manager_instance is None:
        _auth_manager_instance = AuthManager()
    return _auth_manager_instance
