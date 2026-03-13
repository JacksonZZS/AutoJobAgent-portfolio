# tests/test_backward_compat.py
"""
Backward compatibility tests.
Ensures all existing import paths continue to work after refactoring.
"""
import pytest


class TestApplyBotImports:
    """Verify apply_bot.py shim re-exports work."""

    def test_import_jobsdb_apply_bot(self):
        from core.apply_bot import JobsDBApplyBot
        assert JobsDBApplyBot is not None

    def test_import_apply_status(self):
        from core.apply_bot import ApplyStatus
        assert hasattr(ApplyStatus, "SUCCESS")
        assert hasattr(ApplyStatus, "FAILED")
        assert hasattr(ApplyStatus, "SKIPPED")

    def test_import_apply_job_info(self):
        from core.apply_bot import ApplyJobInfo
        info = ApplyJobInfo(
            job_id="123", title="Dev", company="Co",
            location="HK", job_url="https://example.com"
        )
        assert info.job_id == "123"

    def test_import_apply_result(self):
        from core.apply_bot import ApplyResult
        assert ApplyResult is not None

    def test_models_direct_import(self):
        from core.models import ApplyStatus, ApplyJobInfo, ApplyResult
        assert ApplyStatus.SUCCESS.value == "success"


class TestLLMEngineImports:
    """Verify llm_engine.py shim re-exports work."""

    def test_shim_import_llm_engine(self):
        from core.llm_engine import LLMEngine
        assert LLMEngine is not None

    def test_shim_import_load_pdf_text(self):
        from core.llm_engine import load_pdf_text
        assert callable(load_pdf_text)

    def test_shim_import_pre_filter_job(self):
        from core.llm_engine import pre_filter_job
        assert callable(pre_filter_job)

    def test_shim_import_blacklists(self):
        from core.llm_engine import EDUCATION_BLACKLIST, LANGUAGE_BLACKLIST, EXPERIENCE_BLACKLIST
        assert len(EDUCATION_BLACKLIST) > 0
        assert len(LANGUAGE_BLACKLIST) > 0
        assert len(EXPERIENCE_BLACKLIST) > 0


class TestNewPackageImports:
    """Verify new package imports work."""

    def test_llm_package_import(self):
        from core.llm import LLMEngine, load_pdf_text
        assert LLMEngine is not None
        assert callable(load_pdf_text)

    def test_llm_pre_filter_import(self):
        from core.llm.pre_filter import pre_filter_job
        assert callable(pre_filter_job)

    def test_llm_json_utils_import(self):
        from core.llm.json_utils import clean_json_string, parse_json_response
        assert callable(clean_json_string)
        assert callable(parse_json_response)

    def test_llm_pdf_utils_import(self):
        from core.llm.pdf_utils import load_pdf_text
        assert callable(load_pdf_text)

    def test_apply_mixins_import(self):
        from core.apply.pdf_mixin import PDFGenerationMixin
        from core.apply.browser_mixin import BrowserManagementMixin
        from core.apply.dedup_mixin import DedupMixin
        from core.apply.hud_mixin import HUDMixin
        from core.apply.auth_mixin import AuthMixin
        from core.apply.cover_letter_mixin import CoverLetterMixin
        assert PDFGenerationMixin is not None
        assert BrowserManagementMixin is not None


class TestPrivateMethodsAccessible:
    """Verify private methods from Mixins are accessible on JobsDBApplyBot."""

    def test_pdf_methods(self):
        from core.apply_bot import JobsDBApplyBot
        assert hasattr(JobsDBApplyBot, '_generate_custom_resume_pdf')
        assert hasattr(JobsDBApplyBot, '_generate_cover_letter_pdf')
        assert hasattr(JobsDBApplyBot, '_generate_pdf_from_html')
        assert hasattr(JobsDBApplyBot, '_get_file_as_data_uri')

    def test_browser_methods(self):
        from core.apply_bot import JobsDBApplyBot
        assert hasattr(JobsDBApplyBot, 'start')
        assert hasattr(JobsDBApplyBot, 'close')
        assert hasattr(JobsDBApplyBot, '_is_browser_ready')
        assert hasattr(JobsDBApplyBot, '_cleanup_singleton_lock')

    def test_dedup_methods(self):
        from core.apply_bot import JobsDBApplyBot
        assert hasattr(JobsDBApplyBot, '_load_job_history')
        assert hasattr(JobsDBApplyBot, '_is_job_processed')
        assert hasattr(JobsDBApplyBot, '_mark_job_processed')
        assert hasattr(JobsDBApplyBot, '_extract_job_id')
        assert hasattr(JobsDBApplyBot, '_generate_job_key')

    def test_hud_methods(self):
        from core.apply_bot import JobsDBApplyBot
        assert hasattr(JobsDBApplyBot, '_update_hud')
        assert hasattr(JobsDBApplyBot, '_check_captcha')
        assert hasattr(JobsDBApplyBot, '_wait_for_captcha_resolution')

    def test_auth_methods(self):
        from core.apply_bot import JobsDBApplyBot
        assert hasattr(JobsDBApplyBot, '_is_logged_in')
        assert hasattr(JobsDBApplyBot, 'ensure_logged_in')

    def test_cover_letter_methods(self):
        from core.apply_bot import JobsDBApplyBot
        assert hasattr(JobsDBApplyBot, 'generate_cover_letter')
        assert hasattr(JobsDBApplyBot, '_generate_default_cover_letter')

    def test_core_methods_still_present(self):
        from core.apply_bot import JobsDBApplyBot
        assert hasattr(JobsDBApplyBot, 'apply_to_job')
        assert hasattr(JobsDBApplyBot, 'auto_apply_for_jobs')
        assert hasattr(JobsDBApplyBot, 'stream_apply_with_target')

    def test_mro_includes_all_mixins(self):
        from core.apply_bot import JobsDBApplyBot
        mro_names = [c.__name__ for c in JobsDBApplyBot.__mro__]
        assert 'PDFGenerationMixin' in mro_names
        assert 'BrowserManagementMixin' in mro_names
        assert 'DedupMixin' in mro_names
        assert 'HUDMixin' in mro_names
        assert 'AuthMixin' in mro_names
        assert 'CoverLetterMixin' in mro_names
