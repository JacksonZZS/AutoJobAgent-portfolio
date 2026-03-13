"""
URL 清理工具 - 确保 URL 唯一性
移除查询参数，避免重复抓取
"""

import logging
from urllib.parse import urlparse, urlunparse
from typing import Optional

logger = logging.getLogger(__name__)


def clean_job_url(url: str) -> str:
    """
    清理职位 URL，移除查询参数确保唯一性

    Args:
        url: 原始 URL

    Returns:
        清理后的 URL（移除查询参数）

    Examples:
        >>> clean_job_url("https://hk.jobsdb.com/job/12345678?source=email")
        'https://hk.jobsdb.com/job/12345678'

        >>> clean_job_url("https://hk.jobsdb.com/job/12345678")
        'https://hk.jobsdb.com/job/12345678'
    """
    try:
        # 解析 URL
        parsed = urlparse(url)

        # 重建 URL，移除查询参数（query）和片段（fragment）
        cleaned = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            '',  # params
            '',  # query - 移除查询参数
            ''   # fragment
        ))

        # 移除尾部斜杠（如果有）
        cleaned = cleaned.rstrip('/')

        if cleaned != url:
            logger.debug(f"URL cleaned: {url} -> {cleaned}")

        return cleaned

    except Exception as e:
        logger.warning(f"Failed to clean URL '{url}': {e}, returning original")
        return url


def extract_job_id(url: str) -> Optional[str]:
    """
    从 URL 中提取职位 ID

    Args:
        url: 职位 URL

    Returns:
        职位 ID，如果提取失败返回 None

    Examples:
        >>> extract_job_id("https://hk.jobsdb.com/job/12345678?source=email")
        '12345678'

        >>> extract_job_id("https://hk.jobsdb.com/hk/en/job/python-developer-12345678")
        '12345678'
    """
    try:
        # 先清理 URL
        cleaned_url = clean_job_url(url)

        # 尝试从路径中提取 ID
        parsed = urlparse(cleaned_url)
        path_parts = parsed.path.strip('/').split('/')

        # 查找 'job' 关键字后的部分
        if 'job' in path_parts:
            job_index = path_parts.index('job')
            if job_index + 1 < len(path_parts):
                job_id = path_parts[job_index + 1]
                # 如果包含连字符，取最后一部分（通常是 ID）
                if '-' in job_id:
                    job_id = job_id.split('-')[-1]
                return job_id

        # 如果没有找到，尝试取路径的最后一部分
        if path_parts:
            last_part = path_parts[-1]
            # 如果包含连字符，取最后一部分
            if '-' in last_part:
                return last_part.split('-')[-1]
            return last_part

        return None

    except Exception as e:
        logger.warning(f"Failed to extract job ID from '{url}': {e}")
        return None


def normalize_url(url: str) -> str:
    """
    标准化 URL（清理 + 小写化）

    Args:
        url: 原始 URL

    Returns:
        标准化后的 URL

    Examples:
        >>> normalize_url("HTTPS://HK.JOBSDB.COM/Job/12345678?Source=Email")
        'https://hk.jobsdb.com/job/12345678'
    """
    try:
        # 先清理
        cleaned = clean_job_url(url)

        # 转小写（保持路径大小写敏感性，只转换 scheme 和 netloc）
        parsed = urlparse(cleaned)
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,  # 保持路径原样
            parsed.params,
            parsed.query,
            parsed.fragment
        ))

        return normalized

    except Exception as e:
        logger.warning(f"Failed to normalize URL '{url}': {e}, returning cleaned version")
        return clean_job_url(url)
