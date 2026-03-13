# core/apply/__init__.py
"""
Apply bot package.
Re-exports JobsDBApplyBot and models for convenient importing.
"""

from core.apply.pdf_mixin import PDFGenerationMixin
from core.apply.browser_mixin import BrowserManagementMixin
from core.apply.dedup_mixin import DedupMixin
from core.apply.hud_mixin import HUDMixin
from core.apply.auth_mixin import AuthMixin
from core.apply.cover_letter_mixin import CoverLetterMixin
from core.models import ApplyStatus, ApplyJobInfo, ApplyResult

__all__ = [
    "PDFGenerationMixin",
    "BrowserManagementMixin",
    "DedupMixin",
    "HUDMixin",
    "AuthMixin",
    "CoverLetterMixin",
    "ApplyStatus",
    "ApplyJobInfo",
    "ApplyResult",
]
