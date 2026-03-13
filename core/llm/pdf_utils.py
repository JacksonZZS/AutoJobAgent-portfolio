# core/llm/pdf_utils.py
"""PDF text extraction utilities."""

import os
import logging
import pdfplumber

logger = logging.getLogger(__name__)


def load_pdf_text(pdf_path: str) -> str:
    """
    读取PDF文件并提取文本内容

    Args:
        pdf_path: PDF文件路径

    Returns:
        提取的文本内容
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as e:
        raise RuntimeError(f"读取PDF文件失败: {e}")

    return "\n".join(text_parts)
