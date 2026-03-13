"""
Backward compatibility shim.
All functionality has been moved to core/llm/ package.
This file re-exports all public symbols so existing imports continue to work.
"""

from core.llm import LLMEngine, load_pdf_text
from core.llm.pre_filter import (
    pre_filter_job,
    EDUCATION_BLACKLIST,
    LANGUAGE_BLACKLIST,
    EXPERIENCE_BLACKLIST,
)

__all__ = [
    "LLMEngine",
    "load_pdf_text",
    "pre_filter_job",
    "EDUCATION_BLACKLIST",
    "LANGUAGE_BLACKLIST",
    "EXPERIENCE_BLACKLIST",
]
