"""
Profile 编辑器 - 允许用户更新个人信息
"""

import streamlit as st
from core.user_identity import get_user_identity_manager, get_user_identity


def render_profile_editor(user_id: str):
    """
    渲染 Profile 编辑器

    Args:
        user_id: 用户 ID
    """
    st.markdown("## 👤 个人资料")

    # 获取当前用户信息
    identity_manager = get_user_identity_manager()
    user_identity = get_user_identity(user_id)

    if not user_identity:
        st.error("❌ 无法获取用户信息")
        return

    # 显示当前信息
    with st.expander("📋 当前信息", expanded=False):
        st.write(f"**用户名**: {user_identity.username}")
        st.write(f"**真实姓名**: {user_identity.real_name}")
        st.write(f"**邮箱**: {user_identity.email}")
        st.write(f"**电话**: {user_identity.phone}")
        if user_identity.linkedin:
            st.write(f"**LinkedIn**: {user_identity.linkedin}")
        if user_identity.github:
            st.write(f"**GitHub**: {user_identity.github}")
        if user_identity.location:
            st.write(f"**位置**: {user_identity.location}")

    st.markdown("---")
    st.markdown("### ✏️ 更新信息")

    # 编辑表单
    with st.form("profile_update_form"):
        real_name = st.text_input(
            "真实姓名",
            value=user_identity.real_name,
            help="用于生成简历的真实姓名"
        )

        email = st.text_input(
            "邮箱",
            value=user_identity.email,
            help="用于简历的联系邮箱"
        )

        phone = st.text_input(
            "电话",
            value=user_identity.phone,
            help="用于简历的联系电话"
        )

        linkedin = st.text_input(
            "LinkedIn",
            value=user_identity.linkedin or "",
            placeholder="例如: https://linkedin.com/in/yourname",
            help="LinkedIn 个人主页链接"
        )

        github = st.text_input(
            "GitHub",
            value=user_identity.github or "",
            placeholder="例如: https://github.com/yourname",
            help="GitHub 个人主页链接"
        )

        location = st.text_input(
            "所在地",
            value=user_identity.location or "",
            placeholder="例如: Hong Kong",
            help="您的所在地"
        )

        submit = st.form_submit_button("💾 保存更新", use_container_width=True, type="primary")

        if submit:
            # 验证输入
            if not real_name or not email or not phone:
                st.error("❌ 真实姓名、邮箱和电话不能为空")
            else:
                try:
                    # 更新用户信息
                    identity_manager.update_user(
                        user_id=user_id,
                        real_name=real_name,
                        email=email,
                        phone=phone,
                        linkedin=linkedin if linkedin else None,
                        github=github if github else None,
                        location=location if location else None
                    )

                    st.success("✅ 个人资料更新成功！")
                    st.balloons()
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ 更新失败: {e}")

    st.info("""
    💡 **提示**：
    - 这些信息将用于生成个性化简历
    - 请确保信息准确无误
    - 更新后立即生效
    """)
