"""
WebSocket API 路由
提供实时状态推送，用于前端监控任务进度
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
import asyncio
import json
from datetime import datetime
from typing import Dict

# 导入核心业务模块
from core.status_manager import get_status_manager
from core.auth_service import verify_login_token

router = APIRouter(tags=["WebSocket"])


# ============================================================
# WebSocket 连接管理器
# ============================================================

class ConnectionManager:
    """
    WebSocket 连接管理器（单例模式）

    功能：
    - 管理所有活跃的 WebSocket 连接
    - 支持按 user_id 发送消息
    - 自动清理断开的连接
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        """
        接受 WebSocket 连接

        Args:
            user_id: 用户 ID
            websocket: WebSocket 连接对象
        """
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"[WebSocket] User {user_id} connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, user_id: str):
        """
        断开连接

        Args:
            user_id: 用户 ID
        """
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"[WebSocket] User {user_id} disconnected. Total connections: {len(self.active_connections)}")

    async def send_message(self, user_id: str, message: dict):
        """
        发送消息给指定用户

        Args:
            user_id: 用户 ID
            message: 消息内容（字典）
        """
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                print(f"[WebSocket] Error sending message to {user_id}: {e}")
                self.disconnect(user_id)

    async def broadcast(self, message: dict):
        """
        广播消息给所有连接的用户

        Args:
            message: 消息内容（字典）
        """
        disconnected = []
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WebSocket] Error broadcasting to {user_id}: {e}")
                disconnected.append(user_id)

        # 清理断开的连接
        for user_id in disconnected:
            self.disconnect(user_id)


# 全局连接管理器实例
manager = ConnectionManager()


# ============================================================
# WebSocket 端点
# ============================================================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(...)
):
    """
    WebSocket 连接端点

    **功能**：
    - 实时推送任务状态更新
    - 推送人工复核通知
    - 双向通信（接收用户决策）

    **连接方式**：
    ```javascript
    const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/${userId}?token=${jwtToken}`);
    ```

    **消息类型**：
    - `status_update`: 状态更新
    - `manual_review_required`: 需要人工复核
    - `task_completed`: 任务完成
    - `error`: 错误通知
    """

    # ============================================================
    # 1. 验证 JWT token
    # ============================================================
    verified_user_id = verify_login_token(token)
    print(f"[WebSocket Auth] user_id from URL: {user_id}, verified_user_id: {verified_user_id}")
    if not verified_user_id or str(verified_user_id) != user_id:
        print(f"[WebSocket Auth] REJECTED - verified={verified_user_id}, expected={user_id}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    # ============================================================
    # 2. 建立连接
    # ============================================================
    await manager.connect(user_id, websocket)

    try:
        # ============================================================
        # 3. 发送初始状态
        # ============================================================
        status_mgr = get_status_manager(user_id)
        initial_status = status_mgr.read_status()

        await websocket.send_json({
            "type": "status_update",
            "timestamp": datetime.now().isoformat(),
            "data": initial_status
        })

        # ============================================================
        # 4. 轮询状态变化并推送
        # ============================================================
        # 🔴 修复：忽略 last_updated 字段进行比较，避免时间戳干扰
        def status_hash(status_data: dict) -> str:
            """生成状态哈希（忽略时间戳字段）"""
            copy = {k: v for k, v in status_data.items() if k != "last_updated"}
            return json.dumps(copy, sort_keys=True)

        last_status_hash = status_hash(initial_status)

        while True:
            # 🔴 修复：缩短轮询间隔至 0.3 秒，提高实时性
            await asyncio.sleep(0.3)

            # 读取最新状态
            current_status = status_mgr.read_status()
            current_hash = status_hash(current_status)

            # 如果状态有变化，推送更新
            if current_hash != last_status_hash:
                print(f"[WebSocket] Status changed for user {user_id}, pushing update...")
                await websocket.send_json({
                    "type": "status_update",
                    "timestamp": datetime.now().isoformat(),
                    "data": current_status
                })
                last_status_hash = current_hash

                # ============================================================
                # 5. 特殊事件通知
                # ============================================================

                # 人工复核通知
                if current_status.get("status") == "manual_review":
                    await websocket.send_json({
                        "type": "manual_review_required",
                        "timestamp": datetime.now().isoformat(),
                        "data": current_status.get("manual_review_data", {})
                    })

                # 任务完成通知
                elif current_status.get("status") == "completed":
                    await websocket.send_json({
                        "type": "task_completed",
                        "timestamp": datetime.now().isoformat(),
                        "data": {
                            "message": current_status.get("message", ""),
                            "stats": current_status.get("stats", {})
                        }
                    })

                # 错误通知
                elif current_status.get("status") == "error":
                    await websocket.send_json({
                        "type": "error",
                        "timestamp": datetime.now().isoformat(),
                        "data": {
                            "message": current_status.get("message", "Unknown error")
                        }
                    })

            # ============================================================
            # 6. 接收客户端消息（可选）
            # ============================================================
            try:
                # 非阻塞接收（超时 0.1 秒）
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=0.1
                )

                # 处理客户端发送的消息
                if message.get("type") == "ping":
                    # 心跳响应
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })

                elif message.get("type") == "manual_decision":
                    # 人工决策（也可以通过 REST API 提交）
                    decision = message.get("decision")
                    if decision:
                        status_mgr.set_manual_decision(decision)
                        await websocket.send_json({
                            "type": "decision_received",
                            "timestamp": datetime.now().isoformat(),
                            "data": {"decision": decision}
                        })

            except asyncio.TimeoutError:
                # 没有收到消息，继续循环
                pass

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        print(f"[WebSocket] User {user_id} disconnected normally")

    except Exception as e:
        manager.disconnect(user_id)
        print(f"[WebSocket] User {user_id} disconnected with error: {e}")


@router.get("/ws/health")
async def websocket_health():
    """
    WebSocket 健康检查

    返回当前活跃连接数
    """
    return {
        "status": "healthy",
        "active_connections": len(manager.active_connections),
        "connected_users": list(manager.active_connections.keys())
    }
