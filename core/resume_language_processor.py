"""
多语言简历处理工具 - 语言检测、翻译、智能决策
"""

import logging
from typing import Dict, Optional, Tuple
from core.llm_engine import LLMEngine

logger = logging.getLogger(__name__)


class ResumeLanguageProcessor:
    """简历语言处理器 - 检测、翻译、智能决策"""

    def __init__(self, llm_engine: Optional[LLMEngine] = None):
        """
        初始化语言处理器

        Args:
            llm_engine: LLM 引擎实例，如果为 None 则创建新实例
        """
        self.llm_engine = llm_engine or LLMEngine()

    def detect_language(self, text: str, max_chars: int = 3000) -> Dict:
        """
        检测文本的主要语言

        Args:
            text: 待检测的文本
            max_chars: 最大检测字符数（避免超长文本）

        Returns:
            {
                "language": "zh_cn" | "zh_tw" | "en" | "mixed",
                "confidence": 0.0-1.0,
                "reason": "判断依据"
            }
        """
        # 截断文本
        text_sample = text[:max_chars] if len(text) > max_chars else text

        system_prompt = """你是一名语言检测助手。
给定一段简历文本，你需要判断其「主要语言」，在以下集合中选择：
- `zh_cn`：简体中文
- `zh_tw`：繁体中文
- `en`：英文
- `mixed`：中英混合且无法判断哪种明显占主导

要求：
- 忽略个人姓名、邮箱、URL、项目名等少量英文或中文噪音。
- 根据整篇文本占比和句子结构判断主要语言。
- 输出格式必须是 JSON：
{
  "language": "zh_cn | zh_tw | en | mixed",
  "confidence": 0.0-1.0,
  "reason": "简要说明判断依据，50字以内"
}"""

        user_prompt = f"""下面是一份简历的文本内容，请根据要求判断主要语言：

```text
{text_sample}
```"""

        try:
            result = self.llm_engine._call_ai(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=500,
                prefill="{"
            )

            if result:
                logger.info(f"语言检测成功: {result.get('language')} (置信度: {result.get('confidence')})")
                return result
            else:
                logger.warning("语言检测失败，返回默认值")
                return {
                    "language": "unknown",
                    "confidence": 0.0,
                    "reason": "LLM 返回无效响应"
                }

        except Exception as e:
            logger.error(f"语言检测异常: {e}")
            return {
                "language": "unknown",
                "confidence": 0.0,
                "reason": f"检测失败: {str(e)}"
            }

    def translate_to_english_summary(self, text: str, language: str) -> Dict:
        """
        将中文简历翻译为英文概要

        Args:
            text: 简历原文
            language: 检测到的语言代码

        Returns:
            {
                "english_summary": "英文简介",
                "skill_keywords": "keyword1, keyword2, ...",
                "translation_needed": True/False
            }
        """
        # 如果已经是英文，生成结构化摘要
        if language == "en":
            return self._generate_english_summary(text)

        # 中文简历需要翻译
        system_prompt = """你是一名资深技术招聘顾问，擅长将中文简历转写为专业英文摘要。
任务：
1. 阅读候选人中文简历（可能包含少量英文）。
2. 用专业英文写出一段到两段的简洁个人简介，突出：
   - 核心技术栈与技能
   - 最近 3–5 年的关键项目或工作经验
   - 领域经验（如金融、电商、AI）
3. 输出中保留公司名、项目名、技术名等专有名词，不要随意改写。
4. 不要编造简历中不存在的经历或技能。
5. 额外列出一个英文的 skill keywords 列表，用逗号分隔。

输出格式必须是 JSON：
{
  "english_summary": "一到两段英文简介",
  "skill_keywords": "keyword1, keyword2, ..."
}"""

        user_prompt = f"""将下面的中文简历内容转写为英文简介，并输出 JSON：

```text
{text[:4000]}
```"""

        try:
            result = self.llm_engine._call_ai(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2000,
                prefill="{"
            )

            if result:
                result["translation_needed"] = True
                logger.info("简历翻译成功")
                return result
            else:
                logger.warning("简历翻译失败")
                return {
                    "english_summary": "",
                    "skill_keywords": "",
                    "translation_needed": True
                }

        except Exception as e:
            logger.error(f"简历翻译异常: {e}")
            return {
                "english_summary": "",
                "skill_keywords": "",
                "translation_needed": True
            }

    def _generate_english_summary(self, text: str) -> Dict:
        """
        为英文简历生成结构化摘要

        Args:
            text: 英文简历原文

        Returns:
            结构化摘要字典
        """
        system_prompt = """You are a professional resume analyst.
Extract and summarize the key information from the English resume:
1. Write a concise 1-2 paragraph professional summary
2. Highlight core technical skills and expertise
3. Mention recent work experience and key projects
4. Extract skill keywords

Output format must be JSON:
{
  "english_summary": "1-2 paragraph summary",
  "skill_keywords": "keyword1, keyword2, ..."
}"""

        user_prompt = f"""Analyze and summarize the following English resume:

```text
{text[:4000]}
```"""

        try:
            result = self.llm_engine._call_ai(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2000,
                prefill="{"
            )

            if result:
                result["translation_needed"] = False
                logger.info("英文简历摘要生成成功")
                return result
            else:
                return {
                    "english_summary": text[:500],  # 使用原文前500字符作为备选
                    "skill_keywords": "",
                    "translation_needed": False
                }

        except Exception as e:
            logger.error(f"英文摘要生成异常: {e}")
            return {
                "english_summary": text[:500],
                "skill_keywords": "",
                "translation_needed": False
            }

    def decide_cover_letter_language(
        self,
        job_description: str,
        company_name: str,
        company_profile: Optional[str] = None
    ) -> Dict:
        """
        决定 Cover Letter 应使用的语言

        Args:
            job_description: 职位描述
            company_name: 公司名称
            company_profile: 公司简介（可选）

        Returns:
            {
                "language": "en" | "zh_cn",
                "reason": "决策理由"
            }
        """
        system_prompt = """你是一名职业顾问，负责判断 Cover Letter 应该使用中文还是英文。
你会得到：
- 岗位描述文本
- 公司名称和公司简介（如果有）

请根据以下原则决定 Cover Letter 的语言：
1. 默认使用英文。
2. 如果岗位描述主要语言是中文，且公司是中国公司或主要面向中文市场，则使用中文。
3. 如果岗位描述主要语言是英文或是跨国公司，优先使用英文。
4. 如果信息不足，则选择英文。

输出 JSON 格式：
{
  "language": "en" | "zh_cn",
  "reason": "简要说明理由，30字以内"
}
只输出 JSON，不要多余文本。"""

        company_info = f"公司简介：\n{company_profile}" if company_profile else "公司简介：无"

        user_prompt = f"""请根据下面的信息判断 Cover Letter 使用中文还是英文：

公司名称：{company_name}
{company_info}

岗位描述：
```text
{job_description[:2000]}
```"""

        try:
            result = self.llm_engine._call_ai(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=300,
                prefill="{"
            )

            if result:
                logger.info(f"Cover Letter 语言决策: {result.get('language')} - {result.get('reason')}")
                return result
            else:
                # 默认英文
                return {
                    "language": "en",
                    "reason": "LLM 响应无效，使用默认英文"
                }

        except Exception as e:
            logger.error(f"Cover Letter 语言决策异常: {e}")
            return {
                "language": "en",
                "reason": f"决策失败，使用默认英文: {str(e)}"
            }

    def process_resume(self, resume_text: str) -> Dict:
        """
        完整处理简历：检测语言 + 翻译/摘要

        Args:
            resume_text: 简历原文

        Returns:
            {
                "resume_original_text": "原文",
                "resume_language": "语言代码",
                "language_confidence": 置信度,
                "resume_en_summary": "英文摘要",
                "skill_keywords": "技能关键词",
                "translation_meta": {...}
            }
        """
        logger.info("开始处理简历：语言检测 + 翻译/摘要")

        # 1. 语言检测
        lang_result = self.detect_language(resume_text)

        # 2. 翻译/摘要
        translation_result = self.translate_to_english_summary(
            resume_text,
            lang_result.get("language", "unknown")
        )

        # 3. 组装结果
        processed_data = {
            "resume_original_text": resume_text,
            "resume_language": lang_result.get("language", "unknown"),
            "language_confidence": lang_result.get("confidence", 0.0),
            "language_detection_reason": lang_result.get("reason", ""),
            "resume_en_summary": translation_result.get("english_summary", ""),
            "skill_keywords": translation_result.get("skill_keywords", ""),
            "translation_needed": translation_result.get("translation_needed", False),
            "translation_meta": {
                "model": self.llm_engine.model,
                "language_detected": lang_result.get("language"),
                "confidence": lang_result.get("confidence")
            }
        }

        logger.info(f"简历处理完成: 语言={processed_data['resume_language']}, "
                   f"置信度={processed_data['language_confidence']:.2f}")

        return processed_data
