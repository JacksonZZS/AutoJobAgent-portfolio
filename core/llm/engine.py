# core/llm/engine.py
"""
LLMEngine - Core AI interaction engine.
Handles all LLM API calls for resume analysis, job matching, and content generation.
"""

import os
import json
import re
import logging
import time
from difflib import SequenceMatcher
from google import genai
from dotenv import load_dotenv
from datetime import datetime

from core.llm.json_utils import clean_json_string, parse_json_response
from core.llm.pre_filter import pre_filter_job
from core.llm.prompts import RESUME_EXTRACTION_PROMPT

load_dotenv()

logger = logging.getLogger(__name__)


class LLMEngine:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError("❌ MISSING_API_KEY: Please check your .env file for GOOGLE_API_KEY.")

        # 使用官方 Google GenAI 客户端
        self.client = genai.Client(api_key=api_key)
        
        # 默认使用稳定的 gemini-3-flash-preview 确保恢复成功
        self.model = os.getenv("LLM_MODEL") or "gemini-3-flash-preview"
        logger.info(f"🚀 LLMEngine initialized with model: {self.model}")

    def _clean_json_string(self, text):
        """Delegate to module-level function for backward compatibility."""
        return clean_json_string(text)

    def _parse_json_response(self, text, retry_with_repair=True):
        """Delegate to module-level function for backward compatibility."""
        return parse_json_response(text, retry_with_repair=retry_with_repair)

    def _extract_contact_details(self, resume_text: str) -> dict:
        """Extract common contact fields from raw resume text as a fallback."""
        text = resume_text or ""

        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)

        linkedin_match = re.search(r'(https?://[^\s]*linkedin\.com/[^\s|,;]+)', text, re.IGNORECASE)
        github_match = re.search(r'(https?://[^\s]*github\.com/[^\s|,;]+)', text, re.IGNORECASE)
        portfolio_match = re.search(
            r'(https?://[^\s]+)',
            text,
            re.IGNORECASE,
        )

        phone_match = re.search(
            r'(\+?\d[\d\s\-\(\)]{7,}\d)',
            text
        )

        portfolio_url = ""
        if portfolio_match:
            candidate = portfolio_match.group(1)
            if "linkedin.com" not in candidate.lower() and "github.com" not in candidate.lower():
                portfolio_url = candidate

        return {
            "email": email_match.group(0) if email_match else "",
            "phone": phone_match.group(1).strip() if phone_match else "",
            "linkedin": linkedin_match.group(1) if linkedin_match else "",
            "github": github_match.group(1) if github_match else "",
            "portfolio": portfolio_url,
        }

    def _is_valid_url(self, value: str) -> bool:
        """Return True only for plausible http(s) URLs."""
        if not value or not isinstance(value, str):
            return False
        candidate = value.strip()
        return bool(re.match(r"^https?://[^\s/$.?#].[^\s]*$", candidate, re.IGNORECASE))

    def _normalize_text_key(self, value: str) -> str:
        """Normalize user-visible text for fuzzy matching."""
        if not value:
            return ""
        normalized = re.sub(r"[^a-z0-9]+", "", value.lower())
        return normalized

    def _should_skip_fallback_item(self, name: str, edit_instructions: list[dict]) -> bool:
        """Honor explicit delete/modify instructions when restoring missing items."""
        normalized_name = self._normalize_text_key(name)
        for instruction in edit_instructions:
            if instruction.get("action") not in {"delete", "modify"}:
                continue
            target = self._normalize_text_key(str(instruction.get("target", "")))
            if target and (target in normalized_name or normalized_name in target):
                return True
        return False

    def _merge_missing_projects(
        self,
        candidate_projects: list[dict],
        extracted_projects: list[dict],
        edit_instructions: list[dict],
    ) -> list[dict]:
        """Append missing original projects without overwriting AI modifications/additions."""
        merged = list(candidate_projects or [])
        existing_names = {
            self._normalize_text_key(project.get("name", ""))
            for project in merged
            if isinstance(project, dict)
        }

        for project in extracted_projects:
            name = project.get("name", "")
            normalized = self._normalize_text_key(name)
            if not normalized or normalized in existing_names:
                continue
            if self._should_skip_fallback_item(name, edit_instructions):
                continue
            merged.append(project)
            existing_names.add(normalized)

        return merged

    def _project_similarity(self, left: dict, right: dict) -> float:
        """Estimate whether two project entries refer to the same project."""
        left_name = self._normalize_text_key(left.get("name", ""))
        right_name = self._normalize_text_key(right.get("name", ""))
        name_score = SequenceMatcher(None, left_name, right_name).ratio() if left_name and right_name else 0.0

        left_date = self._normalize_text_key(left.get("date", ""))
        right_date = self._normalize_text_key(right.get("date", ""))
        same_date = bool(left_date and right_date and left_date == right_date)

        left_bullets = " ".join(left.get("bullets", []) or [])
        right_bullets = " ".join(right.get("bullets", []) or [])
        left_tokens = {
            token for token in re.findall(r"[A-Za-z]{3,}", left_bullets.lower())
            if token not in {"with", "from", "that", "this", "using", "built", "developed", "designed"}
        }
        right_tokens = {
            token for token in re.findall(r"[A-Za-z]{3,}", right_bullets.lower())
            if token not in {"with", "from", "that", "this", "using", "built", "developed", "designed"}
        }
        overlap = len(left_tokens & right_tokens)

        if name_score >= 0.82:
            return 1.0
        if name_score >= 0.68 and same_date:
            return 0.95
        if name_score >= 0.6 and overlap >= 3:
            return 0.9
        if same_date and overlap >= 5:
            return 0.85
        return max(name_score, 0.0)

    def _is_truncated_bullet(self, bullet: str) -> bool:
        """Detect obviously truncated bullet text from broken extraction/JSON repair."""
        if not bullet:
            return True
        text = bullet.strip()
        if len(text) < 12:
            return True
        if re.search(r'\b(and|with|for|to|of|in|via|using)\s+[a-zA-Z]$', text):
            return True
        if re.search(r'\b[a-zA-Z]$', text) and len(text.split()[-1]) == 1:
            return True
        if text.endswith((" and", " with", " for", " to", " of", " in", " via", " using")):
            return True
        return False

    def _clean_project_bullets(self, bullets: list[str]) -> list[str]:
        """Drop duplicates and obviously truncated bullet lines."""
        cleaned: list[str] = []
        seen: set[str] = set()
        for bullet in bullets or []:
            if not isinstance(bullet, str):
                continue
            value = bullet.strip()
            if not value or self._is_truncated_bullet(value):
                continue
            key = self._normalize_text_key(value)
            if key and key not in seen:
                cleaned.append(value)
                seen.add(key)
        return cleaned

    def _dedupe_and_merge_projects(self, projects: list[dict]) -> list[dict]:
        """Merge duplicate project variants while preserving richer AI edits."""
        merged: list[dict] = []
        for project in projects or []:
            if not isinstance(project, dict):
                continue

            project_copy = {
                "name": project.get("name", ""),
                "date": project.get("date", ""),
                "bullets": self._clean_project_bullets(project.get("bullets", []) or []),
            }
            matched_index = None
            for index, existing in enumerate(merged):
                if self._project_similarity(existing, project_copy) >= 0.85:
                    matched_index = index
                    break

            if matched_index is None:
                merged.append(project_copy)
                continue

            existing = merged[matched_index]
            if len(project_copy.get("name", "")) > len(existing.get("name", "")):
                existing["name"] = project_copy["name"]
            if len(project_copy.get("date", "")) > len(existing.get("date", "")):
                existing["date"] = project_copy["date"]
            existing["bullets"] = self._clean_project_bullets(
                (existing.get("bullets", []) or []) + (project_copy.get("bullets", []) or [])
            )

        return merged

    def _apply_project_edit_instruction_hints(self, projects: list[dict], edit_instructions: list[dict]) -> list[dict]:
        """Ensure project-scoped add/modify instructions are still reflected after fallback merges."""
        for instruction in edit_instructions:
            action = instruction.get("action")
            if action not in {"add", "modify"}:
                continue
            target = str(instruction.get("target", ""))
            content = str(instruction.get("content", "")).strip()
            if not target or not content:
                continue

            normalized_target = self._normalize_text_key(target)
            applied = False
            for project in projects:
                name_key = self._normalize_text_key(project.get("name", ""))
                if not name_key:
                    continue
                if normalized_target in name_key or name_key in normalized_target:
                    if action == "modify":
                        project["bullets"] = [content]
                    else:
                        combined = " ".join([project.get("name", "")] + (project.get("bullets", []) or []))
                        if self._normalize_text_key(content) not in self._normalize_text_key(combined):
                            project.setdefault("bullets", []).append(content)
                    applied = True

            if not applied and action == "add":
                projects.append({
                    "name": target,
                    "date": "",
                    "bullets": [content],
                })

        for project in projects:
            project["bullets"] = self._clean_project_bullets(project.get("bullets", []) or [])
        return projects

    def _parse_project_from_instruction(self, target: str, content: str) -> dict:
        """Parse a project-like block from edit instruction content."""
        lines = [line.strip() for line in (content or "").splitlines() if line.strip()]
        text = (content or "").strip()

        name = target.strip()
        date = ""
        bullets: list[str] = []

        if lines:
            header = lines[0]
            header_date_match = re.search(
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)\d{2}\s*[–-]\s*(?:Present|Current|Now|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)\d{2}|(?:19|20)\d{2}))|((?:19|20)\d{2}\s*[–-]\s*(?:Present|Current|Now|(?:19|20)\d{2}))',
                header,
                re.IGNORECASE,
            )
            if header_date_match:
                date = header_date_match.group(0)
                possible_name = header.replace(date, "").strip(" |-–")
                if possible_name:
                    name = possible_name
                lines = lines[1:]
            elif len(lines) > 1 and not lines[0].startswith(("-", "•")):
                possible_name = header.strip(" |-–")
                if len(possible_name.split()) <= 12:
                    name = possible_name
                    lines = lines[1:]

        if lines:
            for line in lines:
                bullet = re.sub(r'^[\-\u2022•]\s*', '', line).strip()
                if bullet:
                    bullets.append(bullet)
        elif text:
            sentence_bullets = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', text)
            bullets = [bullet.strip(" -") for bullet in sentence_bullets if bullet.strip()]

        if not bullets and text:
            bullets = [text]

        return {
            "name": name,
            "date": date,
            "bullets": self._clean_project_bullets(bullets),
        }

    def _apply_deterministic_project_edits(self, projects: list[dict], edit_instructions: list[dict]) -> list[dict]:
        """Apply project add/modify instructions deterministically after AI generation."""
        result = list(projects or [])

        for instruction in edit_instructions:
            action = instruction.get("action")
            if action not in {"add", "modify"}:
                continue

            target = str(instruction.get("target", "")).strip()
            content = str(instruction.get("content", "")).strip()
            if not target or not content:
                continue

            replacement = self._parse_project_from_instruction(target, content)
            normalized_target = self._normalize_text_key(target)

            matched_index = None
            best_score = 0.0
            for index, project in enumerate(result):
                project_name = str(project.get("name", "")).strip()
                project_key = self._normalize_text_key(project_name)
                if not project_key:
                    continue
                score = SequenceMatcher(None, normalized_target, project_key).ratio()
                if normalized_target in project_key or project_key in normalized_target:
                    score = max(score, 0.95)
                if score > best_score:
                    best_score = score
                    matched_index = index

            if action == "modify":
                if matched_index is not None and best_score >= 0.55:
                    result[matched_index] = replacement
                else:
                    result.append(replacement)
            elif action == "add":
                if matched_index is None or best_score < 0.55:
                    result.append(replacement)

        return self._dedupe_and_merge_projects(result)

    def _merge_missing_skills(self, candidate_skills: list[dict], extracted_skills: list[dict]) -> list[dict]:
        """Preserve AI-generated skills and append raw-skill categories that disappeared."""
        merged = list(candidate_skills or [])
        existing_categories = {
            self._normalize_text_key(skill.get("name", ""))
            for skill in merged
            if isinstance(skill, dict)
        }

        for skill in extracted_skills:
            category = self._normalize_text_key(skill.get("name", ""))
            if not category or category in existing_categories:
                continue
            merged.append(skill)
            existing_categories.add(category)

        return merged

    def _validate_resume_result(self, result: dict, allow_missing_projects: bool = False) -> tuple[bool, str]:
        """Reject truncated LLM outputs before PDF generation."""
        experience = result.get("experience", [])
        projects = result.get("projects", [])
        education = result.get("education")

        exp_count = len(experience) if isinstance(experience, list) else 0
        proj_count = len(projects) if isinstance(projects, list) else 0
        has_education = bool(education)

        if not has_education:
            return False, "missing education"
        if exp_count == 0 and proj_count == 0:
            return False, "missing both experience and projects"
        if not allow_missing_projects and exp_count == 0:
            return False, "missing experience"
        return True, "ok"

    def _extract_section_lines(self, resume_text: str, headings: list[str]) -> list[str]:
        """Extract lines under a named resume section."""
        lines = [line.strip() for line in (resume_text or "").splitlines()]
        normalized_headings = {heading.lower() for heading in headings}
        common_stops = {
            "professional summary",
            "summary",
            "work experience",
            "experience",
            "projects",
            "skills",
            "languages",
            "certifications",
            "additional information",
        }

        in_section = False
        captured: list[str] = []
        for line in lines:
            clean = re.sub(r"[:\-\s]+$", "", line).strip()
            lowered = clean.lower()
            if not clean:
                if in_section and captured:
                    captured.append("")
                continue

            if lowered in normalized_headings:
                in_section = True
                continue

            if in_section and lowered in common_stops:
                break

            if in_section:
                captured.append(clean)

        return captured

    def _extract_education_entries(self, resume_text: str) -> list[dict]:
        """Best-effort extraction of education entries from raw resume text."""
        section_lines = self._extract_section_lines(
            resume_text,
            ["education", "academic background", "education background"],
        )
        if not section_lines:
            return []

        text = "\n".join(section_lines)
        chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
        entries: list[dict] = []

        for chunk in chunks:
            lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            if not lines:
                continue

            university = ""
            degree = ""
            date = ""
            honors = ""
            gpa = ""
            courses: list[dict] = []

            date_match = re.search(
                r'((?:19|20)\d{2}(?:\s*[-–]\s*(?:present|current|now|(?:19|20)\d{2}))?)',
                chunk,
                re.IGNORECASE,
            )
            if date_match:
                date = date_match.group(1)

            gpa_match = re.search(r'GPA[:\s]*([0-9.\/]+)', chunk, re.IGNORECASE)
            if gpa_match:
                gpa = gpa_match.group(1)

            honors_match = re.search(
                r'(First Class Honou?rs|Second Class Honou?rs|Dean\'?s List|Distinction|Merit)',
                chunk,
                re.IGNORECASE,
            )
            if honors_match:
                honors = honors_match.group(1)

            course_match = re.search(r'(?:Relevant )?Courses?[:\s]*(.+)', chunk, re.IGNORECASE)
            if course_match:
                raw_courses = re.split(r'[,;/|]+', course_match.group(1))
                courses = [{"name": course.strip()} for course in raw_courses if course.strip()]

            for line in lines:
                if not university and re.search(r'(University|College|Institute|School)', line, re.IGNORECASE):
                    university = line
                    continue
                if not degree and re.search(r'(Bachelor|Master|B\.?Sc|M\.?Sc|PhD|Doctor|Major|Minor)', line, re.IGNORECASE):
                    degree = line

            if not university:
                university = lines[0]
            if not degree and len(lines) > 1:
                degree = lines[1]

            entry = {
                "university": university,
                "degree": degree,
                "date": date,
            }
            if honors:
                entry["honors"] = honors
            if gpa:
                entry["gpa"] = gpa
            if courses:
                entry["courses"] = courses

            if university or degree:
                entries.append(entry)

        return entries

    def _extract_project_entries(self, resume_text: str) -> list[dict]:
        """Best-effort extraction of project entries from raw resume text."""
        section_lines = self._extract_section_lines(
            resume_text,
            ["projects", "project experience", "selected projects"],
        )
        if not section_lines:
            return []

        entries: list[dict] = []
        current: dict | None = None

        def flush_current():
            nonlocal current
            if current and current.get("name"):
                current["bullets"] = [bullet for bullet in current.get("bullets", []) if bullet]
                entries.append(current)
            current = None

        for raw_line in section_lines:
            line = raw_line.strip()
            if not line:
                continue

            bullet_text = re.sub(r'^[\-\u2022•]\s*', '', line).strip()
            is_bullet = bullet_text != line or line.startswith(("-", "•"))

            # Project header heuristics: contains a date or separator and is not a bullet.
            looks_like_header = (
                not is_bullet and (
                    "|" in line
                    or "\\hfill" in line
                    or re.search(r'(19|20)\d{2}', line)
                )
            )

            if looks_like_header:
                flush_current()
                header = re.sub(r'\\hfill.*$', '', line).strip()
                date_match = re.search(
                    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)\d{2}\s*[-–]\s*(?:Present|Current|Now|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)\d{2}|(?:19|20)\d{2}))|((?:19|20)\d{2}\s*[-–]\s*(?:Present|Current|Now|(?:19|20)\d{2}))',
                    header,
                    re.IGNORECASE,
                )
                date = date_match.group(0) if date_match else ""
                name = header
                if "|" in header:
                    name = header.split("|", 1)[0].strip()
                if date:
                    name = name.replace(date, "").strip(" |-")
                current = {
                    "name": name,
                    "date": date,
                    "bullets": [],
                }
                continue

            if current is None:
                current = {
                    "name": line,
                    "date": "",
                    "bullets": [],
                }
                continue

            current["bullets"].append(bullet_text if is_bullet else line)

        flush_current()
        return entries

    def _extract_skill_entries(self, resume_text: str) -> list[dict]:
        """Best-effort extraction of skills section from raw resume text."""
        section_lines = self._extract_section_lines(
            resume_text,
            ["skills", "technical skills", "core skills"],
        )
        if not section_lines:
            return []

        skills: list[dict] = []
        uncategorized: list[str] = []

        for raw_line in section_lines:
            line = raw_line.strip()
            if not line:
                continue

            if ":" in line:
                name, values = line.split(":", 1)
                keywords = [item.strip() for item in re.split(r'[,|/;]+', values) if item.strip()]
                if keywords:
                    skills.append({
                        "name": name.strip(),
                        "keywords": keywords,
                    })
                continue

            uncategorized.extend([item.strip() for item in re.split(r'[,|/;]+', line) if item.strip()])

        if uncategorized:
            skills.append({
                "name": "Core Skills",
                "keywords": uncategorized,
            })

        return skills

    def _extract_languages(self, resume_text: str) -> list[str]:
        """Best-effort extraction of language section from raw resume text."""
        text = resume_text or ""
        patterns = [
            r'Languages?\s*[:|-]\s*(.+)',
            r'语言能力\s*[:：-]\s*(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).splitlines()[0]
                parts = re.split(r'[,|/;]+', raw)
                cleaned = [part.strip() for part in parts if part.strip()]
                if cleaned:
                    return cleaned

        detected = []
        known_languages = [
            "English", "Chinese", "Mandarin", "Cantonese", "Japanese",
            "Korean", "French", "German", "Spanish"
        ]
        lower_text = text.lower()
        for language in known_languages:
            if language.lower() in lower_text:
                detected.append(language)

        return detected

    def _extract_work_status(self, resume_text: str) -> dict:
        """Best-effort extraction of residency and availability from raw resume text."""
        text = (resume_text or "").lower()

        permanent_patterns = [
            "hong kong permanent resident",
            "hk permanent resident",
            "permanent resident",
            "no visa sponsorship required",
            "no work visa required",
        ]
        availability_patterns = [
            "available immediately",
            "immediately available",
            "available to start immediately",
            "immediate availability",
        ]

        work_eligibility = "Hong Kong Permanent Resident" if any(
            pattern in text for pattern in permanent_patterns
        ) else ""
        availability = "Available immediately" if any(
            pattern in text for pattern in availability_patterns
        ) else ""

        return {
            "work_eligibility": work_eligibility,
            "availability": availability,
        }

    def _call_ai(self, system_prompt, user_prompt, max_tokens=4000, prefill=None, max_retries=3, temperature=0):
        """
        官方 Google GenAI 调用方法
        """
        for attempt in range(max_retries):
            try:
                # 构造官方配置
                config = {
                    "system_instruction": system_prompt,
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                    "response_mime_type": "application/json"
                }

                print(f"📡 Sending request to Gemini ({self.model}, attempt {attempt + 1}/{max_retries})...")

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=config
                )

                raw_text = response.text
                if not raw_text:
                    continue

                # 解析并返回
                parsed_data = self._parse_json_response(raw_text, retry_with_repair=True)
                if parsed_data:
                    return parsed_data

            except Exception as e:
                error_str = str(e)
                print(f"❌ Gemini Error: {error_str}")
                if any(code in error_str for code in ["429", "503", "500"]):
                    wait_time = (2 ** attempt) * 5
                    print(f"⚠️ 繁忙或限流，等待 {wait_time}s 后重试...")
                    time.sleep(wait_time)
                    continue
                return None
        return None

        return None

    def analyze_user_profile(self, resume_text, transcript_text):
        """[User Profiling]"""
        system_prompt = "You are a Career Strategist. Output strictly valid JSON."
        user_prompt = f"Analyze this resume and transcript. Resume: {resume_text[:2000]}"
        return self._call_ai(system_prompt, user_prompt, temperature=0)

    def generate_search_strategy(self, resume_text, transcript_text):
        """[Strategic Discovery]"""
        print("🎯 AI 正在根据你的个人画像制定动态搜索策略...")

        # 🔍 添加日志：输入数据检查
        print(f"📊 Resume text length: {len(resume_text) if resume_text else 0}")
        print(f"📊 Transcript text length: {len(transcript_text) if transcript_text else 0}")

        system_prompt = """
        You are a Recruitment Expert.
        Generate EXACTLY 5 job role keywords based on the candidate's profile.

        🔴 KEYWORD RULES (CRITICAL):
        1. Use SHORT, GENERAL role names (1-2 words preferred)
           - GOOD: "Data Analyst", "Data Scientist", "Business Analyst", "AI Engineer", "Data Engineer"
           - BAD: "Machine Learning Engineer", "Business Intelligence Analyst", "Data Science Specialist"

        2. Must output EXACTLY 5 keywords
        3. Prefer generic titles that appear frequently on job boards
        4. NO skill combinations, NO adjectives, NO specializations
        5. Maximum 2 words per keyword

        🔴 SENIORITY DETECTION & BLACKLIST:
        First, detect the candidate's seniority level from their resume:
        - Fresh Graduate: Still in school or graduated within 1 year, 0-1 years experience
        - Junior: 1-3 years experience
        - Mid-Level: 3-6 years experience
        - Senior: 6+ years experience

        Then generate blacklist based on seniority:
        - Fresh Graduate → ["Senior", "Lead", "Manager", "Director", "VP", "Principal", "Staff", "Head"]
        - Junior → ["Senior", "Lead", "Manager", "Director", "VP", "Principal"]
        - Mid-Level → ["Director", "VP", "Head", "Chief", "Intern", "Graduate"]
        - Senior → ["Intern", "Junior", "Entry", "Graduate", "Trainee"]

        🔴 BLACKLIST FORMAT:
        - SINGLE WORDS only, NOT full job titles

        OUTPUT PURE JSON ONLY. No markdown, no explanations.
        """

        user_prompt = f"""
        # INPUT DATA
        Resume: {resume_text[:2000]}
        Transcript: {transcript_text[:1000] if transcript_text else "Not provided"}

        # OUTPUT FORMAT (EXACTLY 5 short keywords)
        {{
            "seniority": "Fresh Graduate",
            "keywords": ["Data Analyst", "Data Scientist", "Business Analyst", "AI Engineer", "Data Engineer"],
            "blacklist": ["Senior", "Lead", "Manager", "Director", "VP", "Principal", "Staff", "Head"]
        }}
        """

        # 🔍 添加日志：调用 AI
        print("🤖 Calling LLM API...")
        result = self._call_ai(system_prompt, user_prompt, temperature=0)

        # 🔍 添加日志：返回结果检查
        print(f"📦 LLM API returned: {type(result)}")
        if result is None:
            print("❌ Result is None!")
        else:
            print(f"✅ Result type: {type(result)}")
            print(f"✅ Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
            print(f"✅ Result content: {result}")

        return result

    def check_match_score(self, resume_text, jd_text, resume_language="unknown", resume_en_summary=None, job_language="unknown"):
        """
        [Dynamic Matching with Cross-Language Support]

        Args:
            resume_text: 简历原文
            jd_text: 职位描述原文
            resume_language: 简历语言代码 (zh_cn/zh_tw/en/mixed/unknown)
            resume_en_summary: 简历英文摘要（如果有）
            job_language: 职位描述语言代码

        Returns:
            评分结果字典
        """
        # 🔴 Step 0: 硬性要求预过滤（节省 Token）
        filter_result = pre_filter_job(jd_text)
        if not filter_result["pass"]:
            print(f"🚫 预过滤拦截: {filter_result['reason']}")
            return {
                "score": 0,
                "detected_seniority": "N/A",
                "verdict": "NO_MATCH",
                "match_analysis": f"硬性要求不符，已自动跳过。原因：{filter_result['reason']}",
                "strengths": [],
                "risks": [filter_result["reason"]],
                "education_match": filter_result["filter_type"] != "education",
                "experience_match": True,
                "pre_filtered": True,
                "filter_type": filter_result["filter_type"]
            }

        print("⚖️ AI 正在自动建模资历等级并执行跨语言匹配预审...")

        system_prompt = """你是一名资深技术招聘官，负责评估候选人与岗位的匹配度。
你会同时看到：
- 候选人的原始简历文本（可能是中文或英文）
- （可选）候选人简历的英文摘要
- 岗位描述（可能是中文或英文）
- 简历和岗位描述的语言标识

要求：
1. 如果简历和岗位描述使用的语言不同，你需要 **在内部** 将其中之一翻译，使两者处于同一语言环境（通常统一为英文）。
   - 不要在最终输出中展示翻译，只用于你自己的理解。

2. 评分时重点关注：
   - 技能与技术栈匹配度
   - 相关工作经验年限和深度
   - 与岗位要求的领域经验（如金融、电商、AI 等）
   - 对必备要求（必需技能、必须行业经验）的覆盖情况

3. 🔴 学历要求检查 (CRITICAL - 硬性门槛)：
   - 检查 JD 中是否有学历要求，常见关键词：
     * "Master's degree required", "PhD required", "硕士及以上", "博士学历"
     * "Bachelor's degree in Computer Science", "本科及以上"
     * "CFA required", "CPA required", "特定证书要求"

   - 如果 JD 明确要求某学历/证书，但候选人不满足：
     * 评分上限为 50 分（即使其他方面完美匹配）
     * 在 risks 中明确标注："学历不符合要求：JD要求[X]，候选人为[Y]"
     * verdict 必须设为 "NO_MATCH"

   - 学历层级（从高到低）：PhD > Master's > Bachelor's > Diploma
   - 如果候选人学历 >= JD 要求，不扣分
   - 如果候选人学历 < JD 要求，这是硬性不匹配

4. 🔴 经验年限检查：
   - 检查 JD 中的经验要求："3+ years", "5年以上经验", "Senior (7+ years)"
   - 如果候选人经验明显不足（差距 > 2年），在 risks 中标注
   - 应届生投递要求 5+ 年经验的职位，评分上限 40 分

5. 不要因为简历语言与 JD 不一致、语法不完美而明显降低评分，除非 JD 明确要求母语或书面表达能力。

6. 给出 0–100 的综合匹配评分，其中 70 分可视为"可以推荐面试"的参考阈值。

7. 输出格式必须是 JSON：
{
  "score": 0-100,
  "detected_seniority": "Junior/Mid/Senior",
  "verdict": "MATCH/NO_MATCH",
  "match_analysis": "详细的匹配分析和理由",
  "strengths": ["优势1", "优势2"],
  "risks": ["风险或不足1", "风险或不足2"],
  "education_match": true/false,
  "experience_match": true/false
}
- 当你认为候选人明显达到或超过推荐标准时，`verdict` 设为 `"MATCH"`；反之为 `"NO_MATCH"`。
- 如果学历或经验有硬性不匹配，`verdict` 必须为 `"NO_MATCH"`。"""

        # 构建用户提示词
        resume_section = f"""简历原文语言：{resume_language}
简历原文：
```text
{resume_text[:1500]}
```"""

        if resume_en_summary:
            resume_section += f"""

简历英文摘要：
```text
{resume_en_summary[:800]}
```"""

        user_prompt = f"""下面是候选人的简历与岗位描述：

{resume_section}

岗位描述语言：{job_language}
岗位描述：
```text
{jd_text[:2500]}
```

请根据系统提示进行内部翻译和匹配评估，并按要求输出 JSON。"""

        return self._call_ai(system_prompt, user_prompt, max_tokens=1000, prefill="{", temperature=0)

    def generate_resume_data(
        self,
        resume_text,
        transcript_text,
        jd_text,
        user_real_name: str,
        user_email: str,
        user_phone: str,
        user_linkedin: str = None,
        user_github: str = None
    ):
        """
        [Resume Generation] - 启用强制 JSON 模式（使用用户真实身份）

        Args:
            resume_text: 简历文本
            transcript_text: 成绩单文本
            jd_text: 职位描述
            user_real_name: 用户真实姓名（从数据库提取）
            user_email: 用户邮箱（从数据库提取）
            user_phone: 用户电话（从数据库提取）
            user_linkedin: 用户 LinkedIn（可选）
            user_github: 用户 GitHub（可选）

        Returns:
            简历数据字典
        """
        system_prompt = """
        You are a Professional Resume Tailoring Expert with deep expertise in:
        - Analyzing job descriptions to extract key requirements
        - Optimizing resumes for ATS (Applicant Tracking Systems)
        - Highlighting relevant experience and quantifying achievements
        - Creating compelling professional summaries

        ## 🎯 YOUR MISSION
        Create a TAILORED resume that maximizes the candidate's interview chances for THIS SPECIFIC JOB.
        This is NOT just data extraction - you must STRATEGICALLY reorganize and emphasize content.

        ## 📊 JD ANALYSIS FRAMEWORK (Apply Before Writing)

        **Step 1: Extract Job Requirements**
        - Priority 1 (Must-Have): Years of experience, required skills, education
        - Priority 2 (Important): Technical tools, methodologies, competencies
        - Priority 3 (Nice-to-Have): Soft skills, industry knowledge, bonus qualifications

        **Step 2: Keyword Mapping**
        - Identify repeated terms and phrases in JD
        - Note exact technology names, tools, frameworks
        - Capture industry-specific terminology

        ## 🔴 IDENTITY ENFORCEMENT RULES

        1. **Name Field**:
           - If user_real_name is PROVIDED (not empty), use it EXACTLY as given
           - If EMPTY (""), extract the candidate's FULL NAME from the resume header

        2. **Contact Information**:
           - If user_email/user_phone are PROVIDED (not empty), use them EXACTLY
           - If EMPTY (""), extract from resume header (NOT placeholders)

        ## 📝 RESUME TAILORING RULES

        **Professional Summary (3-4 lines)**:
        - Lead with years of experience in target role/field
        - Include TOP 3-4 required skills FROM THE JD
        - Mention industry experience if relevant to JD

        **Experience Bullets (STAR Format)**:
        - Format: [Action Verb] + [What] + [How/Tools] + [Quantified Result]
        - Use EXACT keywords from JD naturally
        - Quantify with numbers: percentages, dollar amounts, time saved, scale
        - Prioritize JD-relevant achievements FIRST
        - 🔴 KEEP ALL BULLETS - Do NOT reduce or summarize bullets

        **Skills Section**:
        - Group by category matching JD requirements
        - List JD-required tools/technologies FIRST
        - Use EXACT terminology from JD

        **Projects**:
        - 🔴 NEVER merge multiple projects into one - each project is separate
        - 🔴 PROJECT RETENTION RULES (CRITICAL):
          * If resume has ≤3 projects: KEEP ALL PROJECTS (only reword + reorder by relevance)
          * If resume has 4+ projects: Can delete at most 1 least relevant, must keep at least 3
        - For each project:
          * High relevance → KEEP with all bullets, reword to match JD keywords
          * Medium relevance → KEEP with 2-3 key bullets, highlight transferable skills
          * Low relevance → Shorten to 1-2 bullets, move to end (but still KEEP if ≤3 projects)
        - Sort projects by relevance (most relevant first)
        - Reword bullet points to use JD keywords and action verbs

        ## 🔴 SMART CONTENT OPTIMIZATION (Based on JD Relevance)

        **High Relevance (JD mentions this skill/experience)**:
        - KEEP all bullet points
        - Can REWORD to better match JD keywords
        - Add quantified metrics if possible

        **Medium Relevance (Transferable skills)**:
        - Keep 2-3 most impactful bullets
        - Emphasize transferable aspects

        **Low Relevance (Not related to JD)**:
        - Can reduce to 1-2 bullets or remove entirely
        - Exception: Keep if it shows leadership, impact, or scale

        ## 🔴 PROTECTED FIELDS (NEVER DELETE)
        - work_eligibility: ALWAYS keep (critical for HK jobs)
        - availability: ALWAYS keep
        - Education: ALWAYS keep full details
        - Contact info: ALWAYS keep
        - Most recent/relevant experience: Keep at least 3 bullets

        ## 🔴 MANDATORY FIELDS (MUST EXTRACT)
        - work_eligibility: Extract visa/residency status (e.g., "Hong Kong Permanent Resident", "Work Visa Required")
        - availability: Extract availability (e.g., "Available immediately", "2 weeks notice")
        - These are CRITICAL for Hong Kong job applications - NEVER omit them

        OUTPUT PURE JSON ONLY. No markdown, no explanations.
        """

        user_prompt = f"""
        # MISSION
        Extract candidate details and tailor them to the JD using the provided user identity.

        # 🔴 USER IDENTITY (MUST USE - DO NOT MODIFY)
        - Name: {user_real_name}
        - Email: {user_email}
        - Phone: {user_phone}
        - LinkedIn: {user_linkedin if user_linkedin else ''}
        - GitHub: {user_github if user_github else ''}

        # INPUT DATA (Extract content only, NOT identity)
        RESUME: {resume_text[:6000]}
        TRANSCRIPT: {transcript_text[:1500]}
        JD: {jd_text[:3000]}

        # REQUIRED OUTPUT SCHEMA (Strict JSON)
        {{
            "name": "{user_real_name}",
            "target_role": "Role Title from JD",
            "phone": "{user_phone}",
            "email": "{user_email}",
            "linkedin": "{user_linkedin if user_linkedin else ''}",
            "github": "{user_github if user_github else ''}",
            "summary": "TAILORED summary mentioning TOP 3-5 JD keywords. Start with years of experience.",
            "experience": [
                {{
                    "title": "Job Title",
                    "company": "Company",
                    "date": "Date Range (e.g., Jan 2024 - Present)",
                    "bullets": ["🔴 KEEP ALL BULLETS from original resume - reword with JD keywords but NEVER delete"]
                }}
            ],
            "projects": [
                {{
                    "name": "Project Name",
                    "date": "Project Date (e.g., Sep 2023 - Dec 2023)",
                    "bullets": ["🔴 KEEP ALL BULLETS from original resume - reword with JD keywords but NEVER delete"]
                }}
            ],
            "skills": [{{"name": "Category matching JD", "keywords": ["JD-required skills FIRST", "Then other skills"]}}],
            "education": {{
                "university": "University Name from RESUME",
                "degree": "Degree Name from RESUME",
                "date": "Graduation Date from RESUME",
                "honors": "Honors/GPA from RESUME if any",
                "courses": [
                    {{"name": "Course Name", "grade": "A+/A/A-/Distinction"}},
                    {{"name": "Another Course", "grade": "A+"}}
                ]
            }},
            "languages": [],
            "work_eligibility": "🔴 MANDATORY: Extract from resume (e.g., 'Hong Kong Permanent Resident', 'Work Visa Required', 'Right to Work in HK')",
            "availability": "🔴 MANDATORY: Extract from resume (e.g., 'Available immediately', 'Available from March 2026', '2 weeks notice')"
        }}

        # USER FEEDBACK HANDLING (CRITICAL - Apply if user provides feedback):
        You are a professional resume editor. The user may provide feedback in Chinese or English.
        You MUST understand and execute their instructions precisely.

        ## 1. CONTENT OPERATIONS:
        **删除/remove/delete** → Remove specified content completely
        **新增/add/include** → Add new content
        **修改/change/rewrite** → Modify existing content
        **合并/merge/combine** → Combine multiple items

        ## 2. ORDER OPERATIONS:
        **移动/move/放到** → Reorder sections or items
        **交换/swap** → Swap positions
        **置顶/放最前** → Move to top

        ## 3. LENGTH OPERATIONS:
        **扩展/expand/详细** → Add more details
        **精简/shorten/压缩** → Reduce length
        **平衡/balance** → Distribute content evenly

        ## 4. STYLE OPERATIONS:
        **突出/highlight/强调** → Emphasize certain aspects
        **弱化/downplay** → De-emphasize
        **针对/tailor** → Customize for specific job

        ## 5. DETAIL OPERATIONS:
        **改日期/update date** → Change dates
        **改名称/rename** → Change names
        **改顺序/reorder bullets** → Reorder items within a section

        # CRITICAL REQUIREMENTS:

        ## Identity Fields (MANDATORY - USE PROVIDED VALUES):
        1. "name" MUST be: {user_real_name}
        2. "email" MUST be: {user_email}
        3. "phone" MUST be: {user_phone}
        4. "linkedin": If empty, use "" (empty string). NEVER write "Not provided"
        5. "github": If empty, use "" (empty string). NEVER write "Not provided"

        ## Date Fields (MANDATORY - EXTRACT FROM RESUME):
        6. Every experience MUST have a "date" field with specific dates (e.g., "Jan 2024 - Present", "Mar 2023 - Aug 2023")
        7. Every project MUST have a "date" field with specific dates (e.g., "Sep 2023 - Dec 2023")
        8. If exact dates not found, estimate based on context but NEVER leave date empty

        ## Education Extraction (DYNAMIC - FROM RESUME):
        6. Find the education section in the RESUME text
        7. Extract "university" EXACTLY as written in the resume (DO NOT hardcode any school name)
        8. Extract "degree" (e.g., "Bachelor of Science in Computer Science", "Master of Engineering")
        9. Extract "date" (graduation date or study period) - THIS IS MANDATORY:
           - Extract the date EXACTLY as written in the resume (e.g., "Sept 2022 — Oct 2025")
           - DO NOT add "(Expected)" unless it is explicitly written in the original resume
           - DO NOT modify the month or year - copy it exactly as shown
           - Check near the university name, degree, or in a separate "Education" section
           - If only start year found, estimate end as start+4 for Bachelor's, start+2 for Master's
           - NEVER return empty string for date - always provide at least estimated graduation year
        10. Extract "honors" (GPA, honors, awards) if mentioned
        11. 🔴 CRITICAL: Extract "courses" ONLY from TRANSCRIPT (never from RESUME):
            - If TRANSCRIPT is empty or contains no course data, set "courses" to [] (empty array)
            - NEVER invent, guess, or extract courses from the resume text
            - ONLY extract courses explicitly listed in the TRANSCRIPT with actual grades
        12. If no education section found, use empty strings but maintain the structure

        ## Projects Extraction (AUTOMATIC CLASSIFICATION):
        13. Identify project-based experiences in the RESUME
        14. Look for keywords: "Capstone", "Project", "Technical Project", "Side Project", "Academic Project"
        15. Even if under "Work Experience", classify academic/school projects as "projects"
        16. Each project must have: "name", "date", "bullets" (array of achievements)
        17. If no projects found, return empty array []

        ## Work Experience (EXCLUDE PROJECTS):
        18. Extract only actual work experiences (internships, full-time jobs, part-time work)
        19. DO NOT include academic projects or capstone projects here
        20. Each experience must have: "title", "company", "date", "bullets"

        ## Fresh Graduate Rules:
        21. If experience ≤3 years, emphasize academic projects and coursework
        22. Highlight technical skills and learning ability
        23. Focus on potential and growth mindset
        24. Ensure at least 3-5 courses are listed if available
        """
        # 🟢 关键修改：传入 prefill="{"，强制 AI 闭嘴，直接开始写 JSON
        return self._call_ai(system_prompt, user_prompt, max_tokens=4000, prefill="{", temperature=0)

    def generate_cover_letter(self, candidate_profile, job_info, language="en"):
        """
        生成个性化 Cover Letter（支持动态日期和智能收件人，支持中英文）

        Args:
            candidate_profile: 候选人简历信息字典 (包含 resume_text, name)
            job_info: 职位信息字典，包含 title, company, location, jd_text, hr_name (可选)
            language: 生成语言，"en" 或 "zh_cn"，默认 "en"

        Returns:
            生成的 Cover Letter 文本
        """
        logger.info("Generating cover letter for position: %s at %s (language: %s)",
                   job_info.get('title', 'N/A'), job_info.get('company', 'N/A'), language)

        # 🔴 动态日期注入（根据语言格式化）
        if language == "zh_cn":
            current_date = datetime.now().strftime("%Y年%m月%d日")  # 例如: 2026年01月21日
        else:
            current_date = datetime.now().strftime("%B %d, %Y")  # 例如: January 21, 2026

        # 🔴 智能收件人处理（根据语言）
        hr_name = job_info.get('hr_name', '').strip()
        if language == "zh_cn":
            if hr_name:
                recipient = f"尊敬的{hr_name}："
                logger.info(f"Using personalized recipient (Chinese): {recipient}")
            else:
                recipient = "尊敬的招聘负责人："
                logger.info("Using default recipient (Chinese): 尊敬的招聘负责人：")
        else:
            if hr_name:
                recipient = f"Dear {hr_name},"
                logger.info(f"Using personalized recipient: {recipient}")
            else:
                recipient = "Dear Hiring Manager,"
                logger.info("Using default recipient: Dear Hiring Manager,")

        # 获取候选人姓名 - 多重回退逻辑确保使用真实姓名
        candidate_name = candidate_profile.get("name", "")

        # 如果没有姓名，尝试从 resume_text 中提取
        if not candidate_name or candidate_name == "Candidate":
            resume_text = candidate_profile.get("resume_text", "")
            if resume_text:
                # 尝试从简历文本的前几行提取姓名（通常在顶部）
                first_lines = resume_text.split('\n')[:5]
                for line in first_lines:
                    line = line.strip()
                    # 姓名通常是全大写或首字母大写，2-4个单词
                    if line and len(line.split()) <= 4 and len(line) < 50:
                        # 排除常见的非姓名行
                        if not any(keyword in line.lower() for keyword in ['email', 'phone', 'tel', 'mobile', '@', 'http', 'www']):
                            candidate_name = line
                            logger.info(f"Extracted name from resume text: {candidate_name}")
                            break

        # 最后的回退：如果还是没有姓名，使用占位符但记录警告
        if not candidate_name or candidate_name == "Candidate":
            candidate_name = "Candidate"
            logger.warning("⚠️ Could not extract candidate name, using placeholder 'Candidate'")

        # 🔴 根据语言选择 system prompt
        if language == "zh_cn":
            system_prompt = """
            你是一名专业的职业咨询顾问，擅长撰写有说服力的求职信。
            你撰写的求职信简洁、专业、个性化，能够突出候选人的优势。
            你必须严格遵循提供的格式要求，包括日期位置和收件人称呼。
            """
        else:
            system_prompt = """
            You are a professional career consultant specializing in writing compelling cover letters.
            You write concise, professional, and personalized cover letters that highlight candidate strengths.
            You MUST follow the exact format requirements provided, including date placement and recipient addressing.
            """

        # 获取简历文本 - 优先使用 resume_text，如果没有则构造摘要
        resume_text = candidate_profile.get("resume_text", "")

        if not resume_text and isinstance(candidate_profile, dict):
            # 如果没有 resume_text，从结构化数据中提取关键信息
            summary_parts = []
            key_fields = ["name", "email", "phone", "summary", "skills", "experience"]

            for field in key_fields:
                if field in candidate_profile and candidate_profile[field]:
                    value = candidate_profile[field]
                    # 如果是列表或字典，简化展示
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value, ensure_ascii=False)
                    summary_parts.append(f"{field.upper()}: {value}")

            resume_text = "\n".join(summary_parts) if summary_parts else json.dumps(candidate_profile, ensure_ascii=False)

        # 🔴 根据语言生成不同的 user prompt
        if language == "zh_cn":
            user_prompt = f"""
        为以下职位申请撰写一封专业的求职信（中文）。

        # 候选人信息
        候选人姓名：{candidate_name}
        {resume_text[:2000]}

        # 目标职位
        职位：{job_info.get('title', 'N/A')}
        公司：{job_info.get('company', 'N/A')}
        地点：{job_info.get('location', 'N/A')}

        职位描述：
        {job_info.get('jd_text', 'N/A')[:2000]}

        # 🔴 关键格式要求（必须严格遵循）

        ## 1. 日期和抬头
        - 以当前日期开头：{current_date}
        - 日期后空一行
        - 添加公司名称：{job_info.get('company', 'N/A')}
        - 如果有公司地址，添加地址（否则跳过）
        - 收件人前空一行

        ## 2. 收件人
        - 使用此收件人称呼：{recipient}
        - 这是根据可用信息预先确定的
        - 不要更改或修改收件人称呼

        ## 3. 正文内容
        - 长度：300-500 字
        - 开头段落：表达兴趣并提及具体职位
        - 正文段落（2-3段）：突出与职位描述匹配的相关技能、经验和成就
        - 尽可能使用具体示例和数据
        - 展现对公司和职位的热情
        - 结尾段落：表达面试意愿

        ## 4. 结尾
        - 使用"此致\\n敬礼"
        - 然后是候选人姓名：{candidate_name}

        ## 5. 语气和语言
        - 专业、自信，但不傲慢
        - 使用中文

        # 格式示例（仅供参考结构 - 不要复制内容）

        {current_date}

        {job_info.get('company', '公司名称')}
        [公司地址（如有）]

        {recipient}

        [开头段落表达兴趣...]

        [正文段落1突出相关经验...]

        [正文段落2展现热情和匹配度...]

        [结尾段落请求面试...]

        此致
        敬礼

        {candidate_name}

        # 你的输出
        仅输出严格遵循上述格式的求职信文本。
        不要有任何解释、不要有 Markdown 格式、不要有额外文本。
        """
        else:
            user_prompt = f"""
        Write a professional yet personable cover letter for the following job application.

        # CANDIDATE INFO
        Candidate Name: {candidate_name}
        {resume_text[:2000]}

        # TARGET JOB
        Position: {job_info.get('title', 'N/A')}
        Company: {job_info.get('company', 'N/A')}
        Location: {job_info.get('location', 'N/A')}

        Job Description:
        {job_info.get('jd_text', 'N/A')[:2000]}

        # 🔴 CRITICAL FORMAT REQUIREMENTS (MUST FOLLOW EXACTLY)

        ## 1. Date and Header
        - Start with the current date: {current_date}
        - Leave one blank line after the date
        - Add company name: {job_info.get('company', 'N/A')}
        - If company address is available, add it (otherwise skip)
        - Leave one blank line before the recipient

        ## 2. Recipient
        - Use this exact recipient line: {recipient}
        - This has been pre-determined based on available information
        - DO NOT change or modify the recipient line

        ## 3. Body Content (HUMANIZE - CRITICAL)
        - Length: 300-400 words
        - Write in a NATURAL, CONVERSATIONAL tone - like a real person, not a robot
        - Opening paragraph: Express genuine interest. Mention HOW you found the role or WHY this company excites you personally
        - Body paragraphs (2-3):
          * Share specific stories or examples from your experience
          * Use "I" statements naturally, vary sentence structure
          * Connect your experience to their needs with enthusiasm
          * Avoid generic phrases like "I am writing to apply" or "I believe I am a good fit"
        - Closing paragraph: Express genuine interest in discussing further, show personality

        ## 4. Closing
        - Use "Yours sincerely," (NOT "Best regards" or "Sincerely")
        - Follow with EXACTLY this name: {candidate_name}
        - DO NOT modify or abbreviate the candidate name

        ## 5. Tone and Language
        - Professional yet warm and authentic
        - Sound like a real person with genuine enthusiasm
        - Avoid corporate jargon and template phrases
        - English

        # EXAMPLE FORMAT (STRUCTURE ONLY - DO NOT COPY CONTENT)

        {current_date}

        {job_info.get('company', 'Company Name')}
        [Company Address if available]

        {recipient}

        [Opening paragraph - show genuine interest, mention something specific about the company...]

        [Body paragraph 1 - share a specific story or achievement relevant to the role...]

        [Body paragraph 2 - connect your skills to their needs with enthusiasm...]

        [Closing paragraph - express genuine interest in discussing further...]

        Yours sincerely,
        {candidate_name}

        # YOUR OUTPUT
        OUTPUT ONLY THE COVER LETTER TEXT FOLLOWING THE EXACT FORMAT ABOVE.
        The signature name MUST be exactly: {candidate_name}
        NO EXPLANATIONS, NO MARKDOWN, NO EXTRA TEXT.
        """

        try:
            # 直接调用 AI，不需要 JSON 格式
            messages = [{"role": "user", "content": user_prompt}]

            response = self.client.messages.create(
                model=self.model,
                max_tokens=3000,  # 🔴 修复：增加到 3000 tokens，确保求职信完整生成
                temperature=0.7,  # 稍高温度以增加创意性
                system=system_prompt,
                messages=messages
            )

            # 处理多种内容块类型（TextBlock 和 ThinkingBlock）
            cover_letter = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    cover_letter = block.text.strip()
                    break

            if not cover_letter:
                raise ValueError("API 响应中没有找到文本内容")

            logger.info("Cover letter generated successfully (length: %d characters)", len(cover_letter))

            # 🔴 验证格式：确保包含日期和正确的收件人
            if current_date not in cover_letter:
                logger.warning("⚠️ Generated cover letter missing date, prepending it")
                cover_letter = f"{current_date}\n\n{cover_letter}"

            if recipient not in cover_letter and "Dear" not in cover_letter:
                logger.warning("⚠️ Generated cover letter missing recipient, adding it")
                # 在日期后添加收件人
                parts = cover_letter.split('\n\n', 1)
                if len(parts) == 2:
                    cover_letter = f"{parts[0]}\n\n{job_info.get('company', '')}\n\n{recipient}\n\n{parts[1]}"

            return cover_letter

        except Exception as e:
            logger.exception("Cover letter generation failed")
            # 🔴 返回一个符合新格式的基本模板（根据语言）
            if language == "zh_cn":
                return f"""{current_date}

{job_info.get('company', '公司名称')}

{recipient}

我写信表达我对贵公司{job_info.get('title', '该职位')}的浓厚兴趣。

凭借我的背景和经验，我相信我能为贵公司团队带来价值。我对加入{job_info.get('company', '贵公司')}的机会感到兴奋，并期待有机会讨论我的技能如何与贵公司的需求相匹配。

感谢您考虑我的申请。期待您的回复。

此致
敬礼

{candidate_name}
"""
            else:
                return f"""{current_date}

{job_info.get('company', 'Company Name')}

{recipient}

I am writing to express my strong interest in the {job_info.get('title', 'position')} at {job_info.get('company', 'your company')}.

With my background and experience, I believe I would be a valuable addition to your team. I am excited about the opportunity to contribute to {job_info.get('company', 'your company')} and would welcome the chance to discuss how my skills align with your needs.

Thank you for considering my application. I look forward to hearing from you.

Yours sincerely,
{candidate_name}
"""

    def generate_job_search_keywords_from_resume(self, resume_text: str) -> str:
        """
        基于简历内容生成求职搜索关键词

        Args:
            resume_text: 简历文本内容

        Returns:
            逗号分隔的关键词字符串（3个关键词）
        """
        system_prompt = "你是一个专业的求职顾问，擅长分析简历并提取关键技能。"

        user_prompt = f"""请分析以下简历内容，提取出3个最适合用于求职搜索的关键词。

要求：
1. 关键词应该是具体的职位名称或技术领域
2. 关键词应该能够在招聘网站上搜索到相关职位
3. 优先选择简历中最突出的技能和经验相关的关键词
4. 只返回3个关键词，用中文逗号分隔
5. 不要包含任何解释或其他内容

简历内容：
{resume_text[:3000]}

请直接返回3个关键词（用逗号分隔）："""

        try:
            messages = [{"role": "user", "content": user_prompt}]

            response = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                temperature=0.3,
                system=system_prompt,
                messages=messages
            )

            # 处理多种内容块类型（TextBlock 和 ThinkingBlock）
            keywords = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    keywords = block.text.strip()
                    break

            if not keywords:
                raise ValueError("API 响应中没有找到文本内容")
            # 清理可能的多余字符
            keywords = keywords.replace("，", ",").replace("、", ",")
            # 确保格式正确
            keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
            return ",".join(keyword_list[:3])  # 最多返回3个

        except Exception as e:
            logger.exception("Generate keywords failed")
            raise RuntimeError(f"生成关键词失败: {e}")

    def extract_top_courses(self, transcript_text: str, min_grade: str = "B+") -> str:
        """
        从成绩单文本中智能提取优选课程（B+ 或以上）

        Args:
            transcript_text: 成绩单原始文本（可能包含表格、乱码等）
            min_grade: 最低成绩要求（默认 B+）

        Returns:
            清洗后的课程名称列表（逗号分隔字符串）
        """
        logger.info("🎓 正在智能解析成绩单，提取优选课程...")

        system_prompt = """You are an academic records auditor specialized in parsing unformatted university transcripts.
Your task is to extract course information with high accuracy, even when the text is messy or poorly formatted.

CRITICAL RULE: You MUST strictly enforce grade filtering with ABSOLUTE ZERO tolerance for grades below B+ (3.3 GPA).
ANY course with B (3.0), B- (2.7), or lower MUST be REJECTED. This is NON-NEGOTIABLE."""

        user_prompt = f"""# MISSION
Parse the provided unformatted text from a university transcript and extract ONLY the courses with high grades.

# INPUT DATA (Raw Transcript Text)
{transcript_text[:4000]}

# ⚠️ CRITICAL GRADE FILTERING RULES - READ CAREFULLY ⚠️

## ✅ WHITELIST - Include ONLY these exact grades (NO EXCEPTIONS):
- **A+** (4.0 GPA or 90-100 or 9.0/10 or 4.5/4.5)
- **A** (4.0 GPA or 85-89 or 8.5-8.9/10 or 4.0-4.4/4.5)
- **A-** (3.7 GPA or 80-84 or 8.0-8.4/10 or 3.7-3.9/4.5)
- **B+** (3.3 GPA or 75-79 or 7.5-7.9/10 or 3.3-3.6/4.5)
- **Distinction** (explicit "Distinction" label)
- **High Distinction** (explicit "High Distinction" label)

## ❌ BLACKLIST - ABSOLUTELY FORBIDDEN (REJECT IMMEDIATELY):
- **B** (3.0 GPA or 70-74 or 7.0-7.4/10) - ❌ REJECT
- **B-** (2.7 GPA or 65-69 or 6.5-6.9/10) - ❌ REJECT
- **C+** (2.3 GPA or 60-64) - ❌ REJECT
- **C** (2.0 GPA or 55-59) - ❌ REJECT
- **C-** (1.7 GPA or 50-54) - ❌ REJECT
- **D+, D, D-** (below 50) - ❌ REJECT
- **F, Fail** - ❌ REJECT
- **Pass** (without "Distinction" or "High Distinction") - ❌ REJECT
- **Credit** (without "Distinction") - ❌ REJECT
- **Not specified** or **Missing grade** - ❌ REJECT
- **Any numeric score below 75** - ❌ REJECT
- **Any GPA below 3.3** - ❌ REJECT

# MANDATORY VERIFICATION STEPS (YOU MUST FOLLOW THESE):

**Step 1**: Extract all courses with their grades from the transcript.

**Step 2**: For EACH course, check its grade against the WHITELIST:
   - If grade is A+, A, A-, B+, Distinction, or High Distinction → KEEP IT
   - If grade is B, B-, C+, C, C-, D, F, Pass, Credit, or below 75 → DELETE IT IMMEDIATELY

**Step 3**: Before outputting, perform a FINAL VERIFICATION:
   - Review your output list
   - If you see ANY course that might have B, B-, or lower → REMOVE IT
   - If you're unsure about a grade → EXCLUDE IT (better safe than sorry)

**Step 4**: Double-check numeric conversions:
   - 75-79 → B+ (INCLUDE)
   - 70-74 → B (EXCLUDE)
   - Below 70 → EXCLUDE
   - GPA 3.3-3.6 → B+ (INCLUDE)
   - GPA 3.0-3.2 → B (EXCLUDE)
   - GPA below 3.0 → EXCLUDE

# TASK REQUIREMENTS
1. Identify course names and their corresponding grades from the messy text.
2. **CRITICAL**: Include ONLY courses with grades from the WHITELIST above.
3. Handle common parsing errors (split lines, extra whitespace, etc.).
4. Ignore non-course entries (e.g., "Total Credits", "GPA", "Semester").

# OUTPUT FORMAT
Return ONLY a clean, comma-separated list of course names. No explanations, no grades, no extra text.
If NO courses meet the criteria, return an empty string.

# EXAMPLE OUTPUT (CORRECT)
Machine Learning, Advanced Algorithms, Data Mining, Computer Vision, Natural Language Processing

# EXAMPLE OUTPUT (WRONG - DO NOT DO THIS)
Machine Learning, Advanced Algorithms, Database Systems (B), Data Mining

# YOUR OUTPUT (Course Names Only):"""

        try:
            messages = [{"role": "user", "content": user_prompt}]

            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0,  # 使用低温度确保一致性
                system=system_prompt,
                messages=messages
            )

            # 提取文本内容
            course_list = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    course_list = block.text.strip()
                    break

            if not course_list:
                logger.warning("⚠️ AI 未返回任何课程信息")
                return ""

            # 清理输出（移除可能的多余文本）
            # 如果 AI 还是说了废话，只保留逗号分隔的部分
            if "\n" in course_list:
                # 取第一行（通常是课程列表）
                course_list = course_list.split("\n")[0].strip()

            # 移除可能的引号或括号
            course_list = course_list.replace('"', '').replace("'", '').strip()

            # 验证格式（应该是逗号分隔的课程名）
            courses = [c.strip() for c in course_list.split(",") if c.strip()]

            if not courses:
                logger.warning("⚠️ 未能从成绩单中提取到符合条件的课程")
                return ""

            logger.info(f"✅ 成功提取 {len(courses)} 门优选课程")
            return ", ".join(courses)

        except Exception as e:
            logger.error(f"❌ 成绩单解析失败: {e}")
            return ""

    def optimize_resume_for_hk_hr(
        self,
        resume_text: str,
        permanent_resident: bool = False,
        available_immediately: bool = False,
        linkedin_url: str = "",
        github_url: str = "",
        portfolio_url: str = "",
        target_profile: str = "general",
        edit_instructions: list | None = None,
        additional_notes: str = ""
    ) -> dict:
        """简历优化，支持目标版本和结构化编辑指令。"""
        logger.info("🎯 开始优化简历...")
        edit_instructions = edit_instructions or []
        extracted_contact = self._extract_contact_details(resume_text)
        extracted_education = self._extract_education_entries(resume_text)
        extracted_projects = self._extract_project_entries(resume_text)
        extracted_skills = self._extract_skill_entries(resume_text)
        extracted_languages = self._extract_languages(resume_text)
        extracted_work_status = self._extract_work_status(resume_text)

        profile_guidance = {
            "general": "Keep the resume broadly applicable for modern tech roles. Balance engineering, product impact, and ATS keyword coverage.",
            "qa": "Emphasize testing, automation, defect prevention, QA workflows, regression coverage, test planning, and quality metrics.",
            "fintech": "Emphasize financial systems, risk, data accuracy, compliance awareness, analytics, transaction workflows, and business-critical reliability.",
            "da": "Emphasize analytics, SQL, dashboards, experimentation, business insights, data cleaning, reporting, and measurable decision support.",
        }
        profile_instruction = profile_guidance.get(
            str(target_profile).lower(),
            profile_guidance["general"],
        )
        serialized_instructions = json.dumps(edit_instructions, ensure_ascii=False, indent=2)

        system_prompt = """You are a Professional Resume Consultant. 
MISSION: Map raw resume text into a specific JSON schema and follow structured edit instructions exactly.
🔴 DATA INTEGRITY: You MUST include ALL work experiences, ALL projects, and ALL education details unless the user explicitly deletes something.
🔴 CONTACT INTEGRITY: Preserve email, phone, LinkedIn, GitHub, portfolio, and languages whenever they appear in the source.
🔴 STATUS INTEGRITY: Preserve permanent residency, visa/work eligibility, and availability whenever they appear in the source.
🔴 EDIT RULES:
- delete: remove only the targeted content.
- add: add new content naturally in the best matching section.
- modify: rewrite only the targeted section while preserving factual consistency.
🔴 TARGET PROFILE: adjust wording, summary, and keyword emphasis for the requested profile without inventing experience.
🔴 MANDATORY: Do NOT omit "Loan Risk Analytics System" or "Capstone" unless explicitly deleted.
🔴 FORMAT: Output ONLY pure JSON."""

        user_prompt = f"""# RAW CONTENT:
{resume_text[:5000]}

# TARGET PROFILE:
{target_profile}

# PROFILE GUIDANCE:
{profile_instruction}

# STRUCTURED EDIT INSTRUCTIONS:
{serialized_instructions}

# ADDITIONAL NOTES:
{additional_notes if additional_notes else "Standard HK optimization."}

# OUTPUT SCHEMA:
{{
  "name": "...",
  "email": "...",
  "phone": "...",
  "linkedin": "...",
  "github": "...",
  "portfolio": "...",
  "summary": "...",
  "experience": [{{"title": "...", "company": "...", "date": "...", "bullets": ["..."]}}],
  "projects": [{{"name": "...", "date": "...", "bullets": ["..."]}}],
  "education": [{{"university": "...", "degree": "...", "date": "...", "gpa": "...", "courses": [{{"name": "..."}}]}}],
  "skills": [{{"name": "...", "keywords": ["..."]}}],
  "languages": ["..."]
}}"""

        result = None
        for attempt in range(2):
            logger.info(f"📡 Calling Gemini (Attempt {attempt+1}/2)...")
            candidate = self._call_ai(system_prompt, user_prompt, max_tokens=4000, temperature=0)
            
            if candidate:
                # 🛠️ 字段对齐修复
                if "projects" in candidate and isinstance(candidate["projects"], list):
                    for p in candidate["projects"]:
                        if "title" in p and "name" not in p: p["name"] = p["title"]
                if extracted_projects:
                    candidate_projects = candidate.get("projects", [])
                    if not isinstance(candidate_projects, list):
                        candidate_projects = []
                    candidate["projects"] = self._merge_missing_projects(
                        candidate_projects,
                        extracted_projects,
                        edit_instructions,
                    )
                    candidate["projects"] = self._dedupe_and_merge_projects(candidate["projects"])
                    candidate["projects"] = self._apply_project_edit_instruction_hints(
                        candidate["projects"],
                        edit_instructions,
                    )
                    candidate["projects"] = self._apply_deterministic_project_edits(
                        candidate["projects"],
                        edit_instructions,
                    )
                if extracted_skills:
                    candidate_skills = candidate.get("skills", [])
                    if not isinstance(candidate_skills, list):
                        candidate_skills = []
                    candidate["skills"] = self._merge_missing_skills(candidate_skills, extracted_skills)
                if not candidate.get("education") and extracted_education:
                    candidate["education"] = extracted_education
                
                requested_delete = "delete" in str(additional_notes).lower() or any(
                    item.get("action") == "delete" for item in edit_instructions
                )
                is_complete, reason = self._validate_resume_result(
                    candidate,
                    allow_missing_projects=requested_delete,
                )

                print(
                    f"📊 Check: exp={len(candidate.get('experience', []))}, "
                    f"proj={len(candidate.get('projects', []))}, "
                    f"edu={bool(candidate.get('education'))}, complete={is_complete}"
                )

                if is_complete:
                    result = candidate
                    break
                logger.warning(f"⚠️ Data incomplete ({reason}), retrying...")
                user_prompt += (
                    "\n\nCRITICAL: Previous output was incomplete. "
                    "You must return non-empty education and preserve work experience/projects from the source."
                )

        if result:
            if permanent_resident:
                result["work_eligibility"] = "Hong Kong Permanent Resident"
            elif not result.get("work_eligibility") and extracted_work_status.get("work_eligibility"):
                result["work_eligibility"] = extracted_work_status["work_eligibility"]

            if available_immediately:
                result["availability"] = "Available immediately"
            elif not result.get("availability") and extracted_work_status.get("availability"):
                result["availability"] = extracted_work_status["availability"]
            if not result.get("email") and extracted_contact.get("email"):
                result["email"] = extracted_contact["email"]
            if not result.get("phone") and extracted_contact.get("phone"):
                result["phone"] = extracted_contact["phone"]
            if linkedin_url:
                result["linkedin"] = linkedin_url
            elif not result.get("linkedin") and extracted_contact.get("linkedin"):
                result["linkedin"] = extracted_contact["linkedin"]
            if github_url:
                result["github"] = github_url
            elif not result.get("github") and extracted_contact.get("github"):
                result["github"] = extracted_contact["github"]
            if portfolio_url:
                result["portfolio"] = portfolio_url
            elif not result.get("portfolio") and extracted_contact.get("portfolio"):
                result["portfolio"] = extracted_contact["portfolio"]
            if result.get("linkedin") and not self._is_valid_url(result["linkedin"]):
                result["linkedin"] = extracted_contact.get("linkedin", "")
            if result.get("github") and not self._is_valid_url(result["github"]):
                result["github"] = extracted_contact.get("github", "")
            if result.get("portfolio") and not self._is_valid_url(result["portfolio"]):
                result["portfolio"] = extracted_contact.get("portfolio", "")
            if not result.get("languages") and extracted_languages:
                result["languages"] = extracted_languages
            return result
        return None
