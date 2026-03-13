"""
投递历史组件 - Dashboard UI
显示用户的职位投递历史记录
"""

import streamlit as st
from pathlib import Path
import json
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def render_job_history(user_id: str):
    """
    渲染用户的投递历史记录

    Args:
        user_id: 用户 ID
    """
    # 🔴 删除重复标题（主 Dashboard 已有标题）
    # st.markdown("---")
    # st.markdown("## 📊 投递历史")

    # 读取用户的历史记录文件
    history_file = Path(f"data/histories/history_{user_id}.json")

    if not history_file.exists():
        st.info("📭 暂无投递记录")
        st.caption("当您开始使用自动投递功能后，投递历史将显示在这里。")
        return

    try:
        # 读取历史记录
        with open(history_file, 'r', encoding='utf-8') as f:
            history_data = json.load(f)

        if not history_data:
            st.info("📭 暂无投递记录")
            return

        # 转换为列表格式
        records = []
        for job_id, record in history_data.items():
            records.append({
                "job_id": job_id,
                "title": record.get("title", "N/A"),
                "company": record.get("company", "N/A"),
                "status": record.get("status", "unknown"),
                "score": record.get("score", 0),
                "reason": record.get("reason", ""),
                "link": record.get("link", ""),
                "processed_at": record.get("processed_at", ""),
                "resume_path": record.get("resume_path", ""),  # 🔴 新增：简历路径
                "cl_path": record.get("cl_path", ""),  # 🔴 新增：求职信路径
            })

        # 按时间倒序排序
        records.sort(key=lambda x: x["processed_at"], reverse=True)

        # 统计信息
        total_count = len(records)
        success_count = sum(1 for r in records if r["status"] == "success")
        skipped_count = sum(1 for r in records if "skipped" in r["status"])
        failed_count = sum(1 for r in records if r["status"] == "failed")

        # 显示统计卡片
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("📊 总计", total_count)

        with col2:
            st.metric("✅ 成功投递", success_count, delta_color="normal")

        with col3:
            st.metric("⏭️ 已跳过", skipped_count)

        with col4:
            st.metric("❌ 失败", failed_count, delta_color="inverse")

        st.markdown("---")

        # 筛选选项
        col_filter1, col_filter2 = st.columns([1, 1])

        with col_filter1:
            status_filter = st.multiselect(
                "📌 筛选状态",
                options=["success", "skipped_low_score", "skipped_permanent", "skipped_temporary", "failed"],
                default=None,
                help="选择要显示的状态类型"
            )

        with col_filter2:
            sort_by = st.selectbox(
                "🔄 排序方式",
                options=["时间（最新优先）", "时间（最旧优先）", "评分（高到低）", "评分（低到高）"],
                index=0
            )

        # 应用筛选
        filtered_records = records
        if status_filter:
            filtered_records = [r for r in records if r["status"] in status_filter]

        # 应用排序
        if sort_by == "时间（最旧优先）":
            filtered_records.sort(key=lambda x: x["processed_at"])
        elif sort_by == "评分（高到低）":
            filtered_records.sort(key=lambda x: x["score"], reverse=True)
        elif sort_by == "评分（低到高）":
            filtered_records.sort(key=lambda x: x["score"])

        # 显示记录数量
        st.caption(f"显示 {len(filtered_records)} 条记录（共 {total_count} 条）")

        # 显示记录列表
        if not filtered_records:
            st.info("🔍 没有符合筛选条件的记录")
            return

        # 渲染每条记录
        for idx, record in enumerate(filtered_records, 1):
            with st.container():
                # 状态图标和颜色
                status_config = {
                    "success": {"icon": "✅", "color": "green", "label": "成功投递"},
                    "skipped_low_score": {"icon": "⏭️", "color": "orange", "label": "评分过低"},
                    "skipped_permanent": {"icon": "🚫", "color": "red", "label": "永久跳过"},
                    "skipped_temporary": {"icon": "⏸️", "color": "blue", "label": "暂时跳过"},
                    "failed": {"icon": "❌", "color": "red", "label": "投递失败"},
                }

                status = record["status"]
                config = status_config.get(status, {"icon": "❓", "color": "gray", "label": status})

                # 创建卡片
                col_main, col_score, col_files, col_action = st.columns([5, 1, 2, 1])

                with col_main:
                    st.markdown(f"**{idx}. {record['title']}**")
                    st.caption(f"🏢 {record['company']}")

                    # 状态标签
                    st.markdown(
                        f"<span style='background-color: {config['color']}; color: white; padding: 2px 8px; border-radius: 5px; font-size: 12px;'>"
                        f"{config['icon']} {config['label']}"
                        f"</span>",
                        unsafe_allow_html=True
                    )

                    # 时间
                    try:
                        processed_time = datetime.fromisoformat(record["processed_at"])
                        time_str = processed_time.strftime("%Y-%m-%d %H:%M")
                        st.caption(f"🕒 {time_str}")
                    except:
                        st.caption(f"🕒 {record['processed_at']}")

                    # 原因（如果有）
                    if record["reason"]:
                        st.caption(f"💬 {record['reason']}")

                with col_score:
                    if record["score"] > 0:
                        # 根据评分显示不同颜色
                        if record["score"] >= 80:
                            score_color = "green"
                        elif record["score"] >= 60:
                            score_color = "orange"
                        else:
                            score_color = "red"

                        st.markdown(
                            f"<div style='text-align: center;'>"
                            f"<span style='font-size: 24px; font-weight: bold; color: {score_color};'>{record['score']}</span><br>"
                            f"<span style='font-size: 12px; color: gray;'>评分</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

                # 🔴 新增：简历和求职信下载按钮
                with col_files:
                    # 下载简历
                    if record["resume_path"] and Path(record["resume_path"]).exists():
                        with open(record["resume_path"], "rb") as f:
                            resume_data = f.read()
                        st.download_button(
                            label="📄 简历",
                            data=resume_data,
                            file_name=Path(record["resume_path"]).name,
                            mime="application/pdf",
                            key=f"resume_{idx}_{record['job_id']}",
                            use_container_width=True
                        )
                    else:
                        st.caption("📄 无简历")

                    # 下载求职信
                    if record["cl_path"] and Path(record["cl_path"]).exists():
                        with open(record["cl_path"], "rb") as f:
                            cl_data = f.read()
                        st.download_button(
                            label="📝 求职信",
                            data=cl_data,
                            file_name=Path(record["cl_path"]).name,
                            mime="application/pdf",
                            key=f"cl_{idx}_{record['job_id']}",
                            use_container_width=True
                        )
                    else:
                        st.caption("📝 无求职信")

                with col_action:
                    if record["link"]:
                        st.markdown(
                            f"<a href='{record['link']}' target='_blank' style='display: inline-block; padding: 8px 12px; background-color: #2196F3; color: white; text-decoration: none; border-radius: 5px; font-size: 12px; text-align: center;'>🔗 查看</a>",
                            unsafe_allow_html=True
                        )

                st.markdown("---")

        # 导出功能
        st.markdown("### 💾 导出数据")
        col_export1, col_export2 = st.columns([1, 3])

        with col_export1:
            if st.button("📥 导出为 CSV", use_container_width=True):
                # 创建 DataFrame
                df = pd.DataFrame(filtered_records)
                csv = df.to_csv(index=False, encoding='utf-8-sig')

                st.download_button(
                    label="⬇️ 下载 CSV 文件",
                    data=csv,
                    file_name=f"job_history_{user_id}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

        with col_export2:
            st.caption("导出当前筛选的记录为 CSV 文件，可用 Excel 打开")

    except Exception as e:
        logger.error(f"Failed to load job history: {e}")
        st.error(f"❌ 加载历史记录失败: {e}")


# Streamlit Fragment 版本（支持自动刷新）
@st.fragment(run_every=3)
def job_history_fragment(user_id: str):
    """
    投递历史 Fragment（每 3 秒自动刷新）

    Args:
        user_id: 用户 ID
    """
    render_job_history(user_id)
