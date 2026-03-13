"""
全局监控模块 - SaaS 级别的系统监控和日志管理

功能：
1. 维护 global_monitor.json 记录系统级状态
2. 提供多用户任务状态聚合
3. 记录最近事件日志（带用户前缀）
4. 支持管理员监控视图
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from threading import Lock
import time

logger = logging.getLogger(__name__)

# 全局监控文件路径
GLOBAL_MONITOR_FILE = Path(__file__).parent.parent / "data" / "global_monitor.json"
GLOBAL_MONITOR_FILE.parent.mkdir(parents=True, exist_ok=True)

# 文件锁（避免并发写入冲突）
_MONITOR_LOCK = Lock()

# 最近事件的最大保留数量
MAX_RECENT_EVENTS = 100


class GlobalMonitor:
    """全局监控管理器"""

    def __init__(self, monitor_file: Optional[Path] = None):
        """
        初始化全局监控管理器

        Args:
            monitor_file: 监控文件路径（默认使用 GLOBAL_MONITOR_FILE）
        """
        self.monitor_file = monitor_file or GLOBAL_MONITOR_FILE
        self._ensure_initialized()

    def _ensure_initialized(self):
        """确保监控文件已初始化"""
        if not self.monitor_file.exists():
            initial_data = {
                "updated_at": datetime.now().isoformat(),
                "system": {
                    "max_browser_instances": 2,
                    "current_browser_instances": 0,
                    "queue_length": 0,
                    "node_id": os.getenv("NODE_ID", "worker-1"),
                    "uptime_seconds": 0,
                    "start_time": datetime.now().isoformat()
                },
                "users": {},
                "recent_events": []
            }
            self._write_monitor_data(initial_data)
            logger.info(f"Initialized global monitor file: {self.monitor_file}")

    def _read_monitor_data(self) -> Dict:
        """
        读取监控数据（带重试和容错）

        Returns:
            监控数据字典
        """
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with open(self.monitor_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to read monitor file (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to read monitor file after {max_retries} attempts, returning empty data")
                    return self._get_default_data()
            except Exception as e:
                logger.error(f"Unexpected error reading monitor file: {e}")
                return self._get_default_data()

        return self._get_default_data()

    def _write_monitor_data(self, data: Dict):
        """
        写入监控数据（原子操作）

        Args:
            data: 监控数据字典
        """
        with _MONITOR_LOCK:
            try:
                # 更新时间戳
                data["updated_at"] = datetime.now().isoformat()

                # 原子写入：先写临时文件，再替换
                temp_file = self.monitor_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                temp_file.replace(self.monitor_file)
                logger.debug("Monitor data written successfully")

            except Exception as e:
                logger.error(f"Failed to write monitor data: {e}")

    def _get_default_data(self) -> Dict:
        """获取默认监控数据"""
        return {
            "updated_at": datetime.now().isoformat(),
            "system": {
                "max_browser_instances": 2,
                "current_browser_instances": 0,
                "queue_length": 0,
                "node_id": os.getenv("NODE_ID", "worker-1"),
                "uptime_seconds": 0,
                "start_time": datetime.now().isoformat()
            },
            "users": {},
            "recent_events": []
        }

    def update_system_status(
        self,
        current_browser_instances: Optional[int] = None,
        queue_length: Optional[int] = None
    ):
        """
        更新系统级状态

        Args:
            current_browser_instances: 当前浏览器实例数
            queue_length: 等待队列长度
        """
        data = self._read_monitor_data()

        if current_browser_instances is not None:
            data["system"]["current_browser_instances"] = current_browser_instances

        if queue_length is not None:
            data["system"]["queue_length"] = queue_length

        # 更新运行时间
        start_time = datetime.fromisoformat(data["system"]["start_time"])
        uptime = (datetime.now() - start_time).total_seconds()
        data["system"]["uptime_seconds"] = int(uptime)

        self._write_monitor_data(data)

    def update_user_status(
        self,
        user_id: str,
        username: str,
        active_jobs: Optional[int] = None,
        total_jobs: Optional[int] = None,
        last_job_id: Optional[str] = None,
        last_job_status: Optional[str] = None,
        last_score: Optional[int] = None,
        last_decision: Optional[str] = None,
        last_error: Optional[str] = None
    ):
        """
        更新用户状态

        Args:
            user_id: 用户 ID
            username: 用户名
            active_jobs: 活跃任务数
            total_jobs: 总任务数
            last_job_id: 最后一个任务 ID
            last_job_status: 最后一个任务状态
            last_score: 最后一个任务评分
            last_decision: 最后一个任务决策
            last_error: 最后一个错误信息
        """
        data = self._read_monitor_data()

        if user_id not in data["users"]:
            data["users"][user_id] = {
                "username": username,
                "last_seen": datetime.now().isoformat(),
                "active_jobs": 0,
                "total_jobs": 0,
                "last_job_id": None,
                "last_job_status": None,
                "last_score": None,
                "last_decision": None,
                "last_error": None
            }

        user_data = data["users"][user_id]
        user_data["username"] = username
        user_data["last_seen"] = datetime.now().isoformat()

        if active_jobs is not None:
            user_data["active_jobs"] = active_jobs
        if total_jobs is not None:
            user_data["total_jobs"] = total_jobs
        if last_job_id is not None:
            user_data["last_job_id"] = last_job_id
        if last_job_status is not None:
            user_data["last_job_status"] = last_job_status
        if last_score is not None:
            user_data["last_score"] = last_score
        if last_decision is not None:
            user_data["last_decision"] = last_decision
        if last_error is not None:
            user_data["last_error"] = last_error

        self._write_monitor_data(data)

    def add_event(
        self,
        user_id: str,
        username: str,
        level: str,
        event_type: str,
        message: str,
        job_id: Optional[str] = None,
        extra: Optional[Dict] = None
    ):
        """
        添加事件到最近事件列表

        Args:
            user_id: 用户 ID
            username: 用户名
            level: 日志级别（INFO, WARNING, ERROR）
            event_type: 事件类型（job_started, job_completed, browser_error, etc.）
            message: 事件消息
            job_id: 关联的任务 ID（可选）
            extra: 额外信息（可选）
        """
        data = self._read_monitor_data()

        event = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "username": username,
            "level": level,
            "event_type": event_type,
            "job_id": job_id,
            "message": message,
            "extra": extra or {}
        }

        data["recent_events"].insert(0, event)  # 最新的在前面

        # 限制事件数量
        if len(data["recent_events"]) > MAX_RECENT_EVENTS:
            data["recent_events"] = data["recent_events"][:MAX_RECENT_EVENTS]

        self._write_monitor_data(data)

        # 同时记录到标准日志（带用户前缀）
        log_message = f"[User: {username}] {message}"
        if level == "ERROR":
            logger.error(log_message)
        elif level == "WARNING":
            logger.warning(log_message)
        else:
            logger.info(log_message)

    def get_system_metrics(self) -> Dict:
        """
        获取系统指标（用于监控 UI）

        Returns:
            {
                "max_browser_instances": 2,
                "current_browser_instances": 1,
                "available_slots": 1,
                "queue_length": 0,
                "uptime_seconds": 3600,
                "node_id": "worker-1"
            }
        """
        data = self._read_monitor_data()
        system = data.get("system", {})

        current = system.get("current_browser_instances", 0)
        max_instances = system.get("max_browser_instances", 2)

        return {
            "max_browser_instances": max_instances,
            "current_browser_instances": current,
            "available_slots": max(0, max_instances - current),
            "queue_length": system.get("queue_length", 0),
            "uptime_seconds": system.get("uptime_seconds", 0),
            "node_id": system.get("node_id", "unknown")
        }

    def get_all_users_status(self) -> Dict[str, Dict]:
        """
        获取所有用户状态（用于管理员监控）

        Returns:
            {
                "user_123": {
                    "username": "alice",
                    "last_seen": "2026-01-21T12:34:00Z",
                    "active_jobs": 1,
                    "total_jobs": 23,
                    ...
                },
                ...
            }
        """
        data = self._read_monitor_data()
        return data.get("users", {})

    def get_user_status(self, user_id: str) -> Optional[Dict]:
        """
        获取单个用户状态

        Args:
            user_id: 用户 ID

        Returns:
            用户状态字典，如果用户不存在则返回 None
        """
        data = self._read_monitor_data()
        return data.get("users", {}).get(user_id)

    def get_recent_events(self, limit: int = 20, user_id: Optional[str] = None) -> List[Dict]:
        """
        获取最近事件列表

        Args:
            limit: 返回的事件数量限制
            user_id: 如果指定，只返回该用户的事件

        Returns:
            事件列表
        """
        data = self._read_monitor_data()
        events = data.get("recent_events", [])

        if user_id:
            events = [e for e in events if e.get("user_id") == user_id]

        return events[:limit]

    def reset_user_data(self, user_id: str):
        """
        重置用户数据（用于"重置搜索记忆"功能）

        Args:
            user_id: 用户 ID
        """
        data = self._read_monitor_data()

        if user_id in data["users"]:
            # 保留用户名和最后访问时间，重置其他数据
            username = data["users"][user_id].get("username", "unknown")
            data["users"][user_id] = {
                "username": username,
                "last_seen": datetime.now().isoformat(),
                "active_jobs": 0,
                "total_jobs": 0,
                "last_job_id": None,
                "last_job_status": None,
                "last_score": None,
                "last_decision": None,
                "last_error": None
            }

            self._write_monitor_data(data)

            # 记录重置事件
            self.add_event(
                user_id=user_id,
                username=username,
                level="INFO",
                event_type="user_reset",
                message="用户数据已重置"
            )

            logger.info(f"[User: {username}] User data reset successfully")


# 全局单例实例
_global_monitor_instance: Optional[GlobalMonitor] = None


def get_global_monitor() -> GlobalMonitor:
    """
    获取全局监控管理器单例

    Returns:
        GlobalMonitor 实例
    """
    global _global_monitor_instance

    if _global_monitor_instance is None:
        _global_monitor_instance = GlobalMonitor()

    return _global_monitor_instance


# 🔴 便捷函数：用于快速记录事件
def log_user_event(
    user_id: str,
    username: str,
    level: str,
    event_type: str,
    message: str,
    job_id: Optional[str] = None,
    extra: Optional[Dict] = None
):
    """
    快速记录用户事件（便捷函数）

    Args:
        user_id: 用户 ID
        username: 用户名
        level: 日志级别
        event_type: 事件类型
        message: 事件消息
        job_id: 任务 ID（可选）
        extra: 额外信息（可选）
    """
    monitor = get_global_monitor()
    monitor.add_event(
        user_id=user_id,
        username=username,
        level=level,
        event_type=event_type,
        message=message,
        job_id=job_id,
        extra=extra
    )


# 🔴 精准重置：物理删除 scanned_jobs_{user_id}.json
def reset_scanned_jobs(user_id: str, username: str = "unknown"):
    """
    精准重置：物理删除用户的扫描记录文件

    Args:
        user_id: 用户 ID
        username: 用户名（用于日志）
    """
    scanned_jobs_dir = Path(__file__).parent.parent / "data" / "scanned_jobs"
    scanned_jobs_file = scanned_jobs_dir / f"scanned_jobs_{user_id}.json"

    try:
        if scanned_jobs_file.exists():
            scanned_jobs_file.unlink()
            logger.info(f"[User: {username}] Deleted scanned jobs file: {scanned_jobs_file}")

            # 记录到全局监控
            log_user_event(
                user_id=user_id,
                username=username,
                level="INFO",
                event_type="scanned_jobs_reset",
                message=f"已删除扫描记录文件: {scanned_jobs_file.name}"
            )
        else:
            logger.info(f"[User: {username}] No scanned jobs file to delete")

    except Exception as e:
        logger.error(f"[User: {username}] Failed to delete scanned jobs file: {e}")
        log_user_event(
            user_id=user_id,
            username=username,
            level="ERROR",
            event_type="scanned_jobs_reset_failed",
            message=f"删除扫描记录文件失败: {str(e)}"
        )
