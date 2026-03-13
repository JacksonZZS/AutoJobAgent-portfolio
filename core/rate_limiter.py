# core/rate_limiter.py
"""
速率限制器 - 防止 LinkedIn/Indeed 封号
支持请求频率控制、重试机制、熔断器
"""

import time
import asyncio
import logging
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from functools import wraps
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常工作
    OPEN = "open"          # 熔断，拒绝请求
    HALF_OPEN = "half_open"  # 半开，尝试恢复


@dataclass
class RateLimiter:
    """
    速率限制器

    使用滑动窗口算法限制请求频率
    """
    requests_per_minute: int = 5
    requests_per_hour: int = 100

    _minute_timestamps: list = field(default_factory=list)
    _hour_timestamps: list = field(default_factory=list)

    async def acquire(self) -> bool:
        """
        获取请求许可

        Returns:
            是否允许请求
        """
        now = time.time()

        # 清理过期的时间戳
        self._minute_timestamps = [t for t in self._minute_timestamps if now - t < 60]
        self._hour_timestamps = [t for t in self._hour_timestamps if now - t < 3600]

        # 检查分钟限制
        if len(self._minute_timestamps) >= self.requests_per_minute:
            wait_time = 60 - (now - self._minute_timestamps[0])
            logger.warning(f"Rate limit reached (per minute), waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            return await self.acquire()

        # 检查小时限制
        if len(self._hour_timestamps) >= self.requests_per_hour:
            wait_time = 3600 - (now - self._hour_timestamps[0])
            logger.warning(f"Rate limit reached (per hour), waiting {wait_time:.1f}s")
            await asyncio.sleep(min(wait_time, 300))  # 最多等 5 分钟
            return False

        # 记录请求
        self._minute_timestamps.append(now)
        self._hour_timestamps.append(now)
        return True

    def reset(self):
        """重置限制器"""
        self._minute_timestamps.clear()
        self._hour_timestamps.clear()


@dataclass
class CircuitBreaker:
    """
    熔断器

    连续失败超过阈值时，暂停请求一段时间
    """
    failure_threshold: int = 5
    recovery_timeout: int = 60  # 秒

    _failures: int = 0
    _last_failure_time: float = 0
    _state: CircuitState = CircuitState.CLOSED

    def record_success(self):
        """记录成功"""
        self._failures = 0
        self._state = CircuitState.CLOSED

    def record_failure(self):
        """记录失败"""
        self._failures += 1
        self._last_failure_time = time.time()

        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN after {self._failures} failures")

    def can_execute(self) -> bool:
        """检查是否可以执行"""
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # 检查是否可以尝试恢复
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker HALF_OPEN, attempting recovery")
                return True
            return False

        # HALF_OPEN 状态允许一次尝试
        return True

    @property
    def state(self) -> CircuitState:
        return self._state


async def retry_async(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    exponential: bool = True,
    exceptions: tuple = (Exception,),
) -> Any:
    """
    异步重试装饰器

    Args:
        func: 要执行的异步函数
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        exponential: 是否使用指数退避
        exceptions: 要捕获的异常类型

    Returns:
        函数执行结果
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(f"All {max_retries} retries failed: {e}")
                raise

            # 计算延迟
            if exponential:
                delay = min(base_delay * (2 ** attempt), max_delay)
            else:
                delay = base_delay

            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s")
            await asyncio.sleep(delay)

    raise last_exception


def with_retry(max_retries: int = 3, base_delay: float = 2.0):
    """
    重试装饰器

    Usage:
        @with_retry(max_retries=3)
        async def my_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                base_delay=base_delay,
            )
        return wrapper
    return decorator


# 全局限制器实例
PLATFORM_LIMITERS = {
    "linkedin": RateLimiter(requests_per_minute=5, requests_per_hour=50),
    "indeed": RateLimiter(requests_per_minute=10, requests_per_hour=200),
    "jobsdb": RateLimiter(requests_per_minute=15, requests_per_hour=300),
}

PLATFORM_BREAKERS = {
    "linkedin": CircuitBreaker(failure_threshold=3, recovery_timeout=120),
    "indeed": CircuitBreaker(failure_threshold=5, recovery_timeout=60),
    "jobsdb": CircuitBreaker(failure_threshold=5, recovery_timeout=60),
}


def get_rate_limiter(platform: str) -> RateLimiter:
    """获取平台速率限制器"""
    return PLATFORM_LIMITERS.get(platform, RateLimiter())


def get_circuit_breaker(platform: str) -> CircuitBreaker:
    """获取平台熔断器"""
    return PLATFORM_BREAKERS.get(platform, CircuitBreaker())
