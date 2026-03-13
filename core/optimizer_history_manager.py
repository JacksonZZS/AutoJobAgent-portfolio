"""
简历优化历史管理器
用于记录和管理用户的简历优化历史
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class OptimizerHistoryManager:
    """
    简历优化历史管理器

    功能：
    - 记录每次简历优化的详细信息
    - 支持多用户数据隔离
    - 提供历史记录查询和统计
    """

    def __init__(self, user_id: str):
        """
        初始化优化历史管理器

        Args:
            user_id: 用户 ID
        """
        self.user_id = user_id
        self.base_dir = Path(__file__).parent.parent
        self.history_file = self.base_dir / "data" / "optimizer_history" / f"history_{user_id}.json"

        # 确保目录存在
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # 加载历史记录
        self.history = self._load_history()

        logger.debug(f"OptimizerHistoryManager initialized for user {user_id}")

    def _load_history(self) -> List[Dict[str, Any]]:
        """
        从文件加载历史记录

        Returns:
            历史记录列表
        """
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return []
        except Exception as e:
            logger.error(f"Failed to load optimizer history for user {self.user_id}: {e}")
            return []

    def _save_history(self) -> None:
        """保存历史记录到文件"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save optimizer history for user {self.user_id}: {e}")

    def add_record(
        self,
        original_filename: str,
        optimized_pdf_path: str,
        permanent_resident: bool = False,
        available_immediately: bool = False,
        linkedin_url: str = "",
        github_url: str = "",
        portfolio_url: str = "",
        additional_notes: str = ""
    ) -> None:
        """
        添加优化记录

        Args:
            original_filename: 原始简历文件名
            optimized_pdf_path: 优化后的PDF路径
            permanent_resident: 是否为香港永久居民
            available_immediately: 是否可以立即上班
            linkedin_url: LinkedIn地址
            github_url: GitHub地址
            portfolio_url: 个人网站/作品集地址
            additional_notes: 其他补充信息
        """
        record = {
            "id": len(self.history) + 1,
            "original_filename": original_filename,
            "optimized_pdf_path": optimized_pdf_path,
            "optimized_pdf_filename": Path(optimized_pdf_path).name,
            "permanent_resident": permanent_resident,
            "available_immediately": available_immediately,
            "linkedin_url": linkedin_url,
            "github_url": github_url,
            "portfolio_url": portfolio_url,
            "additional_notes": additional_notes,
            "created_at": datetime.now().isoformat()
        }

        self.history.append(record)
        self._save_history()

        logger.info(f"Added optimizer history record for user {self.user_id}: {original_filename}")

    def get_all_records(self) -> List[Dict[str, Any]]:
        """
        获取所有优化记录（按时间倒序）

        Returns:
            优化记录列表
        """
        return sorted(self.history, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_record_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取优化记录

        Args:
            record_id: 记录ID

        Returns:
            优化记录字典，不存在返回 None
        """
        for record in self.history:
            if record.get("id") == record_id:
                return record
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取优化统计信息

        Returns:
            统计信息字典
        """
        return {
            "total_optimizations": len(self.history),
            "permanent_resident_count": sum(1 for r in self.history if r.get("permanent_resident", False)),
            "available_immediately_count": sum(1 for r in self.history if r.get("available_immediately", False)),
            "with_linkedin_count": sum(1 for r in self.history if r.get("linkedin_url", "")),
            "with_github_count": sum(1 for r in self.history if r.get("github_url", "")),
        }

    def delete_record(self, record_id: int) -> bool:
        """
        删除优化记录

        Args:
            record_id: 记录ID

        Returns:
            删除成功返回 True，失败返回 False
        """
        initial_length = len(self.history)
        self.history = [r for r in self.history if r.get("id") != record_id]

        if len(self.history) < initial_length:
            self._save_history()
            logger.info(f"Deleted optimizer history record {record_id} for user {self.user_id}")
            return True

        return False
