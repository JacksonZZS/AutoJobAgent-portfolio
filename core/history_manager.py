import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Optional
from core.url_cleaner import clean_job_url

logger = logging.getLogger(__name__)


class HistoryManager:
    """
    历史记录管理器 - 支持多用户数据隔离

    每个用户拥有独立的历史记录文件：
    - data/histories/history_{user_id}.json
    """

    def __init__(self, user_id: Optional[str] = None, history_file: Optional[str] = None):
        """
        初始化历史记录管理器

        Args:
            user_id: 用户 ID，用于多用户数据隔离（推荐使用）
            history_file: 历史记录文件路径（向后兼容，不推荐）

        优先级：
        1. 如果提供 user_id，使用 data/histories/history_{user_id}.json
        2. 如果提供 history_file，使用指定路径
        3. 否则使用默认路径 data/history/processed_jobs.json（向后兼容）
        """
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.user_id = user_id

        # 🔴 多用户隔离：根据 user_id 动态生成文件路径
        if user_id:
            self.filepath = os.path.join(
                self.base_dir,
                "data",
                "histories",
                f"history_{user_id}.json"
            )
            logger.info(f"HistoryManager initialized for user: {user_id}")
        elif history_file:
            self.filepath = os.path.join(self.base_dir, history_file)
            logger.warning("HistoryManager using custom path (not recommended for multi-user)")
        else:
            # 向后兼容：默认路径
            self.filepath = os.path.join(self.base_dir, "data/history/processed_jobs.json")
            logger.warning("HistoryManager using default path (not suitable for multi-user)")

        # 确保目录存在
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

        # 加载历史记录
        self.history = self._load_history()

        logger.debug(f"History file: {self.filepath}")

    def _load_history(self):
        """读取 JSON 文件"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_history(self):
        """保存回 JSON 文件"""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)

    def get_job_id(self, link):
        """
        从链接中提取唯一 ID。

        关键改进：
        1. 先使用 clean_job_url() 移除查询参数，确保 URL 唯一性
        2. 使用正则表达式强制提取 8-10 位纯数字（与 ApplyBot._extract_job_id 保持一致）
        3. 如果提取失败，对清理后的 URL 做 Hash

        Args:
            link: 职位链接

        Returns:
            唯一的职位 ID
        """
        try:
            # 🔴 关键修改：先清理 URL，移除查询参数
            cleaned_link = clean_job_url(link)
            logger.debug(f"Cleaned URL: {link} -> {cleaned_link}")

            # 🔴 [修复] 使用正则表达式提取 /job/ 后面的 8-10 位纯数字（与 ApplyBot 保持一致）
            import re
            match = re.search(r'/job/(\d{8,10})', cleaned_link)
            if match:
                job_id = match.group(1)
                logger.debug(f"Extracted job ID: {job_id}")
                return job_id

            # 如果没有 /job/ 前缀，尝试提取任意位置的 8-10 位数字
            match = re.search(r'(\d{8,10})', cleaned_link)
            if match:
                job_id = match.group(1)
                logger.debug(f"Extracted job ID (fallback): {job_id}")
                return job_id

        except Exception as e:
            logger.warning(f"Failed to extract job ID from '{link}': {e}")

        # 兜底方案：对清理后的 URL 生成哈希值
        cleaned_link = clean_job_url(link)
        return hashlib.md5(cleaned_link.encode()).hexdigest()

    def is_processed(self, link):
        """
        检查这个链接是否处理过

        Args:
            link: 职位链接

        Returns:
            True 如果已处理，False 如果未处理
        """
        job_id = self.get_job_id(link)
        is_processed = job_id in self.history

        if is_processed:
            logger.debug(f"Job already processed: {link} (ID: {job_id})")

        return is_processed

    def is_duplicate(self, job_id_or_link):
        """
        检查职位是否重复（is_processed 的别名）
        兼容旧代码调用
        """
        return self.is_processed(job_id_or_link)

    def add_job(self, link, title, company, status="processed", score=None, reason=None, resume_path=None, cl_path=None):
        """
        标记这个职位为已处理

        关键改进：
        1. 使用清理后的 URL 作为唯一标识
        2. 同时保存原始 URL 和清理后的 URL
        3. 立即保存到文件，防止程序崩溃导致数据丢失
        4. 🔴 新增：保存简历和求职信路径，方便面试时查看

        Args:
            link: 职位链接
            title: 职位标题
            company: 公司名称
            status: 处理状态 (success, skipped_low_score, skipped_blocked, failed, pending, etc.)
            score: AI 评分（可选）
            reason: 跳过或失败的原因（可选）
            resume_path: 定制化简历 PDF 路径（可选）
            cl_path: 求职信 PDF 路径（可选）
        """
        job_id = self.get_job_id(link)
        cleaned_link = clean_job_url(link)

        record = {
            "title": title,
            "company": company,
            "link": link,  # 保存原始链接
            "cleaned_link": cleaned_link,  # 保存清理后的链接
            "status": status,
            "processed_at": datetime.now().isoformat()
        }

        # 添加可选字段
        if score is not None:
            record["score"] = score
        if reason:
            record["reason"] = reason

        # 🔴 新增：保存简历和求职信路径
        if resume_path:
            record["resume_path"] = resume_path
        if cl_path:
            record["cl_path"] = cl_path

        self.history[job_id] = record

        # 🔴 关键修改：立即保存到文件
        self._save_history()

        logger.info(f"Job added to history: {title} @ {company} (ID: {job_id}, Status: {status})")
        if resume_path:
            logger.debug(f"  Resume: {resume_path}")
        if cl_path:
            logger.debug(f"  Cover Letter: {cl_path}")

    def is_duplicate_cross_platform(self, title: str, company: str) -> dict:
        """
        跨平台去重检测：检查是否已经投递过相同公司的相同职位

        Args:
            title: 职位标题
            company: 公司名称

        Returns:
            dict: {"is_duplicate": bool, "existing_job": dict or None, "platform": str or None}
        """
        if not title or not company:
            return {"is_duplicate": False, "existing_job": None, "platform": None}

        # 标准化：去除空格、转小写
        def normalize(s):
            return s.lower().strip().replace(" ", "").replace("-", "").replace("_", "")

        norm_title = normalize(title)
        norm_company = normalize(company)

        for job_id, record in self.history.items():
            existing_title = normalize(record.get("title", ""))
            existing_company = normalize(record.get("company", ""))

            # 🔴 公司名 + 职位标题都匹配 = 重复
            if norm_company == existing_company and norm_title == existing_title:
                # 检测平台
                link = record.get("link", "")
                if "indeed.com" in link:
                    platform = "Indeed"
                elif "jobsdb.com" in link:
                    platform = "JobsDB"
                elif "linkedin.com" in link:
                    platform = "LinkedIn"
                else:
                    platform = "Unknown"

                print(f"[去重] 跨平台重复检测: {company} - {title} (已在 {platform} 处理过)")
                return {
                    "is_duplicate": True,
                    "existing_job": record,
                    "platform": platform
                }

        return {"is_duplicate": False, "existing_job": None, "platform": None}

    def get_statistics(self):
        """
        获取历史记录统计信息

        Returns:
            dict: 包含各种状态的统计数据
        """
        stats = {
            "total": len(self.history),
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "by_status": {}
        }

        for job_id, record in self.history.items():
            status = record.get("status", "unknown")

            # 统计主要类别
            if status == "success":
                stats["success"] += 1
            elif status.startswith("skipped"):
                stats["skipped"] += 1
            elif status == "failed":
                stats["failed"] += 1

            # 统计详细状态
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

        return stats