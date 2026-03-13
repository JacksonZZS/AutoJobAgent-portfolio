"""
认证界面组件 - Streamlit 登录/注册表单
"""

import streamlit as st
from core.auth_manager import get_auth_manager


def render_auth_page():
    """
    渲染认证页面（登录/注册）

    Returns:
        True 如果用户已认证，False 如果需要继续显示认证页面
    """
    # 检查是否已登录
    if "authenticated" in st.session_state and st.session_state.authenticated:
        return True

    # 页面配置
    st.markdown("""
        <style>
        .auth-container {
            max-width: 500px;
            margin: 0 auto;
            padding: 2rem;
        }
        .auth-title {
            text-align: center;
            color: #1f77b4;
            margin-bottom: 2rem;
        }
        .auth-subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # 标题
    st.markdown('<h1 class="auth-title">🤖 AutoJobAgent</h1>', unsafe_allow_html=True)
    st.markdown('<p class="auth-subtitle">智能求职自动化系统 - SaaS 多用户版</p>', unsafe_allow_html=True)

    # 登录/注册切换
    auth_mode = st.radio(
        "选择操作",
        ["登录", "注册"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.markdown("---")

    auth_manager = get_auth_manager()

    if auth_mode == "登录":
        render_login_form(auth_manager)
    else:
        render_register_form(auth_manager)

    return False


def render_login_form(auth_manager):
    """渲染登录表单"""
    st.subheader("🔐 用户登录")

    with st.form("login_form"):
        username = st.text_input(
            "用户名",
            placeholder="请输入用户名",
            help="输入您注册时使用的用户名"
        )

        password = st.text_input(
            "密码",
            type="password",
            placeholder="请输入密码",
            help="输入您的密码"
        )

        # 🔴 [新功能] 记住登录状态选项
        remember_me = st.checkbox("记住我（30天内自动登录）", value=True)

        # 🔴 移除 Demo 登录按钮，只保留正式登录
        submit = st.form_submit_button("登录", use_container_width=True, type="primary")

        if submit:
            if not username or not password:
                st.error("❌ 请输入用户名和密码")
            else:
                with st.spinner("正在验证..."):
                    success, user_info, message = auth_manager.login(username, password)

                    if success:
                        # 登录成功，保存到 session
                        st.session_state.authenticated = True
                        st.session_state.user_id = user_info["id"]
                        st.session_state.username = user_info["username"]
                        st.session_state.user_email = user_info.get("email", "")

                        # 🔴 [新功能] 如果勾选"记住我"，保存会话令牌
                        if remember_me:
                            from core.session_manager import get_session_manager
                            session_mgr = get_session_manager()
                            token = session_mgr.create_session(
                                user_id=user_info["id"],
                                username=user_info["username"],
                                email=user_info.get("email", ""),
                                expiry_days=30  # 30 天有效期
                            )

                            if token:
                                st.session_state.session_token = token
                                st.success(f"✅ {message}（已保存登录状态）")
                            else:
                                st.success(f"✅ {message}")
                                st.warning("⚠️ 会话保存失败，下次需要重新登录")
                        else:
                            st.success(f"✅ {message}")

                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

    # 🔴 更新提示信息
    st.info("""
    💡 **提示**：
    - 首次使用请先注册账号
    - 勾选"记住我"可在 30 天内免登录
    - 忘记密码请联系管理员
    """)


def render_register_form(auth_manager):
    """渲染注册表单（包含 Profile 信息）"""
    st.subheader("📝 用户注册")

    with st.form("register_form"):
        st.markdown("#### 账户信息")
        username = st.text_input(
            "用户名",
            placeholder="请输入用户名（至少 3 个字符）",
            help="用户名将作为您的唯一标识"
        )

        email = st.text_input(
            "邮箱",
            placeholder="请输入邮箱地址",
            help="用于找回密码和接收通知"
        )

        password = st.text_input(
            "密码",
            type="password",
            placeholder="请输入密码（至少 6 个字符）",
            help="请设置一个安全的密码"
        )

        password_confirm = st.text_input(
            "确认密码",
            type="password",
            placeholder="请再次输入密码",
            help="请再次输入相同的密码"
        )

        st.markdown("---")
        st.markdown("#### Profile 信息（用于简历生成）")

        real_name = st.text_input(
            "真实姓名",
            placeholder="例如: Jackson Zhang",
            help="用于生成简历的真实姓名"
        )

        phone = st.text_input(
            "电话",
            placeholder="例如: +852 1234 5678",
            help="用于简历的联系电话"
        )

        linkedin = st.text_input(
            "LinkedIn（可选）",
            placeholder="例如: https://linkedin.com/in/yourname",
            help="LinkedIn 个人主页链接"
        )

        github = st.text_input(
            "GitHub（可选）",
            placeholder="例如: https://github.com/yourname",
            help="GitHub 个人主页链接"
        )

        location = st.text_input(
            "所在地（可选）",
            placeholder="例如: Hong Kong",
            help="您的所在地"
        )

        submit = st.form_submit_button("注册", use_container_width=True, type="primary")

        if submit:
            # 验证输入
            if not username or not password:
                st.error("❌ 用户名和密码不能为空")
            elif not email:
                st.error("❌ 邮箱不能为空")
            elif not real_name:
                st.error("❌ 真实姓名不能为空")
            elif not phone:
                st.error("❌ 电话不能为空")
            elif len(username) < 3:
                st.error("❌ 用户名至少需要 3 个字符")
            elif len(password) < 6:
                st.error("❌ 密码至少需要 6 个字符")
            elif password != password_confirm:
                st.error("❌ 两次输入的密码不一致")
            else:
                with st.spinner("正在注册..."):
                    success, message = auth_manager.register(
                        username=username,
                        password=password,
                        email=email,
                        real_name=real_name,
                        phone=phone,
                        linkedin=linkedin if linkedin else None,
                        github=github if github else None,
                        location=location if location else None
                    )

                    if success:
                        # 🔴 [修复] 注册成功后立即自动登录，不显示多余的 UI
                        login_success, user_info, login_message = auth_manager.login(username, password)

                        if login_success:
                            # 设置 session_state
                            st.session_state.authenticated = True
                            st.session_state.user_id = user_info["id"]
                            st.session_state.username = user_info["username"]
                            st.session_state.user_email = user_info.get("email", "")

                            # 🔴 [新功能] 保存会话令牌（记住登录状态）
                            from core.session_manager import get_session_manager
                            session_mgr = get_session_manager()
                            token = session_mgr.create_session(
                                user_id=user_info["id"],
                                username=user_info["username"],
                                email=user_info.get("email", ""),
                                expiry_days=30  # 30 天有效期
                            )

                            if token:
                                # 保存令牌到 session_state
                                st.session_state.session_token = token

                            # 🔴 [关键修复] 设置注册成功标志，延迟显示消息到下一次渲染
                            st.session_state.just_registered = True

                            # 🔴 [关键修复] 立即 rerun，不要在这里显示任何 UI
                            st.rerun()
                        else:
                            st.error(f"❌ 自动登录失败: {login_message}")
                            st.info("请切换到「登录」标签页手动登录")
                    else:
                        st.error(f"❌ {message}")

    # 提示信息
    st.info("""
    💡 **注册须知**：
    - 用户名必须唯一，至少 3 个字符
    - 密码至少 6 个字符
    - 邮箱、真实姓名、电话为必填项
    - Profile 信息将用于生成个性化简历
    - 注册成功后将自动登录
    """)


def render_user_info_sidebar():
    """在侧边栏渲染用户信息"""
    if "authenticated" in st.session_state and st.session_state.authenticated:
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 👤 用户信息")

            st.write(f"**用户名**: {st.session_state.username}")
            st.write(f"**用户 ID**: {st.session_state.user_id}")

            if st.session_state.get("user_email"):
                st.write(f"**邮箱**: {st.session_state.user_email}")

            if st.button("🚪 退出登录", use_container_width=True):
                # 🔴 [新功能] 清除保存的会话令牌
                if st.session_state.get("session_token"):
                    from core.session_manager import get_session_manager
                    session_mgr = get_session_manager()
                    session_mgr.delete_session(st.session_state.user_id)

                # 清除认证信息
                st.session_state.authenticated = False
                st.session_state.user_id = None
                st.session_state.username = None
                st.session_state.user_email = None
                st.session_state.session_token = None

                st.success("✅ 已退出登录")
                st.rerun()


def check_authentication() -> bool:
    """
    检查用户是否已认证（支持自动登录）

    Returns:
        True 如果已认证，False 如果未认证
    """
    # 如果当前 session 中已经认证，直接返回
    if st.session_state.get("authenticated"):
        return True

    # 🔴 [新功能] 尝试从保存的会话令牌自动登录
    if "auto_login_checked" not in st.session_state:
        st.session_state.auto_login_checked = True

        # 尝试读取所有会话文件，找到有效的会话
        from core.session_manager import get_session_manager
        from pathlib import Path

        session_mgr = get_session_manager()
        session_dir = session_mgr.session_dir

        # 遍历所有会话文件
        for session_file in session_dir.glob("session_*.json"):
            try:
                import json
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)

                user_id = session_data.get("user_id")
                token = session_data.get("token")

                # 验证会话
                user_info = session_mgr.verify_session(user_id, token)

                if user_info:
                    # 会话有效，自动登录
                    st.session_state.authenticated = True
                    st.session_state.user_id = user_info["id"]
                    st.session_state.username = user_info["username"]
                    st.session_state.user_email = user_info.get("email", "")
                    st.session_state.session_token = token

                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Auto-login successful for user: {user_info['username']}")

                    return True

            except Exception as e:
                # 忽略损坏的会话文件
                continue

        # 清理过期会话
        session_mgr.cleanup_expired_sessions()

    return st.session_state.get("authenticated", False)
