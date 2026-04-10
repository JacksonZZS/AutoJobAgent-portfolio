"""
状态管理器 - 实时进度同步（支持多用户数据隔离）
用于在后台脚本和 Web Dashboard 之间同步任务进度
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


DEFAULT_STATS = {
    "total_seen": 0,
    "total_processed": 0,
    "filtered_history": 0,
    "filtered_title": 0,
    "filtered_company": 0,
    "rejected_low_score": 0,
    "failed_scoring": 0,
    "manual_review": 0,
    "success": 0,
    "skipped": 0,
    "failed": 0,
}


class TaskStatus(Enum):
    """任务状态枚举"""
    IDLE = "idle"                      # 空闲
    INITIALIZING = "initializing"      # 初始化中
    SCRAPING = "scraping"              # 抓取职位列表
    ANALYZING = "analyzing"            # AI 分析匹配度
    GENERATING = "generating"          # 生成定制简历
    MANUAL_REVIEW = "manual_review"    # 🔴 人工复核中(60-74分)
    APPLYING = "applying"              # 浏览器自动投递
    WAITING_USER = "waiting_user"      # 等待用户操作
    COMPLETED = "completed"            # 全部完成
    ERROR = "error"                    # 错误
    STOPPED = "stopped"                # 已停止


# 🔴 新增:阶段进度权重配置
STAGE_PROGRESS_WEIGHTS = {
    TaskStatus.SCRAPING: (0.0, 0.3),    # 抓取阶段占 30%
    TaskStatus.ANALYZING: (0.3, 0.5),   # 分析阶段占 20%
    TaskStatus.APPLYING: (0.5, 1.0),    # 投递阶段占 50%
}


class StatusManager:
    """
    状态管理器 - 支持多用户数据隔离

    通过 JSON 文件实现后台脚本与 Web Dashboard 的实时状态同步
    每个用户拥有独立的状态文件：
    - data/status/status_{user_id}.json
    """

    def __init__(self, user_id: Optional[str] = None, status_file: Optional[str] = None):
        """
        初始化状态管理器

        Args:
            user_id: 用户 ID，用于多用户数据隔离（推荐使用）
            status_file: 状态文件路径（向后兼容，不推荐）

        优先级：
        1. 如果提供 user_id，使用 data/status/status_{user_id}.json
        2. 如果提供 status_file，使用指定路径
        3. 否则使用默认路径 data/app_status.json（向后兼容）
        """
        self.base_dir = Path(__file__).parent.parent
        self.user_id = user_id

        # 🔴 多用户隔离：根据 user_id 动态生成文件路径
        if user_id:
            self.status_file = self.base_dir / "data" / "status" / f"status_{user_id}.json"
            logger.info(f"StatusManager initialized for user: {user_id}")
        elif status_file:
            self.status_file = self.base_dir / status_file
            logger.warning("StatusManager using custom path (not recommended for multi-user)")
        else:
            # 向后兼容：默认路径
            self.status_file = self.base_dir / "data/app_status.json"
            logger.warning("StatusManager using default path (not suitable for multi-user)")

        # 确保目录存在
        self.status_file.parent.mkdir(parents=True, exist_ok=True)

        # 初始化状态文件
        if not self.status_file.exists():
            self._write_status({
                "status": TaskStatus.IDLE.value,
                "step": "",
                "message": "系统就绪",
                "progress": 0,
                "current_job": None,
                "stats": DEFAULT_STATS.copy(),
                "last_updated": datetime.now().isoformat()
            })

        logger.debug(f"Status file: {self.status_file}")

    def _write_status(self, data: Dict[str, Any]) -> None:
        """
        写入状态到文件

        Args:
            data: 状态数据字典
        """
        try:
            # 添加时间戳
            data["last_updated"] = datetime.now().isoformat()

            # 写入文件（原子操作）
            temp_file = self.status_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # 原子替换
            temp_file.replace(self.status_file)

            logger.debug(f"Status updated: {data['status']} - {data['message']}")

        except Exception as e:
            logger.error(f"Failed to write status: {e}")

    def read_status(self) -> Dict[str, Any]:
        """
        读取当前状态

        Returns:
            状态数据字典
        """
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {
                    "status": TaskStatus.IDLE.value,
                    "step": "",
                    "message": "系统就绪",
                    "progress": 0,
                    "current_job": None,
                    "stats": DEFAULT_STATS.copy(),
                    "last_updated": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Failed to read status: {e}")
            return {}

    def update(
        self,
        status: TaskStatus,
        message: str,
        progress: int = None,  # 改为 None，表示保留当前进度
        step: str = "",
        current_job: Optional[Dict[str, str]] = None
    ) -> None:
        """
        更新任务状态

        Args:
            status: 任务状态
            message: 状态消息
            progress: 进度百分比 (0-100)，None 表示保留当前进度
            step: 当前步骤描述
            current_job: 当前处理的职位信息 {"title": "...", "company": "..."}
        """
        # 读取当前状态以保留统计数据和 manual_review_data
        current_data = self.read_status()

        # 🔴 修复：如果没有传入 progress，保留当前进度，避免归零
        if progress is None:
            progress = current_data.get("progress", 0)

        # 更新状态
        data = {
            "status": status.value if isinstance(status, TaskStatus) else status,
            "step": step,
            "message": message,
            "progress": max(0, min(100, progress)),  # 限制在 0-100
            "current_job": current_job,
            "stats": {**DEFAULT_STATS, **current_data.get("stats", {})}
        }

        # 🔴 修复：保留 manual_review_data（避免被覆盖导致前端下载按钮消失）
        if "manual_review_data" in current_data:
            data["manual_review_data"] = current_data["manual_review_data"]
        if "manual_review_queue" in current_data:
            data["manual_review_queue"] = current_data["manual_review_queue"]

        self._write_status(data)

    def update_stats(
        self,
        total_seen: Optional[int] = None,
        total_processed: Optional[int] = None,
        filtered_history: Optional[int] = None,
        filtered_title: Optional[int] = None,
        filtered_company: Optional[int] = None,
        rejected_low_score: Optional[int] = None,
        failed_scoring: Optional[int] = None,
        manual_review: Optional[int] = None,
        success: Optional[int] = None,
        skipped: Optional[int] = None,
        failed: Optional[int] = None
    ) -> None:
        """
        更新统计数据

        Args:
            total_seen: 扫描到的职位数
            total_processed: 总处理数
            filtered_history: 因历史记录跳过
            filtered_title: 因标题过滤跳过
            filtered_company: 因公司黑名单跳过
            rejected_low_score: 低分拒绝数
            failed_scoring: 评分失败数
            manual_review: 进入人工复核数
            success: 成功数
            skipped: 跳过数
            failed: 失败数
        """
        current_data = self.read_status()
        stats = {**DEFAULT_STATS, **current_data.get("stats", {})}

        if total_seen is not None:
            stats["total_seen"] = total_seen
        if total_processed is not None:
            stats["total_processed"] = total_processed
        if filtered_history is not None:
            stats["filtered_history"] = filtered_history
        if filtered_title is not None:
            stats["filtered_title"] = filtered_title
        if filtered_company is not None:
            stats["filtered_company"] = filtered_company
        if rejected_low_score is not None:
            stats["rejected_low_score"] = rejected_low_score
        if failed_scoring is not None:
            stats["failed_scoring"] = failed_scoring
        if manual_review is not None:
            stats["manual_review"] = manual_review
        if success is not None:
            stats["success"] = success
        if skipped is not None:
            stats["skipped"] = skipped
        if failed is not None:
            stats["failed"] = failed

        current_data["stats"] = stats
        self._write_status(current_data)

    def increment_stat(self, stat_name: str) -> None:
        """
        增加统计计数

        Args:
            stat_name: 统计项名称
        """
        current_data = self.read_status()
        stats = {**DEFAULT_STATS, **current_data.get("stats", {})}

        if stat_name in stats:
            stats[stat_name] += 1
            current_data["stats"] = stats
            self._write_status(current_data)

    def reset(self) -> None:
        """重置状态为初始状态（包括清理 manual_review_data）"""
        # 🔴 修复：直接写入完整的初始状态，避免 update() 保留旧数据
        self._write_status({
            "status": TaskStatus.IDLE.value,
            "step": "",
            "message": "系统就绪",
            "progress": 0,
            "current_job": None,
            "stats": DEFAULT_STATS.copy()
            # 🔴 注意：不包含 manual_review_data，会被自动清除
        })

    def check_and_clean_stale_status(self, max_age_minutes: int = 10) -> bool:
        """
        检查并清理过期的状态（方案1：程序启动时自动重置）

        如果状态文件存在且满足以下条件，则重置为 IDLE：
        1. 状态不是 COMPLETED 或 IDLE
        2. 最后更新时间超过 max_age_minutes 分钟

        Args:
            max_age_minutes: 状态过期时间（分钟），默认 10 分钟

        Returns:
            True 表示清理了过期状态，False 表示状态正常
        """
        try:
            current_status = self.read_status()

            # 如果状态是 COMPLETED 或 IDLE，不需要清理
            status_value = current_status.get("status", "")
            if status_value in [TaskStatus.COMPLETED.value, TaskStatus.IDLE.value]:
                return False

            # 检查最后更新时间
            last_updated_str = current_status.get("last_updated", "")
            if not last_updated_str:
                # 如果没有时间戳，认为是过期状态
                logger.warning("⚠️ 检测到无时间戳的旧状态，正在清理...")
                self.reset()
                return True

            # 解析时间戳
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                time_diff = datetime.now() - last_updated
                age_minutes = time_diff.total_seconds() / 60

                if age_minutes > max_age_minutes:
                    logger.warning(f"⚠️ 检测到过期状态（{age_minutes:.1f} 分钟前），正在清理...")
                    logger.info(f"   原状态: {status_value} - {current_status.get('message', '')}")
                    self.reset()
                    logger.info("   ✅ 状态已重置为 IDLE")
                    return True
                else:
                    logger.debug(f"状态正常（{age_minutes:.1f} 分钟前更新）")
                    return False

            except ValueError as e:
                logger.warning(f"⚠️ 无法解析时间戳: {e}，正在清理状态...")
                self.reset()
                return True

        except Exception as e:
            logger.error(f"检查过期状态时出错: {e}")
            return False

    def set_error(self, error_message: str) -> None:
        """
        设置错误状态

        Args:
            error_message: 错误消息
        """
        self.update(
            status=TaskStatus.ERROR,
            message=f"❌ 错误: {error_message}",
            progress=0,
            step="error"
        )

    def set_completed(self, summary_message: str) -> None:
        """
        设置完成状态

        Args:
            summary_message: 完成摘要消息
        """
        self.update(
            status=TaskStatus.COMPLETED,
            message=summary_message,
            progress=100,
            step="completed"
        )

    # 🔴 新增:阶段化进度管理方法

    def update_stage_progress(
        self,
        stage: TaskStatus,
        stage_progress: float,
        message: str = "",
        current_job: Optional[Dict[str, str]] = None
    ) -> None:
        """
        更新阶段内的进度

        Args:
            stage: 当前阶段
            stage_progress: 阶段内进度 (0.0-1.0)
            message: 状态消息
            current_job: 当前处理的职位信息
        """
        if stage not in STAGE_PROGRESS_WEIGHTS:
            logger.warning(f"Unknown stage: {stage}, using default progress")
            overall_progress = int(stage_progress * 100)
        else:
            # 计算整体进度
            start_weight, end_weight = STAGE_PROGRESS_WEIGHTS[stage]
            overall_progress = int((start_weight + (end_weight - start_weight) * stage_progress) * 100)

        self.update(
            status=stage,
            message=message,
            progress=overall_progress,
            step=stage.value,
            current_job=current_job
        )

    def on_scraping_progress(
        self,
        scraped_count: int,
        total_count: int,
        current_company: str = ""
    ) -> None:
        """
        更新抓取进度

        Args:
            scraped_count: 已抓取数量
            total_count: 总数量
            current_company: 当前公司名称
        """
        if total_count > 0:
            stage_progress = scraped_count / total_count
        else:
            stage_progress = 0.0

        message = f"正在抓取职位列表 ({scraped_count}/{total_count})"
        if current_company:
            message += f" - {current_company}"

        self.update_stage_progress(
            stage=TaskStatus.SCRAPING,
            stage_progress=stage_progress,
            message=message
        )

    def on_analyzing_progress(
        self,
        analyzed_count: int,
        total_count: int,
        current_job: Optional[Dict[str, str]] = None
    ) -> None:
        """
        更新分析进度

        Args:
            analyzed_count: 已分析数量
            total_count: 总数量
            current_job: 当前职位信息
        """
        if total_count > 0:
            stage_progress = analyzed_count / total_count
        else:
            stage_progress = 0.0

        message = f"AI 正在分析职位匹配度 ({analyzed_count}/{total_count})"

        self.update_stage_progress(
            stage=TaskStatus.ANALYZING,
            stage_progress=stage_progress,
            message=message,
            current_job=current_job
        )

    def on_applying_progress(
        self,
        applied_count: int,
        total_count: int,
        current_job: Optional[Dict[str, str]] = None
    ) -> None:
        """
        更新投递进度

        Args:
            applied_count: 已投递数量
            total_count: 总数量
            current_job: 当前职位信息
        """
        if total_count > 0:
            stage_progress = applied_count / total_count
        else:
            stage_progress = 0.0

        message = f"正在自动投递 ({applied_count}/{total_count})"

        self.update_stage_progress(
            stage=TaskStatus.APPLYING,
            stage_progress=stage_progress,
            message=message,
            current_job=current_job
        )

    def mark_completed_if_ready(
        self,
        applied_count: int,
        target_count: int,
        success_count: int
    ) -> bool:
        """
        检查是否应该标记为完成

        只有当真正完成所有投递操作时才标记为 COMPLETED

        Args:
            applied_count: 已投递数量(成功+失败)
            target_count: 目标投递数量
            success_count: 成功投递数量

        Returns:
            True 表示已标记为完成,False 表示未完成
        """
        # 🔴 关键修复:只有真正完成所有投递才标记为 COMPLETED
        if applied_count >= target_count and target_count > 0:
            summary = f"✅ 任务完成!成功投递 {success_count}/{target_count} 个职位"
            self.set_completed(summary)
            logger.info(f"Task marked as COMPLETED: {summary}")
            return True

        return False

    # 🔴 新增:人工复核相关方法

    def set_manual_review(
        self,
        score: int,
        dimensions: list = None,
        job_url: str = "",
        job_title: str = "",
        company_name: str = "",
        resume_path: str = "",      # 🔴 新增:简历路径
        cl_path: str = "",          # 🔴 新增:求职信PDF路径
        cl_text: str = ""           # 🔴 新增:求职信文本
    ) -> None:
        """
        设置为人工复核状态(包含预生成的文档)

        Args:
            score: 匹配分数
            dimensions: 评分维度详情
            job_url: 职位链接
            job_title: 职位标题
            company_name: 公司名称
            resume_path: 生成的简历PDF路径
            cl_path: 生成的求职信PDF路径
            cl_text: 求职信文本内容
        """
        current_data = self.read_status()

        message = f"⚠️ 匹配度 {score}% - 建议人工复核"
        if company_name and job_title:
            message += f": {company_name} - {job_title}"

        # 🔴 [DEBUG] 记录设置的数据
        logger.info("=" * 60)
        logger.info("📋 [STATUS] 设置 MANUAL_REVIEW 状态:")
        logger.info(f"   职位: {job_title}")
        logger.info(f"   公司: {company_name}")
        logger.info(f"   评分: {score}")
        logger.info(f"   简历路径: {resume_path}")
        logger.info(f"   求职信路径: {cl_path}")
        logger.info(f"   求职信文本长度: {len(cl_text)} 字符")
        logger.info("=" * 60)

        current_data.update({
            "status": TaskStatus.MANUAL_REVIEW.value,
            "message": message,
            "step": "manual_review",
            "manual_review_data": {
                "score": score,
                "dimensions": dimensions or [],
                "job_url": job_url,
                "job_title": job_title,
                "company_name": company_name,
                "resume_path": resume_path,      # 🔴 新增
                "cl_path": cl_path,              # 🔴 新增
                "cl_text": cl_text,              # 🔴 新增
                "decision": None  # 等待用户决策
            }
        })

        queue = current_data.get("manual_review_queue", [])
        queue.append(current_data["manual_review_data"])
        current_data["manual_review_queue"] = queue

        self._write_status(current_data)

        # 🔴 [DEBUG] 验证写入结果
        verify_data = self.read_status()
        if "manual_review_data" in verify_data:
            logger.info("✅ [STATUS] manual_review_data 写入成功")
            logger.info(f"   验证 - 简历路径: {verify_data['manual_review_data'].get('resume_path', 'MISSING')}")
            logger.info(f"   验证 - 求职信路径: {verify_data['manual_review_data'].get('cl_path', 'MISSING')}")
        else:
            logger.error("❌ [STATUS] manual_review_data 写入失败！")

        logger.info(f"Set MANUAL_REVIEW: {job_title} @ {company_name} (score: {score})")
        if resume_path:
            logger.info(f"  Resume: {resume_path}")
        if cl_path:
            logger.info(f"  Cover Letter: {cl_path}")

    def set_manual_decision(self, decision: str) -> None:
        """
        设置人工复核决策

        Args:
            decision: "APPLY" | "SKIP"
        """
        current_data = self.read_status()

        if "manual_review_data" in current_data:
            current_data["manual_review_data"]["decision"] = decision
            queue = current_data.get("manual_review_queue", [])
            if queue:
                queue[0]["decision"] = decision
            self._write_status(current_data)
            logger.info(f"Manual decision set: {decision}")

    def get_manual_decision(self) -> Optional[str]:
        """
        获取人工复核决策

        Returns:
            "APPLY" | "SKIP" | None
        """
        current_data = self.read_status()
        manual_data = current_data.get("manual_review_data", {})
        return manual_data.get("decision")

    def clear_manual_review(self) -> None:
        """清除人工复核数据"""
        current_data = self.read_status()
        queue = current_data.get("manual_review_queue", [])
        if queue:
            queue.pop(0)
            current_data["manual_review_queue"] = queue

            if queue:
                current_data["manual_review_data"] = queue[0]
                current_data["status"] = TaskStatus.MANUAL_REVIEW.value
                current_data["step"] = "manual_review"
                current_data["message"] = f"⚠️ 还有 {len(queue)} 个职位待人工复核"
            elif "manual_review_data" in current_data:
                del current_data["manual_review_data"]
        elif "manual_review_data" in current_data:
            del current_data["manual_review_data"]
        self._write_status(current_data)


# 全局单例实例字典（支持多用户）
_status_manager_instances: Dict[str, StatusManager] = {}


def get_status_manager(user_id: Optional[str] = None) -> StatusManager:
    """
    获取状态管理器实例（支持多用户单例模式）

    Args:
        user_id: 用户 ID，用于多用户数据隔离

    Returns:
        StatusManager 实例

    说明：
    - 如果提供 user_id，返回该用户的专属实例
    - 如果不提供 user_id，返回默认实例（向后兼容）
    - 每个 user_id 对应一个独立的单例实例
    """
    global _status_manager_instances

    # 使用 user_id 作为 key，如果没有则使用 "default"
    key = user_id if user_id else "default"

    if key not in _status_manager_instances:
        _status_manager_instances[key] = StatusManager(user_id=user_id)
        logger.debug(f"Created new StatusManager instance for: {key}")

    return _status_manager_instances[key]
