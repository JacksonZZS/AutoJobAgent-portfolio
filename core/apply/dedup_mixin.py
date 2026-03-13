# core/apply/dedup_mixin.py
"""Job deduplication mixin for JobsDBApplyBot."""

import json
import re
import hashlib
import logging
from pathlib import Path
from typing import Set

from core.status_manager import get_status_manager

logger = logging.getLogger(__name__)


class DedupMixin:
    """Handles job deduplication: history loading, checking, marking."""

    def _extract_job_id(self, job_url: str) -> str:
        """
        从职位 URL 中提取 Job ID（强制提取 8-10 位纯数字）
        """
        if not job_url:
            return ""

        match = re.search(r'/job/(\d{8,10})', str(job_url))
        if match:
            return match.group(1)

        match = re.search(r'(\d{8,10})', str(job_url))
        if match:
            return match.group(1)

        url_hash = hashlib.md5(str(job_url).encode('utf-8')).hexdigest()[:16]
        logger.debug(f"Could not extract job ID from URL, using hash: {url_hash}")
        return url_hash

    def _generate_job_key(self, title: str, company: str) -> str:
        """
        生成职位唯一标识（基于标题+公司名）
        """
        normalized = f"{title.strip().lower()}|{company.strip().lower()}"
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()[:16]

    def _load_job_history(self):
        """加载已处理的职位历史记录（同时支持 job_id 和 job_key）"""
        if self.job_history_path.exists():
            try:
                with open(self.job_history_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._processed_job_ids = set(data.get("processed_ids", []))
                    self._processed_job_keys = set(data.get("processed_keys", []))
                logger.info(f"Loaded {len(self._processed_job_ids)} job IDs and {len(self._processed_job_keys)} job keys from {self.job_history_path}")
            except Exception as e:
                logger.warning(f"Failed to load job history: {e}, starting with empty history")
                self._processed_job_ids = set()
                self._processed_job_keys = set()
        else:
            self._processed_job_ids = set()
            self._processed_job_keys = set()
            self._save_job_history()
            logger.info(f"Created new job history file: {self.job_history_path}")

    def _save_job_history(self):
        """保存已处理的职位历史到文件（包括 job_id 和 job_key）"""
        try:
            data = {
                "processed_ids": sorted(list(self._processed_job_ids)),
                "processed_keys": sorted(list(self._processed_job_keys))
            }
            with open(self.job_history_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(self._processed_job_ids)} job IDs and {len(self._processed_job_keys)} job keys to {self.job_history_path}")
        except Exception as e:
            logger.error(f"Failed to save job history: {e}")

    def _is_job_processed(self, job_id: str, title: str = None, company: str = None) -> bool:
        """
        检查职位是否已经处理过（同时检查 job_id 和 标题+公司名）
        """
        if job_id in self._processed_job_ids:
            return True

        if job_id in self.history_manager.history:
            return True

        if title and company:
            job_key = self._generate_job_key(title, company)
            if job_key in self._processed_job_keys:
                logger.info(f"🚫 检测到重复职位（标题+公司匹配）: {title} @ {company}")
                return True

        return False

    def _mark_job_processed(
        self,
        job_id: str,
        job_url: str = None,
        title: str = "Unknown",
        company: str = "Unknown",
        status: str = "processed",
        score: float = None,
        reason: str = None
    ):
        """
        标记职位为已处理，并持久化到文件
        """
        job_key = self._generate_job_key(title, company)

        needs_save = False

        if job_id not in self._processed_job_ids:
            self._processed_job_ids.add(job_id)
            needs_save = True

        if job_key not in self._processed_job_keys:
            self._processed_job_keys.add(job_key)
            needs_save = True

        if needs_save:
            self._save_job_history()

            if job_url:
                self.history_manager.add_job(
                    link=job_url,
                    title=title,
                    company=company,
                    status=status,
                    score=score,
                    reason=reason
                )

            status_mgr = get_status_manager(user_id=self.user_id)
            status_mgr.increment_stat("total_processed")

            if status == "success":
                status_mgr.increment_stat("success")
            elif status in ["skip_permanent", "low_score", "skipped_low_score", "rejected", "blacklisted", "skipped_blocked"]:
                status_mgr.increment_stat("failed")
            elif status in ["skipped", "skip", "skip_temporary"]:
                status_mgr.increment_stat("skipped")
            elif status in ["failed", "fail", "error", "failed_exception"]:
                status_mgr.increment_stat("failed")

            logger.debug(f"Marked job as processed: {job_id} (status: {status})")
            logger.debug(f"Updated StatusManager stats for user {self.user_id}")
