"""认证模块 - 处理用户登录验证"""

import streamlit as st
from dashboard import config, state


def verify_password(password: str) -> bool:
    """
    验证密码是否正确

    Args:
        password: 用户输入的密码

    Returns:
        bool: 密码是否正确
    """
    app_config = config.get_config()
    return password == app_config.app_password


def render_login_form() -> None:
    """渲染登录表单"""
    st.markdown("### 🔐 安全验证")
    st.markdown("---")

    # 密码输入
    password = st.text_input(
        "请输入访问密码",
        type="password",
        key="login_password",
        placeholder="输入密码后按回车或点击登录"
    )

    # 登录按钮
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔓 登录", use_container_width=True, type="primary"):
            if verify_password(password):
                state.set_authenticated(True)
                st.success("✅ 验证成功！")
                st.rerun()
            else:
                st.error("❌ 密码错误，请重试")

    # 提示信息
    st.markdown("---")
    st.caption("💡 提示：默认密码可通过环境变量 `APP_PASSWORD` 设置")


def render_logout_button() -> None:
    """渲染登出按钮"""
    st.markdown("---")
    if st.button("🚪 退出登录", use_container_width=True):
        state.set_authenticated(False)
        st.rerun()


def require_auth(func):
    """
    认证装饰器 - 确保函数只在认证后执行

    Args:
        func: 需要认证的函数

    Returns:
        包装后的函数
    """
    def wrapper(*args, **kwargs):
        if not state.is_authenticated():
            st.warning("⚠️ 请先登录")
            return None
        return func(*args, **kwargs)
    return wrapper
