# core/llm/pre_filter.py
"""
硬性要求预过滤（节省 Token，快速跳过不符合的职位）
"""

import logging

logger = logging.getLogger(__name__)

# 学历黑名单 - 本科生无法满足的学历要求
EDUCATION_BLACKLIST = [
    # PhD 要求
    "phd required", "phd program", "doctoral", "ph.d. required",
    "currently enrolled in a phd", "pursuing a phd",
    "博士", "博士学历", "博士在读",
    # Master 要求（硬性）
    "master's degree required", "master's required", "ms required",
    "msc required", "mba required", "master degree required",
    "硕士及以上", "硕士学历要求", "研究生学历",
]

# 语言黑名单 - 你不会的语言（英语、普通话、粤语除外）
LANGUAGE_BLACKLIST = [
    # 日语
    "japanese required", "japanese native", "japanese speaker required",
    "fluent in japanese", "jlpt n1", "jlpt n2", "日本語必須", "日语流利",
    "native japanese", "business level japanese",
    # 韩语
    "korean required", "korean native", "korean speaker required",
    "fluent in korean", "topik", "한국어", "韩语流利",
    # 欧洲语言
    "german required", "french required", "spanish required",
    "italian required", "portuguese required", "dutch required",
    "fluent in german", "fluent in french", "fluent in spanish",
    "native german", "native french", "native spanish",
    "德语流利", "法语流利", "西班牙语流利",
    # 其他亚洲语言
    "thai required", "vietnamese required", "indonesian required",
    "malay required", "hindi required", "tagalog required",
    "泰语", "越南语", "印尼语", "马来语",
]

# 经验年限黑名单 - 应届生/Junior 无法满足的经验要求
EXPERIENCE_BLACKLIST = [
    # 3年以上
    "3+ years", "3-5 years", "3 to 5 years", "3 years of experience",
    "three years", "at least 3 years", "minimum 3 years",
    "3年以上", "三年以上", "3年经验",
    # 5年以上
    "5+ years", "5-7 years", "5 to 7 years", "5 years of experience",
    "five years", "at least 5 years", "minimum 5 years",
    "5年以上", "五年以上", "5年经验",
    # 7年以上
    "7+ years", "7-10 years", "7 years of experience",
    "seven years", "at least 7 years",
    "7年以上", "七年以上",
    # 10年以上
    "10+ years", "10 years of experience", "ten years",
    "10年以上", "十年以上",
    # Senior/Lead 级别（通常需要多年经验）
    "senior level", "lead level", "principal level",
    "senior engineer", "lead engineer", "staff engineer",
    "senior analyst", "lead analyst",
    "senior developer", "lead developer",
]


def pre_filter_job(jd_text: str) -> dict:
    """
    硬性要求预过滤 - 在调用 LLM 之前快速过滤不符合的职位

    Args:
        jd_text: 职位描述文本

    Returns:
        {
            "pass": True/False,  # 是否通过预过滤
            "reason": str,       # 过滤原因（如果未通过）
            "filter_type": str   # 过滤类型：education/language/None
        }
    """
    if not jd_text:
        return {"pass": True, "reason": None, "filter_type": None}

    jd_lower = jd_text.lower()

    # 1. 学历过滤
    for keyword in EDUCATION_BLACKLIST:
        if keyword.lower() in jd_lower:
            reason = f"学历要求不符：JD 包含 '{keyword}'"
            logger.info(f"🚫 预过滤拦截: {reason}")
            return {
                "pass": False,
                "reason": reason,
                "filter_type": "education"
            }

    # 2. 语言过滤
    for keyword in LANGUAGE_BLACKLIST:
        if keyword.lower() in jd_lower:
            reason = f"语言要求不符：JD 包含 '{keyword}'"
            logger.info(f"🚫 预过滤拦截: {reason}")
            return {
                "pass": False,
                "reason": reason,
                "filter_type": "language"
            }

    # 3. 经验年限过滤
    for keyword in EXPERIENCE_BLACKLIST:
        if keyword.lower() in jd_lower:
            reason = f"经验要求不符：JD 包含 '{keyword}'（应届生不符合）"
            logger.info(f"🚫 预过滤拦截: {reason}")
            return {
                "pass": False,
                "reason": reason,
                "filter_type": "experience"
            }

    return {"pass": True, "reason": None, "filter_type": None}
