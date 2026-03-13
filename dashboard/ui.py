"""UI组件和布局管理模块"""

import streamlit as st
from dashboard import state


def render_sidebar_header() -> None:
    """渲染侧边栏头部"""
    st.markdown("# 🎯 求职助手")
    st.markdown("智能求职自动化系统")


def render_session_info() -> None:
    """渲染会话信息"""
    st.markdown("---")
    st.markdown("### 📋 会话信息")
    session_id = state.get_session_id()
    st.code(f"🆔 Session ID: {session_id}")

    # 会话统计
    st.metric("简历", "✅" if state.get_resume_path() else "❌")
    st.metric("成绩单", "✅" if state.get_transcript_path() else "❌")
    st.metric("关键词", len(state.get_job_keywords()))
    st.metric("黑名单", len(state.get_blacklist_companies()))


def render_main_header() -> None:
    """渲染主界面头部"""
    col1, col2 = st.columns([3, 1])

    with col1:
        st.title("🎯 AutoJobAgent Dashboard")
        st.markdown("半自动化求职投递系统 - 让找工作更轻松")

    with col2:
        # 状态指示器
        if state.is_process_running():
            st.success("🟢 运行中")
        else:
            st.info("⚪ 就绪")


def render_footer() -> None:
    """渲染页面底部"""
    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption("© 2024 AutoJobAgent")

    with col2:
        st.caption("版本: v1.0.0")

    with col3:
        st.caption("Powered by Streamlit")


def render_help_section() -> None:
    """渲染帮助信息"""
    with st.expander("❓ 使用帮助", expanded=False):
        st.markdown("""
        ### 使用步骤

        1. **文件上传**
           - 上传简历（必填）
           - 上传成绩单（选填）

        2. **参数配置**
           - 设置职业关键词
           - 设置黑名单公司

        3. **执行任务**
           - 检查前置条件
           - 启动自动投递任务

        ### 注意事项

        - 确保简历文件格式正确
        - 关键词越精确，匹配越准确
        - 任务运行时请勿关闭浏览器

        ### 技术支持

        如有问题，请查看运行日志或联系技术支持。
        """)
