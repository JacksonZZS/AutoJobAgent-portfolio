"""参数配置模块 - 处理职业关键词和黑名单公司设置"""

import streamlit as st
import json
from typing import List, Optional, Dict
from dashboard import state


def parse_input_list(input_text: str) -> List[str]:
    """
    解析用户输入的列表文本
    支持逗号、分号、换行分隔

    Args:
        input_text: 用户输入的文本

    Returns:
        List[str]: 解析后的列表
    """
    if not input_text or not input_text.strip():
        return []

    # 统一分隔符
    text = input_text.replace("；", ";").replace("，", ",")
    text = text.replace("\n", ",").replace(";", ",")

    # 分割并清理
    items = [item.strip() for item in text.split(",")]
    items = [item for item in items if item]  # 移除空项

    return items


def analyze_resume_with_llm(resume_content: str, api_key: str, model: str = "gpt-4o-mini") -> Optional[Dict[str, str]]:
    """
    使用 LLM 分析简历并生成搜索参数

    Args:
        resume_content: 简历文本内容
        api_key: OpenAI API Key
        model: 使用的模型名称

    Returns:
        包含 keywords, blocked_companies, title_exclusions 的字典，失败返回 None
    """
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        prompt = f"""Analyze the resume to determine the candidate's seniority and generate job search parameters.

Resume content:
{resume_content}

Based on the resume's skills, experience, and seniority level, generate the following parameters:

1. **keywords**: 3-5 job search keywords suitable for this candidate (comma-separated)
2. **blocked_companies**: Suggested company types or names to block (comma-separated, e.g., outsourcing companies, recruiting agencies)
3. **title_exclusions**: Job title keywords to exclude based on candidate's seniority (comma-separated)
   - If Fresh Graduate or Junior (0-3 years exp): Set 'title_exclusions' to 'Senior, Manager, Director, Lead, Principal, VP, Head, Chief, Staff, Architect'
   - If Mid-level (3-5 years exp): Set 'title_exclusions' to 'Intern, Junior, Entry, Senior Director, VP, C-level, Chief'
   - If Senior (5+ years exp): Set 'title_exclusions' to 'Intern, Junior, Entry Level, Associate, Trainee, Graduate'

**IMPORTANT**: Return ONLY a strict JSON format with no additional text:
{{"keywords": "keyword1, keyword2, keyword3", "blocked_companies": "company1, company2", "title_exclusions": "exclusion1, exclusion2"}}"""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional career advisor who analyzes resumes and generates precise job search parameters. Return only JSON format results."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )

        # 解析 LLM 返回的 JSON
        result_text = response.choices[0].message.content.strip()

        # 尝试提取 JSON（处理可能的 markdown 包裹）
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        # 查找 JSON 对象
        start = result_text.find("{")
        end = result_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            result_text = result_text[start:end+1]

        result = json.loads(result_text)

        # 验证必需字段
        required_fields = ['keywords', 'blocked_companies', 'title_exclusions']
        if not all(field in result for field in required_fields):
            st.error(f"LLM 返回的 JSON 缺少必需字段。返回内容：{result_text}")
            return None

        # 更新 session state
        keywords_list = parse_input_list(result.get('keywords', ''))
        blocked_list = parse_input_list(result.get('blocked_companies', ''))
        exclusions_list = parse_input_list(result.get('title_exclusions', ''))

        state.set_job_keywords(keywords_list)
        state.set_blacklist_companies(blocked_list)
        state.set_title_exclusions(exclusions_list)

        return result

    except json.JSONDecodeError as e:
        st.error(f"JSON 解析失败：{e}\n返回内容：{result_text}")
        return None
    except Exception as e:
        st.error(f"LLM 分析失败：{str(e)}")
        return None


def render_params_section() -> None:
    """渲染参数配置区域"""
    st.markdown("## ⚙️ 参数配置")
    st.markdown("设置求职偏好和过滤条件")

    # LLM 智能分析（放在最前面）
    st.markdown("### 🤖 LLM 智能分析")
    st.caption("使用 AI 分析简历并自动生成所有搜索参数（根据资历自动生成排除词）")

    with st.expander("📝 智能分析简历", expanded=False):
        col1, col2 = st.columns([3, 1])

        with col1:
            resume_text_input = st.text_area(
                "粘贴简历内容",
                height=200,
                placeholder="将简历文本粘贴到这里，AI 将分析并生成推荐参数...",
                help="AI 将根据您的工作经验自动判断资历等级，并生成相应的职位排除词"
            )

        with col2:
            st.markdown("**API 配置**")
            api_key = st.text_input(
                "OpenAI API Key",
                type="password",
                help="输入 OpenAI API Key"
            )

            model_choice = st.selectbox(
                "模型选择",
                ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
                help="选择 LLM 模型"
            )

        if st.button("🚀 分析简历并自动填充参数", type="primary", use_container_width=True):
            if not resume_text_input.strip():
                st.error("❌ 请先粘贴简历内容")
            elif not api_key:
                st.error("❌ 请输入 OpenAI API Key")
            else:
                with st.spinner("🤖 正在分析简历..."):
                    result = analyze_resume_with_llm(resume_text_input, api_key, model_choice)
                    if result:
                        st.success("✅ 分析完成！参数已自动填充到下方输入框")
                        st.json(result)
                        st.info("ℹ️ 请向下滚动查看更新后的参数，或刷新页面")
                        # 触发页面重新加载
                        st.rerun()

    st.markdown("---")

    # 职业关键词
    st.markdown("### 🎯 职业关键词")
    st.caption("输入您感兴趣的职位关键词，用逗号、分号或换行分隔")

    # 获取当前值
    current_keywords = state.get_job_keywords()
    default_keywords = ", ".join(current_keywords) if current_keywords else ""

    keywords_input = st.text_area(
        "职业搜索关键词（留空则根据简历自动生成）",
        value=default_keywords,
        height=100,
        key="keywords_input",
        placeholder="例如：Python开发, 后端工程师, 数据分析师",
        help="可以手动输入多个关键词，用逗号分隔；留空时会自动读取简历为您匹配关键词。"
    )

    # 实时预览
    if keywords_input:
        parsed_keywords = parse_input_list(keywords_input)
        if parsed_keywords:
            st.markdown("**预览：**")
            st.write(parsed_keywords)

    st.markdown("---")

    # 黑名单公司
    st.markdown("### 🚫 黑名单公司")
    st.caption("输入您不想投递的公司名称，用逗号、分号或换行分隔")

    current_blacklist = state.get_blacklist_companies()
    default_blacklist = ", ".join(current_blacklist) if current_blacklist else ""

    blacklist_input = st.text_area(
        "黑名单公司",
        value=default_blacklist,
        height=100,
        key="blacklist_input",
        placeholder="例如：某某科技, XX公司",
        help="系统将自动跳过这些公司的职位"
    )

    # 实时预览
    if blacklist_input:
        parsed_blacklist = parse_input_list(blacklist_input)
        if parsed_blacklist:
            st.markdown("**预览：**")
            st.write(parsed_blacklist)

    st.markdown("---")

    # 职位标题排除词
    st.markdown("### ⊘ 职位标题排除词")
    st.caption("输入您不想申请的职位关键词（如 Senior, Manager, Director 等），用逗号、分号或换行分隔")

    current_title_exclusions = state.get_title_exclusions()
    default_title_exclusions = ", ".join(current_title_exclusions) if current_title_exclusions else ""

    title_exclusions_input = st.text_area(
        "职位标题排除词",
        value=default_title_exclusions,
        height=100,
        key="title_exclusions_input",
        placeholder="例如：Senior, Manager, Director, Lead, Intern",
        help="系统将自动跳过职位标题中包含这些词的职位"
    )

    # 实时预览
    if title_exclusions_input:
        parsed_title_exclusions = parse_input_list(title_exclusions_input)
        if parsed_title_exclusions:
            st.markdown("**预览：**")
            st.write(parsed_title_exclusions)

    st.markdown("---")

    # 保存按钮
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("💾 保存配置", use_container_width=True, type="primary"):
            # 解析并保存
            keywords = parse_input_list(keywords_input)
            blacklist = parse_input_list(blacklist_input)
            title_exclusions = parse_input_list(title_exclusions_input)

            state.set_job_keywords(keywords)
            state.set_blacklist_companies(blacklist)
            state.set_title_exclusions(title_exclusions)

            st.success("✅ 配置已保存！")

            # 显示保存结果
            st.markdown("**已保存的配置：**")
            st.json({
                "职业关键词": keywords,
                "黑名单公司": blacklist,
                "职位标题排除词": title_exclusions
            })

    # 当前配置状态
    st.markdown("---")
    st.markdown("### 📋 当前配置状态")

    config_col1, config_col2, config_col3 = st.columns(3)

    with config_col1:
        saved_keywords = state.get_job_keywords()
        if saved_keywords:
            st.success(f"✅ 已设置 {len(saved_keywords)} 个关键词")
            with st.expander("查看关键词"):
                for kw in saved_keywords:
                    st.write(f"• {kw}")
        else:
            st.warning("⚠️ 未设置职业关键词")

    with config_col2:
        saved_blacklist = state.get_blacklist_companies()
        if saved_blacklist:
            st.info(f"ℹ️ 已设置 {len(saved_blacklist)} 个黑名单公司")
            with st.expander("查看黑名单"):
                for company in saved_blacklist:
                    st.write(f"• {company}")
        else:
            st.info("ℹ️ 未设置黑名单公司")

    with config_col3:
        saved_title_exclusions = state.get_title_exclusions()
        if saved_title_exclusions:
            st.warning(f"⊘ 已设置 {len(saved_title_exclusions)} 个排除词")
            with st.expander("查看排除词"):
                for exclusion in saved_title_exclusions:
                    st.write(f"• {exclusion}")
        else:
            st.info("ℹ️ 未设置排除词")
