"""任务处理模块 - 处理求职任务的执行"""

import streamlit as st
import subprocess
import sys
import os
import signal
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from dashboard import config, state
from core.llm_engine import LLMEngine, load_pdf_text


def build_command_args() -> Dict[str, Any]:
    """
    构建命令行参数

    Returns:
        Dict[str, Any]: 参数字典
    """
    return {
        "session_id": state.get_session_id(),
        "resume_path": state.get_resume_path(),
        "transcript_path": state.get_transcript_path(),
        "job_keywords": state.get_job_keywords(),
        "blacklist_companies": state.get_blacklist_companies(),
        "title_exclusions": state.get_title_exclusions(),
    }


def resolve_job_keywords() -> Optional[str]:
    """
    解析职业搜索关键词

    如果用户填写了关键词，直接返回；
    如果用户留空，则尝试从简历自动生成。

    Returns:
        关键词字符串，如果无法获取则返回 None
    """
    # 获取用户输入的关键词
    user_keywords_list = state.get_job_keywords()
    if user_keywords_list:
        # 用户已填写关键词，直接返回
        return ",".join(user_keywords_list)

    # 用户未填写，尝试从简历生成
    resume_path = state.get_resume_path()

    if not resume_path:
        st.error("❌ 请填写职业搜索关键词，或上传简历以自动生成关键词")
        return None

    if not os.path.exists(resume_path):
        st.error(f"❌ 简历文件不存在: {resume_path}")
        return None

    try:
        with st.spinner("🤖 正在分析简历生成搜索词..."):
            # 读取简历文本
            resume_text = load_pdf_text(resume_path)

            if not resume_text.strip():
                st.error("❌ 无法从简历中提取文本内容")
                return None

            # 初始化 LLM 引擎
            llm_engine = LLMEngine()

            # 生成关键词
            auto_kw = llm_engine.generate_job_search_keywords_from_resume(resume_text)

            if auto_kw:
                st.success(f"✅ 已自动为您匹配：{auto_kw}")
                # 将生成的关键词保存到 session_state
                keywords_list = [k.strip() for k in auto_kw.split(",")]
                state.set_job_keywords(keywords_list)
                return auto_kw
            else:
                st.error("❌ 无法从简历生成关键词，请手动输入")
                return None

    except FileNotFoundError as e:
        st.error(f"❌ {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ 生成关键词时出错: {e}")
        return None


def validate_before_run() -> tuple[bool, str]:
    """
    运行前验证

    Returns:
        tuple[bool, str]: (是否通过验证, 错误信息)
    """
    # 检查简历是否上传
    if not state.get_resume_path():
        return False, "请先上传简历"

    # 检查简历文件是否存在
    resume_path = state.get_resume_path()
    if not os.path.exists(resume_path):
        return False, f"简历文件不存在：{resume_path}"

    # 解析职业关键词（允许自动生成）
    keywords = resolve_job_keywords()
    if not keywords:
        return False, "无法获取职业关键词"

    return True, ""


def start_process() -> Optional[int]:
    """
    启动求职任务进程

    Returns:
        Optional[int]: 进程PID，失败返回None
    """
    try:
        # 获取脚本路径
        script_path = config.get_core_script_path()

        # 构建参数
        args = build_command_args()

        # 构建命令
        cmd = [
            sys.executable,
            str(script_path),
            "--resume", args["resume_path"],
            "--headless", "False",  # 强制有头模式，让用户观察浏览器进度
        ]

        # 添加可选参数
        if args["transcript_path"]:
            cmd += ["--transcript", args["transcript_path"]]

        if args["job_keywords"]:
            cmd += ["--keywords", ",".join(args["job_keywords"])]

        if args["blacklist_companies"]:
            cmd += ["--block_list", ",".join(args["blacklist_companies"])]

        if args["title_exclusions"]:
            cmd += ["--title_exclusions", ",".join(args["title_exclusions"])]

        # 记录启动日志
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state.add_process_log(f"[{timestamp}] 启动任务...")
        state.add_process_log(f"[{timestamp}] 会话ID: {args['session_id']}")
        state.add_process_log(f"[{timestamp}] 简历: {args['resume_path']}")
        state.add_process_log(f"[{timestamp}] 关键词: {', '.join(args['job_keywords'])}")

        # 启动子进程
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(config.get_config().upload_dir.parent.parent)
        )

        # 更新状态
        state.set_process_running(True, process.pid)
        state.add_process_log(f"[{timestamp}] 进程已启动，PID: {process.pid}")

        return process.pid

    except FileNotFoundError:
        state.add_process_log(f"[ERROR] 脚本文件不存在: {script_path}")
        st.error(f"❌ 脚本文件不存在：{script_path}")
        return None
    except Exception as e:
        state.add_process_log(f"[ERROR] 启动失败: {str(e)}")
        st.error(f"❌ 启动任务失败：{str(e)}")
        return None


def stop_process() -> bool:
    """
    停止求职任务进程

    Returns:
        bool: 是否成功停止
    """
    pid = state.get_process_pid()
    if pid is None:
        return False

    try:
        # 发送终止信号
        os.kill(pid, signal.SIGTERM)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state.add_process_log(f"[{timestamp}] 进程已停止，PID: {pid}")
        state.set_process_running(False, None)

        return True
    except ProcessLookupError:
        # 进程已经不存在
        state.set_process_running(False, None)
        return True
    except Exception as e:
        state.add_process_log(f"[ERROR] 停止进程失败: {str(e)}")
        return False


def render_process_section() -> None:
    """渲染任务执行区域"""
    st.markdown("## 🚀 执行任务")
    st.markdown("启动自动求职任务")

    # 前置条件检查
    st.markdown("### 📋 前置条件检查")

    check_col1, check_col2, check_col3 = st.columns(3)

    with check_col1:
        if state.get_resume_path():
            st.success("✅ 简历已上传")
        else:
            st.error("❌ 简历未上传")

    with check_col2:
        keywords = state.get_job_keywords()
        if keywords:
            st.success(f"✅ 已设置 {len(keywords)} 个关键词")
        else:
            st.error("❌ 未设置关键词")

    with check_col3:
        blacklist = state.get_blacklist_companies()
        if blacklist:
            st.info(f"ℹ️ 已设置 {len(blacklist)} 个黑名单")
        else:
            st.info("ℹ️ 无黑名单公司")

    st.markdown("---")

    # 任务参数预览
    st.markdown("### 📝 任务参数预览")

    with st.expander("查看完整参数", expanded=False):
        args = build_command_args()
        st.json(args)

    st.markdown("---")

    # 控制按钮
    st.markdown("### 🎮 任务控制")

    is_running = state.is_process_running()

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        # 启动按钮
        start_disabled = is_running
        if st.button(
            "▶️ 启动任务",
            use_container_width=True,
            type="primary",
            disabled=start_disabled
        ):
            # 验证
            is_valid, error_msg = validate_before_run()
            if not is_valid:
                st.error(f"❌ {error_msg}")
            else:
                pid = start_process()
                if pid:
                    st.success(f"✅ 任务已启动！PID: {pid}")
                    st.balloons()
                    st.rerun()

    with col2:
        # 停止按钮
        stop_disabled = not is_running
        if st.button(
            "⏹️ 停止任务",
            use_container_width=True,
            type="secondary",
            disabled=stop_disabled
        ):
            if stop_process():
                st.warning("⚠️ 任务已停止")
                st.rerun()
            else:
                st.error("❌ 停止任务失败")

    with col3:
        # 清空日志按钮
        if st.button(
            "🗑️ 清空日志",
            use_container_width=True,
            type="secondary"
        ):
            state.clear_process_logs()
            st.info("ℹ️ 日志已清空")
            st.rerun()

    st.markdown("---")

    # 任务状态
    st.markdown("### 📊 任务状态")

    if is_running:
        st.success(f"🟢 任务运行中 (PID: {state.get_process_pid()})")
    else:
        st.info("⚪ 任务未运行")

    # 日志显示
    st.markdown("### 📋 运行日志")

    logs = state.get_process_logs()
    if logs:
        log_container = st.container()
        with log_container:
            for log in logs[-50:]:  # 只显示最近50条
                st.text(log)
    else:
        st.caption("暂无日志")
