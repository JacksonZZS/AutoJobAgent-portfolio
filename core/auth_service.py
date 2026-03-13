"""
认证服务 - 持久化登录（Remember Me）功能
"""

import os
import hmac
import hashlib
import time
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

# 从环境变量读取密钥，生产环境必须设置
# 支持 JWT_SECRET (docker-compose) 或 AUTH_SECRET_KEY
SECRET_KEY = os.environ.get("JWT_SECRET") or os.environ.get("AUTH_SECRET_KEY", "change-this-in-production-IMPORTANT")

# 数据库路径（使用绝对路径，与 auth_manager.py 保持一致）
DB_PATH = Path(__file__).parent.parent / "data/users.db"


def init_auth_tokens_table():
    """初始化认证 token 表"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # 创建 auth_tokens 表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS auth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 创建索引
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_auth_tokens_token
        ON auth_tokens(token)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_id
        ON auth_tokens(user_id)
    """)

    conn.commit()
    conn.close()


def generate_raw_token() -> str:
    """生成随机 token（32 字节）"""
    return os.urandom(32).hex()


def sign_token(raw: str) -> str:
    """对 token 进行 HMAC 签名，防止篡改"""
    sig = hmac.new(
        SECRET_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{raw}.{sig}"


def verify_token_signature(signed: str) -> Optional[str]:
    """验证 token 签名，返回原始 token"""
    try:
        raw, sig = signed.split(".", 1)
    except ValueError:
        return None

    expected_sig = hmac.new(
        SECRET_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        return None

    return raw


def issue_login_token(user_id: int, ttl_days: int = 7) -> Tuple[str, int]:
    """
    为用户颁发登录 token

    Args:
        user_id: 用户 ID
        ttl_days: token 有效期（天数），默认 7 天

    Returns:
        (signed_token, expires_at) 元组
    """
    init_auth_tokens_table()

    raw = generate_raw_token()
    signed = sign_token(raw)
    now = int(time.time())
    expires = now + ttl_days * 24 * 3600

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO auth_tokens (user_id, token, expires_at, created_at) VALUES (?,?,?,?)",
            (user_id, raw, expires, now),
        )
        conn.commit()
    finally:
        conn.close()

    return signed, expires


def verify_login_token(signed: str) -> Optional[int]:
    """
    验证登录 token

    Args:
        signed: 签名后的 token

    Returns:
        用户 ID，如果 token 无效则返回 None
    """
    # 验证签名
    raw = verify_token_signature(signed)
    if not raw:
        print(f"[Auth Debug] Token signature verification FAILED. SECRET_KEY starts with: {SECRET_KEY[:10]}...")
        return None

    print(f"[Auth Debug] Token signature OK, raw token: {raw[:16]}...")

    init_auth_tokens_table()

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    try:
        now = int(time.time())
        cur.execute(
            "SELECT user_id, expires_at, revoked FROM auth_tokens WHERE token=?",
            (raw,),
        )
        row = cur.fetchone()

        if not row:
            print(f"[Auth Debug] Token NOT FOUND in database")
            return None

        user_id, expires_at, revoked = row
        print(f"[Auth Debug] Token found: user_id={user_id}, expires_at={expires_at}, now={now}, revoked={revoked}")

        if expires_at <= now:
            print(f"[Auth Debug] Token EXPIRED")
            return None

        if revoked:
            print(f"[Auth Debug] Token REVOKED")
            return None

        return user_id
    finally:
        conn.close()


def revoke_token(signed: str) -> bool:
    """
    撤销 token（用于登出）

    Args:
        signed: 签名后的 token

    Returns:
        是否成功撤销
    """
    raw = verify_token_signature(signed)
    if not raw:
        return False

    init_auth_tokens_table()

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    try:
        cur.execute(
            "UPDATE auth_tokens SET revoked=1 WHERE token=?",
            (raw,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def revoke_all_user_tokens(user_id: int) -> int:
    """
    撤销用户的所有 token（用于"退出所有设备"）

    Args:
        user_id: 用户 ID

    Returns:
        撤销的 token 数量
    """
    init_auth_tokens_table()

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    try:
        cur.execute(
            "UPDATE auth_tokens SET revoked=1 WHERE user_id=? AND revoked=0",
            (user_id,)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def cleanup_expired_tokens():
    """清理过期的 token（定期维护任务）"""
    init_auth_tokens_table()

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    try:
        now = int(time.time())
        cur.execute(
            "DELETE FROM auth_tokens WHERE expires_at<?",
            (now,)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    """
    根据 ID 获取用户信息

    Args:
        user_id: 用户 ID

    Returns:
        用户信息字典，如果不存在则返回 None
    """
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT id, username, email, created_at FROM users WHERE id=?",
            (user_id,)
        )
        row = cur.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "created_at": row[3]
        }
    finally:
        conn.close()


# 初始化表（模块加载时）
init_auth_tokens_table()
