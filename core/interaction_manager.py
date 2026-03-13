"""
交互管理器 - 基于文件信号的 Web 交互控制（支持多用户数据隔离）
替代传统的 input() 阻塞，实现 Web 端控制流程
"""

import json
import time
import os
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class InteractionManager:
    """
    交互管理器 - 支持多用户数据隔离

    通过文件信号实现 Web 端与后台脚本的交互控制
    替代传统的 input() 阻塞方式
    每个用户拥有独立的信号文件：
    - data/signals/signal_{user_id}.json
    """

    def __init__(self, user_id: Optional[str] = None, signal_file: Optional[str] = None):
        """
        初始化交互管理器

        Args:
            user_id: 用户 ID，用于多用户数据隔离（推荐使用）
            signal_file: 信号文件路径（向后兼容，不推荐）

        优先级：
        1. 如果提供 user_id，使用 data/signals/signal_{user_id}.json
        2. 如果提供 signal_file，使用指定路径
        3. 否则使用默认路径 data/user_signal.json（向后兼容）
        """
        self.base_dir = Path(__file__).parent.parent
        self.user_id = user_id

        # 🔴 多用户隔离：根据 user_id 动态生成文件路径
        if user_id:
            self.signal_file = self.base_dir / "data" / "signals" / f"signal_{user_id}.json"
            logger.info(f"InteractionManager initialized for user: {user_id}")
        elif signal_file:
            self.signal_file = self.base_dir / signal_file
            logger.warning("InteractionManager using custom path (not recommended for multi-user)")
        else:
            # 向后兼容：默认路径
            self.signal_file = self.base_dir / "data/user_signal.json"
            logger.warning("InteractionManager using default path (not suitable for multi-user)")

        # 确保目录存在
        self.signal_file.parent.mkdir(parents=True, exist_ok=True)

        # 初始化信号文件
        self.reset_signal()

        logger.debug(f"Signal file: {self.signal_file}")

    def reset_signal(self) -> None:
        """重置信号为等待状态"""
        try:
            with open(self.signal_file, "w", encoding="utf-8") as f:
                json.dump({"action": "waiting", "timestamp": time.time()}, f, indent=2)
            logger.debug("Signal reset to 'waiting'")
        except Exception as e:
            logger.error(f"Failed to reset signal: {e}")

    def set_signal(self, action: str, data: Optional[dict] = None) -> None:
        """
        设置信号

        Args:
            action: 动作类型 (continue, cancel, etc.)
            data: 附加数据
        """
        try:
            signal_data = {
                "action": action,
                "timestamp": time.time()
            }
            if data:
                signal_data.update(data)

            with open(self.signal_file, "w", encoding="utf-8") as f:
                json.dump(signal_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Signal set to '{action}'")
        except Exception as e:
            logger.error(f"Failed to set signal: {e}")

    def read_signal(self) -> Optional[dict]:
        """
        读取当前信号

        Returns:
            信号数据字典，如果读取失败返回 None
        """
        try:
            if self.signal_file.exists():
                with open(self.signal_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Failed to read signal: {e}")
            return None

    def wait_for_continue(self, timeout: int = 300, check_interval: float = 1.0) -> bool:
        """
        循环等待 Web 端发出 continue 信号

        Args:
            timeout: 超时时间（秒），默认 5 分钟
            check_interval: 检查间隔（秒），默认 1 秒

        Returns:
            True 如果收到 continue 信号，False 如果超时或取消
        """
        logger.info(f"Waiting for user signal (timeout: {timeout}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            signal = self.read_signal()

            if signal:
                action = signal.get("action")

                if action == "continue":
                    logger.info("Received 'continue' signal from user")
                    self.reset_signal()  # 重置以便下次使用
                    return True

                elif action == "cancel":
                    logger.warning("Received 'cancel' signal from user")
                    self.reset_signal()
                    return False

            time.sleep(check_interval)

        logger.warning(f"Wait timeout after {timeout}s")
        return False

    def wait_for_user_action(
        self,
        message: str,
        timeout: int = 300,
        check_interval: float = 1.0
    ) -> bool:
        """
        等待用户操作（带消息提示）

        Args:
            message: 提示消息
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            True 如果用户确认继续，False 如果取消或超时
        """
        logger.info(f"Waiting for user action: {message}")

        # 设置等待状态信号（包含消息）
        self.set_signal("waiting", {"message": message})

        # 等待用户响应
        return self.wait_for_continue(timeout=timeout, check_interval=check_interval)


# 全局单例实例字典（支持多用户）
_interaction_manager_instances: Dict[str, InteractionManager] = {}


def get_interaction_manager(user_id: Optional[str] = None) -> InteractionManager:
    """
    获取交互管理器实例（支持多用户单例模式）

    Args:
        user_id: 用户 ID，用于多用户数据隔离

    Returns:
        InteractionManager 实例

    说明：
    - 如果提供 user_id，返回该用户的专属实例
    - 如果不提供 user_id，返回默认实例（向后兼容）
    - 每个 user_id 对应一个独立的单例实例
    """
    global _interaction_manager_instances

    # 使用 user_id 作为 key，如果没有则使用 "default"
    key = user_id if user_id else "default"

    if key not in _interaction_manager_instances:
        _interaction_manager_instances[key] = InteractionManager(user_id=user_id)
        logger.debug(f"Created new InteractionManager instance for: {key}")

    return _interaction_manager_instances[key]
