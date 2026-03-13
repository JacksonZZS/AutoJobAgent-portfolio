"""文件上传模块 - 处理简历和成绩单上传"""

import streamlit as st
import os
from pathlib import Path
from typing import Optional, Tuple
from dashboard import config, state


def generate_filename(original_filename: str) -> str:
    """
    生成带会话ID前缀的文件名

    Args:
        original_filename: 原始文件名

    Returns:
        str: 新文件名 {session_id}_{original_filename}
    """
    session_id = state.get_session_id()
    return f"{session_id}_{original_filename}"


def validate_file(uploaded_file) -> Tuple[bool, str]:
    """
    验证上传的文件

    Args:
        uploaded_file: Streamlit上传的文件对象

    Returns:
        Tuple[bool, str]: (是否有效, 错误信息)
    """
    if uploaded_file is None:
        return False, "未选择文件"

    # 检查文件扩展名
    file_ext = Path(uploaded_file.name).suffix.lower()
    allowed_ext = config.get_allowed_extensions()
    if file_ext not in allowed_ext:
        return False, f"不支持的文件格式，允许的格式：{', '.join(allowed_ext)}"

    # 检查文件大小
    max_size = config.get_max_file_size()
    if uploaded_file.size > max_size:
        max_mb = config.get_config().max_file_size_mb
        return False, f"文件过大，最大允许 {max_mb}MB"

    return True, ""


def save_uploaded_file(uploaded_file, file_type: str) -> Optional[str]:
    """
    保存上传的文件

    Args:
        uploaded_file: Streamlit上传的文件对象
        file_type: 文件类型 ("resume" 或 "transcript")

    Returns:
        Optional[str]: 保存的文件绝对路径，失败返回None
    """
    try:
        # 验证文件
        is_valid, error_msg = validate_file(uploaded_file)
        if not is_valid:
            st.error(f"❌ {error_msg}")
            return None

        # 生成新文件名
        new_filename = generate_filename(uploaded_file.name)

        # 获取保存路径
        upload_dir = config.get_upload_dir()
        file_path = upload_dir / new_filename

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # 返回绝对路径
        abs_path = str(file_path.absolute())

        # 更新状态
        if file_type == "resume":
            state.set_resume_path(abs_path)
        elif file_type == "transcript":
            state.set_transcript_path(abs_path)

        return abs_path

    except Exception as e:
        st.error(f"❌ 文件保存失败：{str(e)}")
        return None


def render_upload_section() -> None:
    """渲染文件上传区域"""
    st.markdown("## 📁 文件上传")
    st.markdown("上传您的简历和成绩单（可选）以开始求职流程")

    col1, col2 = st.columns(2)

    # 简历上传（必填）
    with col1:
        st.markdown("### 📄 简历 *（必填）*")
        resume_file = st.file_uploader(
            "选择简历文件",
            type=["pdf", "doc", "docx", "txt"],
            key="resume_uploader",
            help="支持 PDF、Word、TXT 格式"
        )

        if resume_file:
            if st.button("📤 上传简历", key="upload_resume_btn"):
                saved_path = save_uploaded_file(resume_file, "resume")
                if saved_path:
                    st.success(f"✅ 简历上传成功！")
                    st.caption(f"保存路径：`{saved_path}`")

        # 显示当前状态
        current_resume = state.get_resume_path()
        if current_resume:
            st.info(f"📎 当前简历：`{Path(current_resume).name}`")

    # 成绩单上传（选填）
    with col2:
        st.markdown("### 📊 成绩单（选填）")
        transcript_file = st.file_uploader(
            "选择成绩单文件",
            type=["pdf", "doc", "docx", "txt"],
            key="transcript_uploader",
            help="支持 PDF、Word、TXT 格式"
        )

        if transcript_file:
            if st.button("📤 上传成绩单", key="upload_transcript_btn"):
                saved_path = save_uploaded_file(transcript_file, "transcript")
                if saved_path:
                    st.success(f"✅ 成绩单上传成功！")
                    st.caption(f"保存路径：`{saved_path}`")

        # 显示当前状态
        current_transcript = state.get_transcript_path()
        if current_transcript:
            st.info(f"📎 当前成绩单：`{Path(current_transcript).name}`")

    # 上传状态汇总
    st.markdown("---")
    st.markdown("### 📋 上传状态")

    status_col1, status_col2 = st.columns(2)
    with status_col1:
        if state.get_resume_path():
            st.success("✅ 简历已上传")
        else:
            st.warning("⚠️ 简历未上传（必填）")

    with status_col2:
        if state.get_transcript_path():
            st.success("✅ 成绩单已上传")
        else:
            st.info("ℹ️ 成绩单未上传（选填）")
