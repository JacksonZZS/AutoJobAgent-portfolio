"""
简历预处理器 - 中英文简历处理与评分
支持中文简历自动提取英文Profile,确保评分准确性
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# 🔴 新的三档评分阈值
AUTO_APPLY_THRESHOLD = 75      # ≥75分: 自动投递
MANUAL_REVIEW_LOWER = 60       # 60-74分: 半自动(人工复核)
REJECT_THRESHOLD = 60          # <60分: 直接跳过

# 向后兼容
SCORE_THRESHOLD = AUTO_APPLY_THRESHOLD


def is_chinese_text(text: str) -> bool:
    """
    检测文本是否包含中文字符

    Args:
        text: 待检测文本

    Returns:
        True 表示包含中文,False 表示不包含
    """
    if not text:
        return False

    # 检查是否包含 CJK 统一表意文字 (U+4E00 到 U+9FFF)
    chinese_char_count = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    total_chars = len(text.strip())

    # 如果中文字符占比超过 10%,认为是中文文本
    if total_chars > 0:
        ratio = chinese_char_count / total_chars
        return ratio > 0.1

    return False


@dataclass
class ResumeProfile:
    """简历Profile数据类"""
    original_text: str
    english_profile: str
    is_chinese: bool
    language: str  # 'zh' or 'en'


class ResumePreprocessor:
    """简历预处理器"""

    def __init__(self, llm_engine):
        """
        初始化预处理器

        Args:
            llm_engine: LLM引擎实例
        """
        self.llm_engine = llm_engine

    def build_english_profile(self, resume_text: str) -> ResumeProfile:
        """
        构建英文Profile

        对于中文简历,使用LLM提取关键信息并生成英文Profile
        对于英文简历,直接返回原文

        Args:
            resume_text: 简历原文

        Returns:
            ResumeProfile对象
        """
        is_chinese = is_chinese_text(resume_text)

        if not is_chinese:
            logger.info("✅ 检测到英文简历,直接使用原文")
            return ResumeProfile(
                original_text=resume_text,
                english_profile=resume_text,
                is_chinese=False,
                language='en'
            )

        logger.info("🔍 检测到中文简历,开始提取英文Profile...")

        try:
            # 使用LLM提取英文Profile
            prompt = """You are a professional CV translator and summarizer.

Given the following Chinese resume content, extract and rewrite a concise English professional profile highlighting:
1. Core technical skills and expertise
2. Industry experience and years
3. Key achievements and projects
4. Education background

Output ONLY the English professional profile, no Chinese characters.
Keep it concise (200-300 words).

Chinese resume:
{resume_text}

English professional profile:"""

            system_prompt = "You are a professional CV translator. Output English only."
            user_prompt = prompt.format(resume_text=resume_text[:4000])  # 限制长度

            # 调用LLM
            english_profile = self.llm_engine._call_ai(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=600
            )

            if not english_profile or len(english_profile.strip()) < 50:
                logger.warning("⚠️ LLM返回的英文Profile过短,使用原文")
                english_profile = resume_text
            else:
                logger.info(f"✅ 成功提取英文Profile (长度: {len(english_profile)} 字符)")

            return ResumeProfile(
                original_text=resume_text,
                english_profile=english_profile,
                is_chinese=True,
                language='zh'
            )

        except Exception as e:
            logger.error(f"❌ 提取英文Profile失败: {e}")
            logger.warning("⚠️ 降级使用原文")
            return ResumeProfile(
                original_text=resume_text,
                english_profile=resume_text,
                is_chinese=True,
                language='zh'
            )

    def score_job_match(
        self,
        resume_profile: ResumeProfile,
        job_description: str,
        job_title: str = "",
        company_name: str = ""
    ) -> dict:
        """
        评估简历与职位的匹配度 (Fresh Graduate 友好型)

        Args:
            resume_profile: 简历Profile对象
            job_description: 职位描述
            job_title: 职位标题
            company_name: 公司名称

        Returns:
            包含score(0-100)、decision、reasoning和dimensions的字典
        """
        try:
            # 使用英文Profile进行评分
            profile_text = resume_profile.english_profile

            # 🔴 Fresh Graduate 友好型评分Prompt
            prompt = f"""你是一个专业的「简历-岗位匹配评分助手」，需要根据候选人简历和岗位 JD 进行 0-100 分的量化打分，并给出自动化决策建议。

【输出要求】
- 严格输出 JSON，不要输出多余文本。
- 字段：
  - overall_score: 整体匹配分，整数 0-100
  - decision: "AUTO_APPLY" | "MANUAL_REVIEW" | "REJECT"
  - reasoning: 简要评分理由(2-3句话)
  - dimensions: 维度打分数组，每个元素包含:
    - name: 维度名称
    - weight: 权重百分比(整数)
    - score: 该维度得分(0-100)
    - comment: 简要说明

【打分维度与权重】
1. 技能/技术栈匹配（40%）
   - 关注 JD 中硬技能、工具、技术栈与简历中对应技能是否匹配
   - 有直接匹配技能要大幅加分
   - 例如: Python, RAG, LLM, Machine Learning 等

2. 项目/实习经历相关性（25%）
   - 与岗位领域/业务相关的项目经历、实习经历
   - 对 Fresh Graduate，项目 + 实习可视为主要经验来源

3. 教育背景与专业匹配度（20%）
   - 学历层次、专业是否与岗位方向匹配

4. 其他加分项（15%）
   - 竞赛、开源、证书、奖项、语言能力等与岗位相关的优势

【Fresh Graduate 友好规则 - 重要】
- 如果候选人为应届/近届毕业生（简历中包含"应届""2024届""2025届"等字样，或工作年限 < 1 年），且该岗位 JD 要求工作经验 ≤ 3 年，则：
  - 经验/项目相关维度中，不因"正式工作年限不足"做重罚
  - 将项目经历、实习经历视作主要经验来源进行正向打分
  - 在这种情况下：
    - 技能/技术栈匹配良好（技能维度 ≥75）且整体略有不足时，整体分数更倾向落在 60-74 分区间，而不是 <60
  - 只有在技能严重不匹配或方向完全不符时，才给出 <60 的低分

【决策规则】
- overall_score ≥ 75 → decision = "AUTO_APPLY" (自动投递)
- 60 ≤ overall_score ≤ 74 → decision = "MANUAL_REVIEW" (人工复核)
- overall_score < 60 → decision = "REJECT" (直接跳过)

【内容】
职位标题: {job_title}
公司: {company_name}

职位描述:
{job_description[:2000]}

候选人简历:
{profile_text[:2000]}

请根据以上规则打分，并仅输出 JSON。"""

            system_prompt = "You are a professional job matching expert. Output valid JSON only."

            result = self.llm_engine._call_ai(
                system_prompt=system_prompt,
                user_prompt=prompt,
                max_tokens=800,
                prefill="{"
            )

            if not result:
                logger.warning("⚠️ LLM返回空结果,使用默认低分")
                return {
                    "score": 0,
                    "overall_score": 0,
                    "decision": "REJECT",
                    "reasoning": "LLM evaluation failed",
                    "dimensions": [],
                    "match_analysis": {}
                }

            # 提取分数和决策
            overall_score = result.get("overall_score", 0)
            decision = result.get("decision", classify_score(overall_score))
            reasoning = result.get("reasoning", "No reasoning provided")
            dimensions = result.get("dimensions", [])

            # 确保分数在0-100范围内
            overall_score = max(0, min(100, int(overall_score)))

            # 验证决策与分数一致性
            expected_decision = classify_score(overall_score)
            if decision != expected_decision:
                logger.warning(f"⚠️ LLM决策({decision})与分数({overall_score})不一致,使用分数决策")
                decision = expected_decision

            logger.info(f"📊 匹配评分: {overall_score}/100 → {decision}")
            logger.debug(f"💡 评分理由: {reasoning}")

            return {
                "score": overall_score,           # 向后兼容
                "overall_score": overall_score,
                "decision": decision,
                "reasoning": reasoning,
                "dimensions": dimensions,
                "match_analysis": result
            }

        except Exception as e:
            logger.error(f"❌ 评分失败: {e}")
            return {
                "score": 0,
                "overall_score": 0,
                "decision": "REJECT",
                "reasoning": f"Scoring failed: {str(e)}",
                "dimensions": [],
                "match_analysis": {}
            }


def create_preprocessor(llm_engine):
    """
    工厂函数:创建预处理器实例

    Args:
        llm_engine: LLM引擎实例

    Returns:
        ResumePreprocessor实例
    """
    return ResumePreprocessor(llm_engine)


# 便捷函数:快速检查是否达到阈值
def classify_score(score: int) -> str:
    """
    根据分数分类决策

    Args:
        score: 匹配分数 (0-100)

    Returns:
        决策类型: "AUTO_APPLY" | "MANUAL_REVIEW" | "REJECT"
    """
    if score >= AUTO_APPLY_THRESHOLD:
        return "AUTO_APPLY"
    elif score >= MANUAL_REVIEW_LOWER:
        return "MANUAL_REVIEW"
    else:
        return "REJECT"


def meets_threshold(score: int) -> bool:
    """
    检查分数是否达到投递阈值(向后兼容)

    Args:
        score: 匹配分数 (0-100)

    Returns:
        True 表示达到阈值,False 表示未达到
    """
    return score >= SCORE_THRESHOLD


def should_auto_apply(score: int) -> bool:
    """检查是否应该自动投递"""
    return score >= AUTO_APPLY_THRESHOLD


def needs_manual_review(score: int) -> bool:
    """检查是否需要人工复核"""
    return MANUAL_REVIEW_LOWER <= score < AUTO_APPLY_THRESHOLD


def should_reject(score: int) -> bool:
    """检查是否应该直接拒绝"""
    return score < REJECT_THRESHOLD
