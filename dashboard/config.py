"""配置管理模块 - 处理环境变量和应用配置"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
    """应用配置类"""
    # 认证配置
    app_password: str

    # 文件路径配置
    upload_dir: Path
    log_dir: Path
    core_script_path: Path

    # 应用配置
    max_file_size_mb: int = 10
    allowed_extensions: tuple = (".pdf", ".doc", ".docx", ".txt")

    @classmethod
    def from_env(cls) -> "AppConfig":
        """从环境变量加载配置"""
        # 获取项目根目录
        root_dir = Path(__file__).parent.parent.absolute()

        # 上传目录
        upload_dir = root_dir / "data" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 日志目录
        log_dir = root_dir / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # 核心脚本路径
        core_script = root_dir / "core" / "apply_bot.py"

        # 获取密码，如果未配置则报错
        password = os.getenv("APP_PASSWORD")
        if not password:
            import streamlit as st
            st.error("❌ 严重错误：未配置 APP_PASSWORD 环境变量！")
            st.stop()

        return cls(
            app_password=password,
            upload_dir=upload_dir,
            log_dir=log_dir,
            core_script_path=core_script,
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "10")),
        )


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置实例（单例模式）"""
    global _config
    if _config is None:
        _config = AppConfig.from_env()
    return _config


def get_upload_dir() -> Path:
    """获取上传目录路径"""
    return get_config().upload_dir


def get_log_dir() -> Path:
    """获取日志目录路径"""
    return get_config().log_dir


def get_core_script_path() -> Path:
    """获取核心脚本路径"""
    return get_config().core_script_path


def get_allowed_extensions() -> tuple:
    """获取允许的文件扩展名"""
    return get_config().allowed_extensions


def get_max_file_size() -> int:
    """获取最大文件大小（字节）"""
    return get_config().max_file_size_mb * 1024 * 1024
