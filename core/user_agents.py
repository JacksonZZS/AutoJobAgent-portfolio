"""
User-Agent 随机池
参考 web-scraping skill 最佳实践
"""

import random
from typing import Tuple

# 真实浏览器 User-Agent 池
USER_AGENTS = [
    # Chrome - Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',

    # Chrome - Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',

    # Chrome - Linux
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',

    # Safari - Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',

    # Edge - Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0',
]

# 常见视口尺寸
VIEWPORTS = [
    {'width': 1920, 'height': 1080},
    {'width': 1440, 'height': 900},
    {'width': 1536, 'height': 864},
    {'width': 1280, 'height': 800},
    {'width': 1366, 'height': 768},
]


def get_random_user_agent() -> str:
    """获取随机 User-Agent"""
    return random.choice(USER_AGENTS)


def get_random_viewport() -> dict:
    """获取随机视口尺寸"""
    return random.choice(VIEWPORTS).copy()


def get_random_browser_config() -> Tuple[str, dict]:
    """获取随机浏览器配置（UA + 视口）"""
    return get_random_user_agent(), get_random_viewport()


def get_human_delay(min_sec: float = 0.5, max_sec: float = 2.0) -> float:
    """获取模拟人类操作的随机延迟"""
    return random.uniform(min_sec, max_sec)
