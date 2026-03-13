# core/apply/cover_letter_mixin.py
"""Cover letter generation mixin for JobsDBApplyBot."""

import logging

logger = logging.getLogger(__name__)


class CoverLetterMixin:
    """Handles cover letter generation with language detection."""

    def generate_cover_letter(self, candidate_profile: dict, job_info) -> str:
        """
        生成个性化 Cover Letter（支持中英文智能切换）
        """
        if not self.llm_engine:
            logger.warning("LLM engine not provided, using default cover letter")
            return self._generate_default_cover_letter(candidate_profile, job_info)

        job_dict = {
            "title": job_info.title,
            "company": job_info.company,
            "location": job_info.location,
            "jd_text": job_info.jd_text
        }

        # 🔴 新增：智能决定 Cover Letter 语言
        cover_letter_language = "en"
        try:
            from core.resume_language_processor import ResumeLanguageProcessor
            language_processor = ResumeLanguageProcessor(self.llm_engine)

            language_decision = language_processor.decide_cover_letter_language(
                job_description=job_info.jd_text,
                company_name=job_info.company,
                company_profile=None
            )

            cover_letter_language = language_decision.get("language", "en")
            logger.info(f"📝 Cover Letter 语言决策: {cover_letter_language} - {language_decision.get('reason', '')}")

        except Exception as e:
            logger.warning(f"⚠️ Cover Letter 语言决策失败: {e}，使用默认英文")

        try:
            cover_letter = self.llm_engine.generate_cover_letter(
                candidate_profile,
                job_dict,
                language=cover_letter_language
            )
            return cover_letter
        except Exception as e:
            logger.error(f"Failed to generate cover letter: {e}")
            return self._generate_default_cover_letter(candidate_profile, job_info)

    def _generate_default_cover_letter(self, candidate_profile: dict, job_info) -> str:
        """生成默认 Cover Letter"""
        name = candidate_profile.get("name", "")
        if not name or name.lower() in ["candidate", "n/a", "unknown"]:
            try:
                from core.user_identity import get_real_name
                name = get_real_name(self.user_id)
            except Exception:
                name = "Candidate"
        return f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_info.title} position at {job_info.company}.

With my background and experience, I believe I would be a valuable addition to your team. I am excited about the opportunity to contribute to {job_info.company} and would welcome the chance to discuss how my skills align with your needs.

Thank you for considering my application. I look forward to hearing from you.

Best regards,
{name}
"""
