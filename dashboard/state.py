"""状态管理模块 - 处理Streamlit会话状态"""

import streamlit as st
import uuid
from typing import Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class SessionData:
    """会话数据结构"""
    session_id: str
    authenticated: bool = False
    resume_path: Optional[str] = None
    transcript_path: Optional[str] = None
    job_keywords: List[str] = field(default_factory=list)
    blacklist_companies: List[str] = field(default_factory=list)
    process_running: bool = False
    process_pid: Optional[int] = None
    process_logs: List[str] = field(default_factory=list)


def init_session_state() -> None:
    """初始化会话状态"""
    # 生成唯一会话ID
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]

    # 认证状态
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # 文件路径
    if "resume_path" not in st.session_state:
        st.session_state.resume_path = None

    if "transcript_path" not in st.session_state:
        st.session_state.transcript_path = None

    # 参数配置
    if "job_keywords" not in st.session_state:
        st.session_state.job_keywords = []

    if "blacklist_companies" not in st.session_state:
        st.session_state.blacklist_companies = []

    if "title_exclusions" not in st.session_state:
        st.session_state.title_exclusions = []

    # 进程状态
    if "process_running" not in st.session_state:
        st.session_state.process_running = False

    if "process_pid" not in st.session_state:
        st.session_state.process_pid = None

    if "process_logs" not in st.session_state:
        st.session_state.process_logs = []


def get_session_id() -> str:
    """获取当前会话ID"""
    return st.session_state.get("session_id", "unknown")


def set_authenticated(value: bool) -> None:
    """设置认证状态"""
    st.session_state.authenticated = value


def is_authenticated() -> bool:
    """检查是否已认证"""
    return st.session_state.get("authenticated", False)


def set_resume_path(path: Optional[str]) -> None:
    """设置简历路径"""
    st.session_state.resume_path = path


def get_resume_path() -> Optional[str]:
    """获取简历路径"""
    return st.session_state.get("resume_path")


def set_transcript_path(path: Optional[str]) -> None:
    """设置成绩单路径"""
    st.session_state.transcript_path = path


def get_transcript_path() -> Optional[str]:
    """获取成绩单路径"""
    return st.session_state.get("transcript_path")


def set_job_keywords(keywords: List[str]) -> None:
    """设置职业关键词"""
    st.session_state.job_keywords = keywords


def get_job_keywords() -> List[str]:
    """获取职业关键词"""
    return st.session_state.get("job_keywords", [])


def set_blacklist_companies(companies: List[str]) -> None:
    """设置黑名单公司"""
    st.session_state.blacklist_companies = companies


def get_blacklist_companies() -> List[str]:
    """获取黑名单公司"""
    return st.session_state.get("blacklist_companies", [])


def set_title_exclusions(exclusions: List[str]) -> None:
    """设置职位标题排除词"""
    st.session_state.title_exclusions = exclusions


def get_title_exclusions() -> List[str]:
    """获取职位标题排除词"""
    return st.session_state.get("title_exclusions", [])


def set_process_running(running: bool, pid: Optional[int] = None) -> None:
    """设置进程运行状态"""
    st.session_state.process_running = running
    st.session_state.process_pid = pid


def is_process_running() -> bool:
    """检查进程是否运行中"""
    return st.session_state.get("process_running", False)


def get_process_pid() -> Optional[int]:
    """获取进程PID"""
    return st.session_state.get("process_pid")


def add_process_log(log: str) -> None:
    """添加进程日志"""
    if "process_logs" not in st.session_state:
        st.session_state.process_logs = []
    st.session_state.process_logs.append(log)


def get_process_logs() -> List[str]:
    """获取进程日志"""
    return st.session_state.get("process_logs", [])


def clear_process_logs() -> None:
    """清空进程日志"""
    st.session_state.process_logs = []


def reset_session() -> None:
    """重置会话（保留session_id）"""
    session_id = st.session_state.session_id
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.session_id = session_id
    init_session_state()
