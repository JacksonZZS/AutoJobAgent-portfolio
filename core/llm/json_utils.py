# core/llm/json_utils.py
"""JSON cleaning and parsing utilities for LLM responses."""

import json
import re
import ast
import logging

# Try to import json_repair for robust JSON parsing
try:
    import json_repair
    HAS_JSON_REPAIR = True
except ImportError:
    HAS_JSON_REPAIR = False

logger = logging.getLogger(__name__)


def clean_json_string(text):
    """
    高级 JSON 字符串清洗方法
    处理常见的 JSON 格式问题：
    1. 移除 Markdown 代码块标记
    2. 修复双花括号问题
    3. 移除末尾多余逗号
    4. 处理未转义的特殊字符
    5. 提取最外层的 JSON 对象
    """
    try:
        # 1. 移除 Markdown 代码块标记 (```json 和 ```)
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        # 2. 修复双花括号问题（prefill 导致的）
        if text.startswith('{{'):
            text = text[1:]

        # 3. 寻找最外层的花括号 {}
        start = text.find('{')
        end = text.rfind('}')

        if start != -1 and end != -1:
            json_str = text[start : end + 1]

            # 再次检查双花括号
            if json_str.startswith('{{'):
                json_str = json_str[1:]

            # 4. 移除对象末尾的多余逗号 (例如: {"key": "value",})
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)

            return json_str

        return text.strip()
    except Exception as e:
        logger.warning(f"JSON 清洗过程出错: {e}")
        return text


def parse_json_response(text, retry_with_repair=True):
    """
    增强的 JSON 解析方法

    Args:
        text: 待解析的文本
        retry_with_repair: 是否在失败时尝试使用 json_repair

    Returns:
        解析后的 JSON 对象，失败返回 None
    """
    # 第一步：清洗 JSON 字符串
    cleaned_text = clean_json_string(text)

    if not cleaned_text or not cleaned_text.startswith('{'):
        logger.warning(f"清洗后的文本不是有效的 JSON 格式 (前100字符): {text[:100]}")
        return None

    # 第二步：尝试标准 JSON 解析
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logger.warning(f"标准 JSON 解析失败: {e}")
        logger.debug(f"失败的 JSON 片段: {cleaned_text[:200]}...")

        # 第三步：如果有 json_repair 库，尝试使用它修复
        if retry_with_repair and HAS_JSON_REPAIR:
            try:
                logger.info("尝试使用 json_repair 修复 JSON...")
                repaired_data = json_repair.loads(cleaned_text)
                logger.info("✅ json_repair 成功修复 JSON")
                return repaired_data
            except Exception as repair_error:
                logger.warning(f"json_repair 也无法修复: {repair_error}")

        # 第四步：尝试使用 ast.literal_eval 作为最后的备选方案
        try:
            logger.info("尝试使用 ast.literal_eval 解析...")
            python_text = cleaned_text.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            result = ast.literal_eval(python_text)
            logger.info("✅ ast.literal_eval 成功解析")
            return result
        except Exception as ast_error:
            logger.warning(f"ast.literal_eval 也无法解析: {ast_error}")

        return None
