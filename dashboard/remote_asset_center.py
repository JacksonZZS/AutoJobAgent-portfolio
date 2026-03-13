"""
远程物料中心 - Dashboard UI 组件
为用户自主投递模式提供远程协作界面

职责划分：
- 服务器：后台静默抓取 JD、AI 评分、生成个性化 CV/CL 物料
- 用户：在 Dashboard 获取物料后，在自己的浏览器中登录 JobsDB 并完成投递
"""

import streamlit as st
from pathlib import Path
from typing import Optional, Dict, Any
import base64
import time
from datetime import datetime
import logging

from core.status_manager import get_status_manager, TaskStatus
from core.user_identity import get_user_identity, get_username

logger = logging.getLogger(__name__)


class RemoteAssetCenter:
    """远程物料中心管理器"""

    @staticmethod
    def get_file_download_link(file_path: str, link_text: str) -> str:
        """
        生成文件下载链接

        Args:
            file_path: 文件路径
            link_text: 链接文本

        Returns:
            HTML 下载链接
        """
        try:
            with open(file_path, "rb") as f:
                data = f.read()

            b64 = base64.b64encode(data).decode()
            file_name = Path(file_path).name

            href = f'<a href="data:application/pdf;base64,{b64}" download="{file_name}" style="display:inline-block; padding:10px 20px; background-color:#4CAF50; color:white; text-decoration:none; border-radius:5px; font-weight:bold;">{link_text}</a>'

            return href

        except Exception as e:
            return f'<span style="color:red;">文件不存在: {str(e)}</span>'

    @staticmethod
    def render_asset_center(user_id: str):
        """
        渲染远程物料中心 UI

        Args:
            user_id: 用户 ID
        """
        # 🔴 删除重复标题（主 Dashboard 已有标题）
        # st.markdown("---")
        # st.markdown("## 📦 远程物料中心")

        # 获取用户身份信息
        user_identity = get_user_identity(user_id)
        username = get_username(user_id)

        if not user_identity:
            st.error("❌ 无法获取用户身份信息")
            return

        # 显示用户信息
        with st.expander("👤 我的身份信息", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**用户名**: {username}")
                st.write(f"**真实姓名**: {user_identity.real_name}")
                st.write(f"**邮箱**: {user_identity.email}")

            with col2:
                st.write(f"**电话**: {user_identity.phone}")
                if user_identity.location:
                    st.write(f"**位置**: {user_identity.location}")
                if user_identity.linkedin:
                    st.write(f"**LinkedIn**: {user_identity.linkedin}")

        # 获取当前任务状态
        status_manager = get_status_manager(user_id=user_id)
        current_status = status_manager.read_status()

        # 检查是否有待处理的半自动任务
        if current_status.get("status") == TaskStatus.MANUAL_REVIEW.value:
            RemoteAssetCenter._render_pending_job(user_id, current_status)
        else:
            st.info("ℹ️ 当前没有待处理的半自动任务")

            # 显示最近的任务历史
            RemoteAssetCenter._render_recent_jobs(user_id)

    @staticmethod
    def _render_pending_job(user_id: str, status_data: Dict[str, Any]):
        """
        渲染待处理的半自动任务

        Args:
            user_id: 用户 ID
            status_data: 状态数据
        """
        manual_review_data = status_data.get("manual_review_data", {})

        if not manual_review_data:
            st.warning("⚠️ 半自动任务数据不完整")
            return

        # 提取任务信息
        job_title = manual_review_data.get("job_title", "未知职位")
        company_name = manual_review_data.get("company_name", "未知公司")
        score = manual_review_data.get("score", 0)
        job_url = manual_review_data.get("job_url", "")
        resume_path = manual_review_data.get("resume_path", "")
        cl_path = manual_review_data.get("cl_path", "")
        cl_text = manual_review_data.get("cl_text", "")

        # 🔴 [新增] 自动在用户本地浏览器弹出职位页面
        # 使用 session_state 避免重复弹出
        popup_key = f"popup_shown_{user_id}_{manual_review_data.get('job_url', '')}"

        if job_url and popup_key not in st.session_state:
            # 标记为已弹出，避免重复
            st.session_state[popup_key] = True

            # 使用 JavaScript 自动打开新标签页
            st.components.v1.html(
                f"""
                <script>
                    // 自动在用户本地浏览器打开职位页面
                    window.open('{job_url}', '_blank');
                    console.log('Auto-opened job URL: {job_url}');
                </script>
                """,
                height=0
            )

            # 显示提示信息
            st.success(f"✨ 已在新标签页自动打开职位页面：{job_title}")
            st.info("💡 提示：首次使用需要登录 JobsDB，登录后浏览器会记住您的账号，下次无需再登录")

        # 显示任务卡片
        st.markdown("### 🎯 待处理任务")

        # 任务信息
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**职位**: {job_title}")
            st.markdown(f"**公司**: {company_name}")
            st.markdown(f"**匹配度**: {score} 分")

        with col2:
            if score >= 60:
                st.success(f"✅ {score} 分")
            else:
                st.warning(f"⚠️ {score} 分")

        st.markdown("---")

        # 操作按钮区域
        st.markdown("### 📥 物料下载")

        col1, col2, col3 = st.columns(3)

        with col1:
            # 下载定制简历
            if resume_path and Path(resume_path).exists():
                download_link = RemoteAssetCenter.get_file_download_link(
                    resume_path,
                    "📄 下载定制简历"
                )
                st.markdown(download_link, unsafe_allow_html=True)
            else:
                st.error("❌ 简历文件不存在")

        with col2:
            # 下载求职信 PDF
            if cl_path and Path(cl_path).exists():
                download_link = RemoteAssetCenter.get_file_download_link(
                    cl_path,
                    "📝 下载求职信"
                )
                st.markdown(download_link, unsafe_allow_html=True)
            else:
                st.warning("⚠️ 求职信 PDF 未生成")

        with col3:
            # 直达职位页面
            if job_url:
                st.markdown(
                    f'<a href="{job_url}" target="_blank" style="display:inline-block; padding:10px 20px; background-color:#2196F3; color:white; text-decoration:none; border-radius:5px; font-weight:bold;">🔗 直达职位页面</a>',
                    unsafe_allow_html=True
                )
            else:
                st.error("❌ 职位链接不可用")

        # 复制求职信文本
        if cl_text:
            st.markdown("### 📋 求职信文本")

            with st.expander("点击查看求职信内容", expanded=False):
                st.text_area(
                    "求职信内容",
                    value=cl_text,
                    height=300,
                    key="cl_text_display"
                )

            # 复制按钮
            if st.button("📋 复制求职信到剪贴板", key="copy_cl"):
                # 使用 JavaScript 复制到剪贴板
                st.components.v1.html(
                    f"""
                    <script>
                    navigator.clipboard.writeText(`{cl_text.replace('`', '\\`')}`);
                    alert('求职信已复制到剪贴板！');
                    </script>
                    """,
                    height=0
                )

        st.markdown("---")

        # 用户决策按钮
        st.markdown("### ✅ 处理决策")

        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            if st.button("✅ 确认投递", type="primary", key="confirm_apply"):
                status_manager = get_status_manager(user_id=user_id)

                # 🔴 [修复] 设置 APPLY 决策
                status_manager.set_manual_decision("APPLY")

                # 🔴 [DEBUG] 记录确认操作
                logger.info("=" * 60)
                logger.info("✅ [用户操作] 确认投递:")
                logger.info(f"   职位: {job_title}")
                logger.info(f"   公司: {company_name}")
                logger.info(f"   时间: {datetime.now().isoformat()}")
                logger.info("=" * 60)

                # 🔴 [关键修复] 写入历史记录
                try:
                    from core.history_manager import HistoryManager
                    history_mgr = HistoryManager(user_id=user_id)

                    # 写入历史记录
                    logger.info("=" * 60)
                    logger.info("📝 [DEBUG] 开始写入投递历史:")
                    logger.info(f"   - job_url: {job_url}")
                    logger.info(f"   - job_title: {job_title}")
                    logger.info(f"   - company: {company_name}")
                    logger.info(f"   - score: {score}")
                    logger.info(f"   - status: success")
                    logger.info(f"   - user_id: {user_id}")

                    history_mgr.add_job(
                        link=job_url,
                        title=job_title,
                        company=company_name,
                        status="success",  # 标记为成功投递
                        score=score,
                        reason="User confirmed apply via Remote Asset Center",
                        resume_path=resume_path,  # 🔴 新增：保存简历路径
                        cl_path=cl_path  # 🔴 新增：保存求职信路径
                    )

                    # 验证写入结果
                    import json
                    history_file = Path(f"data/histories/history_{user_id}.json")

                    if history_file.exists():
                        with open(history_file, 'r', encoding='utf-8') as f:
                            history_content = json.load(f)
                        logger.info(f"✅ [DEBUG] 历史文件存在: {history_file}")
                        logger.info(f"✅ [DEBUG] 历史记录总数: {len(history_content)}")

                        # 检查当前职位是否在历史中
                        job_id = history_mgr.get_job_id(job_url)
                        if job_id in history_content:
                            logger.info(f"✅ [DEBUG] 职位已成功写入历史: {job_id}")
                            logger.info(f"✅ [DEBUG] 记录内容: {history_content[job_id]}")
                        else:
                            logger.error(f"❌ [DEBUG] 职位未找到在历史中: {job_id}")
                            logger.error(f"❌ [DEBUG] 当前历史中的 job_id 列表: {list(history_content.keys())}")
                    else:
                        logger.error(f"❌ [DEBUG] 历史文件不存在: {history_file}")

                    logger.info("=" * 60)
                    logger.info(f"✅ 已写入投递历史: {job_title} @ {company_name}")

                except Exception as e:
                    logger.error(f"❌ 写入历史记录失败: {e}")
                    logger.exception("完整错误堆栈:")
                    st.error(f"❌ 写入历史记录失败: {e}")

                # 🔴 [关键修复] 先删除 lock_file，让后台进程继续运行并读取决策
                # ⚠️ 不要清除 manual_review_data，让后台进程读取决策后自己清除
                lock_file = Path(f"data/locks/user_interaction_{user_id}.lock")
                logger.info("=" * 60)
                logger.info("🔍 [DEBUG] 尝试删除 lock_file (确认投递):")
                logger.info(f"   路径: {lock_file}")
                logger.info(f"   文件是否存在: {lock_file.exists()}")

                if lock_file.exists():
                    try:
                        lock_file.unlink()
                        logger.info("✅ lock_file 已成功删除")

                        # 验证删除
                        if not lock_file.exists():
                            logger.info("✅ 验证通过: lock_file 已不存在")
                        else:
                            logger.error("❌ 验证失败: lock_file 仍然存在！")
                    except Exception as e:
                        logger.error(f"❌ 删除 lock_file 失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                else:
                    logger.warning("⚠️ lock_file 不存在，跳过删除")

                logger.info("=" * 60)

                st.success("✅ 已确认投递！系统将继续处理...")
                time.sleep(0.5)
                st.rerun()

        with col2:
            if st.button("⏸️ 稍后处理", key="skip_temporary", use_container_width=True):
                status_manager = get_status_manager(user_id=user_id)

                # 🔴 设置暂时跳过决策（下次仍会出现）
                status_manager.set_manual_decision("SKIP_TEMPORARY")

                # 🔴 [DEBUG] 记录操作
                logger.info("=" * 60)
                logger.info("⏸️ [用户操作] 稍后处理（下次仍显示）:")
                logger.info(f"   职位: {job_title}")
                logger.info(f"   公司: {company_name}")
                logger.info(f"   时间: {datetime.now().isoformat()}")
                logger.info("=" * 60)

                # 删除 lock_file，让后台进程继续
                lock_file = Path(f"data/locks/user_interaction_{user_id}.lock")
                if lock_file.exists():
                    try:
                        lock_file.unlink()
                        logger.info("✅ lock_file 已成功删除")
                    except Exception as e:
                        logger.error(f"❌ 删除 lock_file 失败: {e}")

                st.success("✅ 已暂时跳过！下次运行时仍会显示此职位")
                time.sleep(0.5)
                st.rerun()

        with col3:
            if st.button("🚫 永久跳过", key="skip_permanent", use_container_width=True):
                status_manager = get_status_manager(user_id=user_id)

                # 🔴 设置永久跳过决策（永久屏蔽）
                status_manager.set_manual_decision("SKIP_PERMANENT")

                # 🔴 [DEBUG] 记录操作
                logger.info("=" * 60)
                logger.info("🚫 [用户操作] 永久跳过（不再显示）:")
                logger.info(f"   职位: {job_title}")
                logger.info(f"   公司: {company_name}")
                logger.info(f"   时间: {datetime.now().isoformat()}")
                logger.info("=" * 60)

                # 🔴 [关键修复] 写入历史记录（标记为永久跳过）
                try:
                    from core.history_manager import HistoryManager
                    history_mgr = HistoryManager(user_id=user_id)

                    # 写入历史记录
                    logger.info("=" * 60)
                    logger.info("📝 [DEBUG] 写入永久跳过记录:")
                    logger.info(f"   - job_url: {job_url}")
                    logger.info(f"   - job_title: {job_title}")
                    logger.info(f"   - company: {company_name}")
                    logger.info(f"   - status: skipped_permanent")

                    history_mgr.add_job(
                        link=job_url,
                        title=job_title,
                        company=company_name,
                        status="skipped_permanent",  # 标记为永久跳过
                        score=score,
                        reason="User permanently skipped via Remote Asset Center",
                        resume_path=resume_path,  # 🔴 新增：保存简历路径（即使跳过也保存，方便查看）
                        cl_path=cl_path  # 🔴 新增：保存求职信路径
                    )

                    logger.info("✅ [DEBUG] 永久跳过记录已写入历史")
                    logger.info("=" * 60)

                except Exception as e:
                    logger.error(f"❌ 写入历史记录失败: {e}")
                    logger.exception("完整错误堆栈:")
                    st.error(f"❌ 写入历史记录失败: {e}")

                # 删除 lock_file，让后台进程继续
                lock_file = Path(f"data/locks/user_interaction_{user_id}.lock")
                if lock_file.exists():
                    try:
                        lock_file.unlink()
                        logger.info("✅ lock_file 已成功删除")
                    except Exception as e:
                        logger.error(f"❌ 删除 lock_file 失败: {e}")

                st.success("✅ 已永久跳过！此职位将不再显示")
                time.sleep(0.5)
                st.rerun()

        # 提示信息
        st.caption("💡 提示：")
        st.caption("  • ✅ 确认投递：系统将自动完成投递流程")
        st.caption("  • ⏸️ 稍后处理：本次不投，下次仍会出现")
        st.caption("  • 🚫 永久跳过：永久屏蔽此职位，不再显示")

    @staticmethod
    def _render_recent_jobs(user_id: str):
        """
        渲染最近的任务历史

        Args:
            user_id: 用户 ID
        """
        from core.global_monitor import get_global_monitor

        st.markdown("### 📊 最近任务")

        monitor = get_global_monitor()
        recent_events = monitor.get_recent_events(limit=10, user_id=user_id)

        if not recent_events:
            st.info("暂无任务历史")
            return

        # 筛选出任务相关事件
        job_events = [
            e for e in recent_events
            if e.get("event_type") in [
                "job_scored",
                "job_applied_auto",
                "job_pending_review",
                "job_skipped"
            ]
        ]

        if not job_events:
            st.info("暂无任务历史")
            return

        # 显示任务列表
        for event in job_events[:5]:
            event_type = event.get("event_type", "")
            message = event.get("message", "")
            timestamp = event.get("timestamp", "")[:19]
            extra = event.get("extra", {})

            # 根据事件类型选择图标和颜色
            if event_type == "job_applied_auto":
                icon = "✅"
                color = "green"
            elif event_type == "job_pending_review":
                icon = "⏳"
                color = "orange"
            elif event_type == "job_skipped":
                icon = "⏭️"
                color = "gray"
            else:
                icon = "📊"
                color = "blue"

            with st.container():
                col1, col2 = st.columns([1, 4])

                with col1:
                    st.markdown(f"<h3 style='color:{color};'>{icon}</h3>", unsafe_allow_html=True)

                with col2:
                    st.markdown(f"**{message}**")
                    st.caption(f"时间: {timestamp}")

                    if extra:
                        score = extra.get("score")
                        decision = extra.get("decision")

                        if score:
                            st.caption(f"评分: {score} 分")
                        if decision:
                            st.caption(f"决策: {decision}")

                st.markdown("---")


# Streamlit Fragment 版本（支持自动刷新）
@st.fragment(run_every=3)
def remote_asset_center_fragment(user_id: str):
    """
    远程物料中心 Fragment（每 3 秒自动刷新）

    Args:
        user_id: 用户 ID
    """
    RemoteAssetCenter.render_asset_center(user_id)
