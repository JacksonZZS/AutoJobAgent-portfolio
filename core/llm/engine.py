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
from anthropic import Anthropic
from dotenv import load_dotenv
from datetime import datetime

from core.llm.json_utils import clean_json_string, parse_json_response
from core.llm.pre_filter import pre_filter_job
from core.llm.prompts import RESUME_EXTRACTION_PROMPT

load_dotenv()

logger = logging.getLogger(__name__)


class LLMEngine:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        # 从 .env 读取 BASE_URL，支持多种变量名
        # 优先级: API_BASE_URL > BASE_URL > ANTHROPIC_BASE_URL > 默认本地
        base_url = os.getenv("API_BASE_URL") or os.getenv("BASE_URL") or os.getenv("ANTHROPIC_BASE_URL") or "http://127.0.0.1:8045"

        if not api_key:
            raise ValueError("❌ MISSING_API_KEY: Please check your .env file.")

        self.client = Anthropic(api_key=api_key, base_url=base_url)
        # 建议使用稳定版本，或者你之前指定的版本
        self.model = "gemini-3-flash"

    def _clean_json_string(self, text):
        """Delegate to module-level function for backward compatibility."""
        return clean_json_string(text)

    def _parse_json_response(self, text, retry_with_repair=True):
        """Delegate to module-level function for backward compatibility."""
        return parse_json_response(text, retry_with_repair=retry_with_repair)

    def _call_ai(self, system_prompt, user_prompt, max_tokens=4000, prefill=None, max_retries=3, temperature=0):
        """
        增强的 AI 调用方法，支持 JSON 解析失败时的自动重试

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            max_tokens: 最大 token 数
            prefill: 强制 AI 以特定字符开头（例如 "{"），防止它说废话
            max_retries: 遇到 429 错误或 JSON 解析失败时的最大重试次数
            temperature: 温度参数，默认为 0（更确定性的输出）

        Returns:
            解析后的 JSON 对象，失败返回 None
        """
        last_raw_text = None  # 保存最后一次的原始响应，用于调试

        # 🔍 添加日志
        print(f"🔧 _call_ai called with max_tokens={max_tokens}, temperature={temperature}, prefill={prefill}")

        for attempt in range(max_retries):
            try:
                messages = [{"role": "user", "content": user_prompt}]

                # ✅ 强力技巧：如果你传入了 prefill (比如 "{")，我们假装 AI 已经说了这个字
                # AI 就只能接着往下填内容，没机会说 "Here is the JSON..."
                if prefill:
                    messages.append({"role": "assistant", "content": prefill})

                # 如果是重试，并且之前解析失败，添加修复提示
                if attempt > 0 and last_raw_text:
                    logger.info(f"🔄 第 {attempt + 1} 次尝试，要求 AI 修复 JSON 格式...")
                    print(f"🔄 Retry attempt {attempt + 1}/{max_retries}")
                    # 在用户提示词后添加修复指令
                    user_prompt_with_fix = f"""{user_prompt}

CRITICAL: The previous response had JSON parsing errors. Please ensure:
1. All strings are properly escaped (especially newlines and quotes)
2. No trailing commas in objects or arrays
3. All brackets and braces are properly closed
4. Output ONLY valid JSON, no explanations or markdown
5. Use double quotes for all strings, not single quotes"""
                    messages[0]["content"] = user_prompt_with_fix

                # 🔍 添加日志
                print(f"📡 Sending request to LLM (attempt {attempt + 1}/{max_retries})...")

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature if attempt == 0 else 0,  # 重试时强制使用 temperature=0
                    system=system_prompt,
                    messages=messages
                )

                # 🔍 添加日志
                print(f"✅ Got response from LLM, processing...")

                # 处理多种内容块类型（TextBlock 和 ThinkingBlock）
                raw_text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        raw_text = block.text
                        break  # 找到第一个文本块就停止

                if not raw_text:
                    print(f"⚠️ API 响应中没有找到文本内容")
                    logger.warning(f"⚠️ API 响应中没有找到文本内容")
                    return None

                # 如果使用了 prefill，AI 返回的内容是剩下的部分，我们要把开头补回去
                if prefill:
                    raw_text = prefill + raw_text

                last_raw_text = raw_text  # 保存原始响应

                # 🔍 添加日志：显示原始响应
                print(f"📝 Raw response (first 500 chars):\n{raw_text[:500]}")

                # ✅ 使用增强的 JSON 解析方法
                print(f"🔍 Parsing JSON response...")
                parsed_data = self._parse_json_response(raw_text, retry_with_repair=True)

                if parsed_data is not None:
                    if attempt > 0:
                        logger.info(f"✅ 第 {attempt + 1} 次尝试成功解析 JSON")
                    print(f"✅ JSON parsed successfully!")
                    return parsed_data
                else:
                    # JSON 解析失败
                    print(f"❌ JSON parsing failed!")
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ JSON 解析失败，准备重试... (尝试 {attempt + 1}/{max_retries})")
                        logger.debug(f"失败的原始响应 (前200字符): {raw_text[:200]}")
                        print(f"⚠️ Will retry...")
                        time.sleep(1)  # 短暂等待后重试
                        continue
                    else:
                        logger.error(f"❌ 已达到最大重试次数，JSON 解析仍然失败")
                        logger.error(f"最后的原始响应 (前500字符): {raw_text[:500]}")
                        print(f"❌ Max retries reached, giving up")
                        return None

            except json.JSONDecodeError as e:
                print(f"❌ JSONDecodeError: {str(e)}")
                logger.error(f"❌ JSON 解析异常: {str(e)}")
                if last_raw_text:
                    logger.error(f"   出错数据片段: {last_raw_text[:200]}...")
                if attempt < max_retries - 1:
                    logger.info(f"🔄 准备重试... (尝试 {attempt + 1}/{max_retries})")
                    time.sleep(1)
                    continue
                return None

            except Exception as e:
                error_str = str(e)
                print(f"❌ Exception in _call_ai: {type(e).__name__}: {error_str}")

                # 🔴 检查是否是可重试的错误（429, 500, 502, 503, 504）
                is_rate_limit = "429" in error_str or "Too Many Requests" in error_str
                is_server_error = any(code in error_str for code in ["500", "502", "503", "504", "InternalServerError", "Bad Gateway", "Service Unavailable"])

                if is_rate_limit or is_server_error:
                    if attempt < max_retries - 1:
                        # 指数退避: 2s, 4s, 8s（服务器错误等待更长时间）
                        base_wait = 3 if is_server_error else 2
                        wait_time = (2 ** attempt) * base_wait
                        error_type = "服务器错误" if is_server_error else "速率限制"
                        logger.warning(f"⚠️ 遇到{error_type}，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                        print(f"⚠️ {error_type}，等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"❌ 已达到最大重试次数: {error_str}")
                        return None
                else:
                    logger.error(f"❌ LLM_ENGINE_ERROR: {error_str}")
                    import traceback
                    traceback.print_exc()
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
        additional_notes: str = ""
    ) -> dict:
        """
        优化简历以符合香港HR要求

        Args:
            resume_text: 原始简历文本
            permanent_resident: 是否为香港永久居民
            available_immediately: 是否可以立即上班
            linkedin_url: LinkedIn 地址
            github_url: GitHub 地址
            portfolio_url: 个人网站/作品集地址
            additional_notes: 其他补充信息

        Returns:
            优化后的简历数据字典
        """
        logger.info("🎯 开始优化简历以符合香港HR要求...")

        # 🔴 自动从简历文本提取 URL（如果用户没有手动提供）
        if not linkedin_url:
            linkedin_match = re.search(r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+', resume_text, re.IGNORECASE)
            if linkedin_match:
                linkedin_url = linkedin_match.group(0)
                logger.info(f"📎 自动提取 LinkedIn: {linkedin_url}")

        if not github_url:
            github_match = re.search(r'(?:https?://)?(?:www\.)?github\.com/[\w-]+', resume_text, re.IGNORECASE)
            if github_match:
                github_url = github_match.group(0)
                logger.info(f"📎 自动提取 GitHub: {github_url}")

        # 构建系统提示词
        system_prompt = """You are a Professional Resume Consultant specializing in Hong Kong job market requirements.

Your task is to optimize resumes to meet Hong Kong HR expectations while maintaining authenticity.

## Hong Kong HR Requirements:

1. **Work Eligibility**: Clearly state work permit status
2. **Availability**: Indicate start date availability
3. **Contact Information**: Include LinkedIn, GitHub if relevant to role
4. **Format**: Clean, ATS-friendly, reverse chronological
5. **Language**: Professional English (Hong Kong business standard)
6. **Length**: Ideally 1 page for fresh graduates, 2 pages maximum for experienced
7. **Highlights**: Quantifiable achievements, relevant skills

## Optimization Rules:

- Keep all original information accurate and truthful
- Improve clarity and formatting
- Add missing sections if needed (e.g., Professional Summary)
- Reorder sections for better flow: Contact → Summary → Experience → Skills → Education → Projects
- Use action verbs and quantify achievements where possible
- Ensure ATS compatibility (no complex formatting)

## 🔴 PROJECT PROTECTION RULES (CRITICAL - NEVER DELETE PROJECTS):

1. **KEEP ALL PROJECTS** - Do NOT delete any projects, especially:
   - Capstone Project / Final Year Project / Academic Project
   - Side projects / Personal projects
   - Any project that shows technical skills

2. **For Fresh Graduates (≤1 year experience)**:
   - Projects are MORE important than work experience
   - MUST keep ALL projects to demonstrate technical ability
   - Only reword/reorder, NEVER delete

3. **Project Optimization (NOT deletion)**:
   - Reword bullet points to match JD keywords
   - Reorder projects by relevance (most relevant first)
   - Add quantifiable metrics if missing
   - Keep minimum 3-4 bullet points per project

4. **If user did NOT explicitly say "删除" or "delete"**:
   - Assume they want to KEEP all projects
   - Only optimize wording and order

## 🔴 USER INSTRUCTIONS (MUST FOLLOW - HIGHEST PRIORITY):

The user may provide special instructions in "Additional Notes". You MUST follow these instructions:

1. **DELETE/REMOVE instructions**: If user says "删除", "remove", "delete" certain projects/sections/content,
   you MUST exclude them from the output completely. Do NOT include them.

2. **COMPRESS/SHORTEN instructions**: If user says "压缩", "compress", "shorten", "reduce bullets",
   you MUST reduce content length - fewer bullet points, shorter descriptions, remove less important items.

3. **ADD/INCLUDE instructions**: If user says "增加", "add", "include" new content,
   you MUST add it AND optimize it to match the resume's overall theme and target role.
   - Analyze the resume's career direction (e.g., Data Science, AI, Frontend, Backend)
   - New content should use similar language, keywords, and style as existing content
   - Quantify achievements where possible
   - Make it consistent with the candidate's experience level

4. **SKILL EXTRACTION FROM NEW CONTENT (INTELLIGENT MATCHING)**:
   When user adds new projects or experiences, you MUST:

   Step 1: Analyze the EXISTING resume to understand the career direction:
   - What is the target role? (DS, DE, Quant, BA, PM, etc.)
   - What skills are already listed?
   - What is the writing style and keyword pattern?

   Step 2: Extract skills from the NEW project that MATCH the resume direction:
   - If resume is DS-focused and new project mentions "built a web scraper":
     → Extract: "Data Collection", "Web Scraping", "Python" (NOT "HTML", "CSS")
   - If resume is Quant-focused and new project mentions "predicted stock prices":
     → Extract: "Time Series Forecasting", "Alpha Generation", "Statistical Modeling"
   - If resume is BA-focused and new project mentions "analyzed customer data":
     → Extract: "Customer Analytics", "SQL", "Business Intelligence"

   Step 3: ADD extracted skills to the appropriate skill category:
   - Group with similar existing skills
   - Use consistent naming convention (match existing skill format)
   - Do NOT duplicate skills already present

   Step 4: REWRITE the new project description to match resume style:
   - Use same action verbs as existing projects
   - Add quantifiable metrics if possible
   - Match the technical depth level of existing content

   Examples:
   - User adds: "做了一个用 Python 预测股票的项目"
   - If resume is DS → "Developed stock prediction model using LSTM, achieving 15% improvement over baseline"
   - If resume is Quant → "Built alpha generation signal with Sharpe ratio 1.2 using time series analysis"
   - If resume is BA → "Analyzed market trends to identify investment opportunities, supporting $1M trading decisions"

5. **TARGET ROLE TRANSFORMATION**: If user specifies a target direction like:
   - "改成 quant 相关" / "quantitative" / "量化"
   - "改成 data engineer" / "数据工程"
   - "改成 ML engineer" / "机器学习工程师"

   You MUST transform the ENTIRE resume to match that direction:

   **For Quantitative/Quant roles:**
   - Rewrite Professional Summary to emphasize: quantitative analysis, statistical modeling, trading strategies
   - Reorder skills: Python, R, SQL, C++ → Statistical Modeling, Time Series → Risk Management, Portfolio Optimization
   - Reframe project bullets: "Built ML model" → "Developed alpha generation model with Sharpe ratio 1.8"
   - Add quant keywords: backtesting, factor models, Greeks, VaR, Monte Carlo, stochastic calculus
   - Emphasize: mathematics background, financial modeling, performance metrics (Sharpe, drawdown, PnL)

   **For Data Science roles:**
   - Emphasize: ML models, A/B testing, feature engineering, model deployment
   - Keywords: accuracy, AUC, precision/recall, production ML, ETL

   **For Data Engineering roles:**
   - Emphasize: pipeline design, data warehousing, scalability, ETL/ELT
   - Keywords: Spark, Airflow, dbt, data lake, batch/streaming

   **For ML Engineering roles:**
   - Emphasize: model serving, MLOps, infrastructure, latency optimization
   - Keywords: TensorFlow Serving, Kubernetes, model monitoring, A/B testing

   **For Business Analyst (BA) roles:**
   - Emphasize: requirements gathering, stakeholder management, process optimization, data-driven insights
   - Reframe technical projects: "Built ML model" → "Analyzed customer data to identify $2M revenue opportunity"
   - Keywords: SQL, Tableau, Power BI, user stories, process mapping, KPIs, ROI analysis
   - Add business context to technical work: impact on revenue, cost savings, efficiency gains

   **For Product Manager (PM) roles:**
   - Emphasize: product strategy, user research, roadmap planning, cross-functional leadership
   - Reframe: "Developed feature" → "Owned end-to-end product lifecycle, increasing user engagement by 40%"
   - Keywords: PRD, user stories, A/B testing, OKRs, sprint planning, stakeholder alignment
   - Focus on: user impact, business metrics, team collaboration

   **For Consultant roles:**
   - Emphasize: problem-solving, client management, strategic recommendations
   - Keywords: stakeholder engagement, business case, ROI, presentation skills, project management
   - Structure achievements: "Situation → Action → Result" format

   **For Finance/Accounting roles:**
   - Emphasize: financial modeling, budgeting, reporting, compliance
   - Keywords: Excel, financial statements, variance analysis, forecasting, audit

6. **STYLE CONSISTENCY**: When adding new content, match the resume's existing tone:
   - If resume focuses on DS/AI → emphasize ML, data analysis, model performance metrics
   - If resume focuses on engineering → emphasize system design, scalability, code quality
   - If resume focuses on product → emphasize user impact, business metrics, stakeholder management

OUTPUT PURE JSON ONLY. No markdown, no explanations."""

        # 构建用户提示词
        user_prompt = f"""# MISSION
Optimize the following resume for Hong Kong HR requirements.

# ORIGINAL RESUME
{resume_text[:4000]}

# ADDITIONAL INFORMATION (To be added if provided)
- Permanent Resident Status: {"Yes - Hong Kong Permanent Resident" if permanent_resident else "Check original resume for work eligibility status"}
- Availability: {"Available Immediately" if available_immediately else "Check original resume for availability status"}
- LinkedIn: {linkedin_url if linkedin_url else "Check original resume for LinkedIn URL"}
- GitHub: {github_url if github_url else "Check original resume for GitHub URL"}
- Portfolio: {portfolio_url if portfolio_url else "Check original resume for portfolio URL"}
- User Feedback / Layout Instructions: {additional_notes if additional_notes else "Not provided"}

# USER FEEDBACK HANDLING (CRITICAL - Apply if feedback provided):
You are a professional resume editor. The user may provide feedback in Chinese or English.
You MUST understand and execute their instructions precisely.

## 1. CONTENT OPERATIONS:
**删除/remove/delete** → Remove specified content completely
  - "删除这个项目" → Remove that project
  - "去掉实习经历" → Remove internship experiences

**新增/add/include** → Add new content
  - "加上Python技能" → Add Python to skills
  - "添加一段XX经历" → Add new experience entry

**修改/change/rewrite** → Modify existing content
  - "把Summary改成..." → Rewrite the summary
  - "重写这段经历" → Rewrite that experience

**合并/merge/combine** → Combine multiple items
  - "把这两个项目合并" → Merge two projects into one

## 2. ORDER OPERATIONS:
**移动/move/放到** → Reorder sections or items
  - "把Projects移到Experience前面" → Move projects before experience
  - "Education放到最后" → Put education at the end
  - "把第3个bullet放到第一个" → Reorder bullets within an entry

**交换/swap** → Swap positions
  - "交换Skills和Projects" → Swap these two sections

**置顶/放最前** → Move to top
  - "最近的工作放最前面" → Most recent job first

## 3. LENGTH OPERATIONS:
**扩展/expand/详细/写长一点** → Add more details
  - "这部分写详细一点" → Expand with more bullets/details
  - "第一页太空了" → Add more content overall

**精简/shorten/压缩/简化** → Reduce length
  - "这段太长了" → Shorten this section
  - "第二页太满了" → Reduce content overall
  - "每个经历只保留3个bullet" → Limit bullets per entry

**平衡/balance** → Distribute content evenly
  - "平衡两页内容" → Balance content across pages

## 4. STYLE OPERATIONS:
**突出/highlight/强调** → Emphasize certain aspects
  - "突出数据分析能力" → Emphasize data analysis skills
  - "强调领导力" → Highlight leadership

**弱化/downplay** → De-emphasize
  - "不要太强调这个" → Reduce emphasis on this

**针对/tailor/优化给** → Customize for specific job
  - "针对这个JD优化" → Tailor for the job description

## 5. DETAIL OPERATIONS:
**改日期/update date** → Change dates
  - "把日期改成2023-2024" → Update date range

**改名称/rename** → Change names
  - "公司名用全称" → Use full company name

**改顺序/reorder bullets** → Reorder items within a section
  - "把最重要的成就放第一个" → Put most important achievement first

# REQUIRED OUTPUT SCHEMA (Strict JSON)
{{
    "name": "Full Name from resume",
    "email": "Email from resume",
    "phone": "Phone from resume",
    "linkedin": "{linkedin_url if linkedin_url else ''}",
    "github": "{github_url if github_url else ''}",
    "portfolio": "{portfolio_url if portfolio_url else ''}",
    "work_eligibility": "{('Hong Kong Permanent Resident - No work visa required' if permanent_resident else 'Requires work visa sponsorship')}",
    "availability": "{('Available immediately' if available_immediately else 'Available with notice period')}",
    "summary": "Professional summary (2-3 sentences highlighting key strengths and experience)",
    "experience": [
        {{
            "title": "Job Title",
            "company": "Company Name",
            "location": "Location",
            "date": "Date Range (e.g., Jan 2024 - Present)",
            "bullets": [
                "Achievement with quantifiable impact (e.g., Increased sales by 30%)",
                "Responsibility with action verb (e.g., Led team of 5 developers)"
            ]
        }}
    ],
    "skills": [
        {{"name": "Technical Skills", "keywords": ["Skill1", "Skill2"]}},
        {{"name": "Languages", "keywords": ["English (Native)", "Cantonese (Fluent)"]}}
    ],
    "education": {{
        "university": "University Name",
        "degree": "Degree Name",
        "date": "Graduation Date",
        "honors": "Honors/GPA if impressive"
    }},
    "projects": [
        {{
            "name": "Project Name",
            "date": "Project Date",
            "bullets": ["Project achievement or description"]
        }}
    ],
    "certifications": ["Certification 1", "Certification 2"],
    "additional_info": "{additional_notes if additional_notes else ''}"
}}

# CRITICAL REQUIREMENTS:

1. **Work Eligibility**: Must include clear statement about work permit status
2. **Availability**: Must state availability clearly
3. **Contact Information**:
   - Use provided LinkedIn URL if given: {linkedin_url}
   - Use provided GitHub URL if given: {github_url}
   - Use provided Portfolio URL if given: {portfolio_url}
   - If not provided, use empty string ""
4. **Date Fields**: Every experience and project MUST have specific dates
5. **Quantifiable Achievements**: Add metrics where possible (%, $, time saved, etc.)
6. **Action Verbs**: Start each bullet with strong action verbs
7. **ATS-Friendly**: Use standard section names and clean formatting

OUTPUT ONLY THE JSON. NO EXPLANATIONS."""

        # 调用 AI
        logger.info("📡 Calling LLM for resume optimization...")
        result = self._call_ai(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4000,
            prefill="{",
            temperature=0
        )

        if result:
            logger.info("✅ Resume optimization successful")

            # 🔴 强制覆盖用户明确提供的字段（LLM 可能会忽略）
            # 🔴 自动补全 URL 前缀
            def normalize_url(url: str) -> str:
                if not url:
                    return ""
                url = url.strip()
                if url and not url.startswith(("http://", "https://")):
                    return f"https://{url}"
                return url

            if linkedin_url:
                result["linkedin"] = normalize_url(linkedin_url)
                logger.info(f"✅ 强制设置 LinkedIn: {result['linkedin']}")
            if github_url:
                result["github"] = normalize_url(github_url)
                logger.info(f"✅ 强制设置 GitHub: {result['github']}")
            if portfolio_url:
                result["portfolio"] = normalize_url(portfolio_url)
                logger.info(f"✅ 强制设置 Portfolio: {result['portfolio']}")
            if permanent_resident:
                result["work_eligibility"] = "Hong Kong Permanent Resident - No work visa required"
            if available_immediately:
                result["availability"] = "Available immediately"

            return result
        else:
            logger.error("❌ Resume optimization failed")
            return None
