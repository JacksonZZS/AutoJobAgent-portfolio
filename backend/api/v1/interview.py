"""
面试题库 API - AI 生成面试题目和答案
支持 JD 链接抓取 + 结合简历生成个性化面试题
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import os
import json
import re

from backend.api.v1.auth import get_current_user
from backend.models.schemas import UserInfo

router = APIRouter(prefix="/interview", tags=["Interview"])


# ==================== 数据模型 ====================

class FetchJDRequest(BaseModel):
    """抓取 JD 请求"""
    url: str = Field(..., description="职位链接")


class FetchJDResponse(BaseModel):
    """抓取 JD 响应"""
    success: bool
    job_title: str = ""
    company: str = ""
    job_description: str = ""
    error: Optional[str] = None


class GenerateQuestionsRequest(BaseModel):
    """生成面试题请求"""
    job_title: str = Field(..., description="职位名称")
    company: Optional[str] = Field(None, description="公司名称")
    job_description: Optional[str] = Field(None, description="职位描述")
    resume_id: Optional[str] = Field(None, description="简历ID，用于生成针对性问题")
    question_types: List[str] = Field(
        default=["technical", "behavioral", "situational"],
        description="题目类型"
    )
    difficulty: str = Field("medium", description="难度: easy/medium/hard")
    count: int = Field(10, ge=5, le=30, description="题目数量")


class InterviewQuestion(BaseModel):
    """面试题目"""
    id: int
    category: str  # technical, behavioral, situational, resume_based
    question: str
    suggested_answer: str
    tips: List[str]
    difficulty: str


class GenerateQuestionsResponse(BaseModel):
    """生成面试题响应"""
    job_title: str
    total_questions: int
    questions: List[InterviewQuestion]
    resume_used: bool = False


class AnswerFeedbackRequest(BaseModel):
    """答案反馈请求"""
    question_id: int
    user_answer: str
    question: str


class AnswerFeedbackResponse(BaseModel):
    """答案反馈响应"""
    score: int  # 0-100
    strengths: List[str]
    improvements: List[str]
    better_answer: str


# ==================== LLM 集成 ====================

async def call_claude_api(prompt: str) -> str:
    """
    调用 Claude API
    """
    try:
        import anthropic

        client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text
    except Exception as e:
        print(f"Claude API 调用失败: {e}")
        return ""


def parse_json_response(response: str) -> dict:
    """
    4层容错 JSON 解析
    """
    # Layer 1: 标准解析
    try:
        return json.loads(response)
    except:
        pass

    # Layer 2: 修复常见问题
    fixed = response.replace("'", '"')
    fixed = re.sub(r',\s*}', '}', fixed)
    fixed = re.sub(r',\s*]', ']', fixed)
    fixed = re.sub(r'\bTrue\b', 'true', fixed)
    fixed = re.sub(r'\bFalse\b', 'false', fixed)
    try:
        return json.loads(fixed)
    except:
        pass

    # Layer 3: 正则提取
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            pass

    brace_match = re.search(r'\{[\s\S]*\}', response)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except:
            pass

    # Layer 4: 返回空
    return {}


# ==================== JD 抓取 ====================

async def fetch_jd_from_url(url: str) -> dict:
    """
    从 URL 抓取职位描述
    支持 Indeed, LinkedIn, JobsDB
    """
    try:
        # 判断平台
        if "indeed" in url.lower():
            return await fetch_indeed_jd(url)
        elif "linkedin" in url.lower():
            return await fetch_linkedin_jd(url)
        elif "jobsdb" in url.lower():
            return await fetch_jobsdb_jd(url)
        else:
            # 通用抓取
            return await fetch_generic_jd(url)
    except Exception as e:
        return {"success": False, "error": str(e)}


async def fetch_indeed_jd(url: str) -> dict:
    """抓取 Indeed JD"""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # 提取信息
            title = await page.query_selector('h1.jobsearch-JobInfoHeader-title')
            company = await page.query_selector('[data-testid="inlineHeader-companyName"]')
            description = await page.query_selector('#jobDescriptionText')

            result = {
                "success": True,
                "job_title": await title.inner_text() if title else "",
                "company": await company.inner_text() if company else "",
                "job_description": await description.inner_text() if description else ""
            }

            await browser.close()
            return result
    except Exception as e:
        return {"success": False, "error": f"Indeed 抓取失败: {str(e)}"}


async def fetch_linkedin_jd(url: str) -> dict:
    """抓取 LinkedIn JD"""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            title = await page.query_selector('.top-card-layout__title')
            company = await page.query_selector('.top-card-layout__second-subline a')
            description = await page.query_selector('.description__text')

            result = {
                "success": True,
                "job_title": await title.inner_text() if title else "",
                "company": await company.inner_text() if company else "",
                "job_description": await description.inner_text() if description else ""
            }

            await browser.close()
            return result
    except Exception as e:
        return {"success": False, "error": f"LinkedIn 抓取失败: {str(e)}"}


async def fetch_jobsdb_jd(url: str) -> dict:
    """抓取 JobsDB JD"""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            title = await page.query_selector('h1[data-automation="job-detail-title"]')
            company = await page.query_selector('[data-automation="advertiser-name"]')
            description = await page.query_selector('[data-automation="jobDescription"]')

            result = {
                "success": True,
                "job_title": await title.inner_text() if title else "",
                "company": await company.inner_text() if company else "",
                "job_description": await description.inner_text() if description else ""
            }

            await browser.close()
            return result
    except Exception as e:
        return {"success": False, "error": f"JobsDB 抓取失败: {str(e)}"}


async def fetch_generic_jd(url: str) -> dict:
    """通用网页抓取"""
    try:
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')

            # 尝试提取标题
            title = soup.find('h1')

            # 尝试提取正文
            body = soup.find('body')
            text = body.get_text(separator='\n', strip=True) if body else ""

            return {
                "success": True,
                "job_title": title.get_text(strip=True) if title else "",
                "company": "",
                "job_description": text[:5000]  # 限制长度
            }
    except Exception as e:
        return {"success": False, "error": f"抓取失败: {str(e)}"}


# ==================== 简历读取 ====================

async def get_resume_content(user_id: str, resume_id: Optional[str] = None) -> Optional[str]:
    """
    获取用户简历内容
    """
    from pathlib import Path
    import pdfplumber

    # 查找简历文件
    resumes_dir = Path(f"data/uploads/{user_id}")
    if not resumes_dir.exists():
        return None

    # 如果指定了 resume_id，查找对应简历
    # 否则使用默认简历或最新上传的
    resume_files = list(resumes_dir.glob("*.pdf"))
    if not resume_files:
        return None

    # 使用最新的简历
    resume_path = max(resume_files, key=lambda p: p.stat().st_mtime)

    # 解析 PDF
    try:
        with pdfplumber.open(resume_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            return text
    except Exception as e:
        print(f"解析简历失败: {e}")
        return None


# ==================== AI 生成函数 ====================

INTERVIEW_PROMPT_WITH_RESUME = """
你是一位资深的技术面试官和HR专家。请根据以下信息生成面试题目：

## 职位信息
- 职位：{job_title}
- 公司：{company}
- 职位描述：
{job_description}

## 候选人简历
{resume_content}

## 要求
请生成 {count} 道面试题，包含以下类型：
1. 技术题 (technical): 根据职位要求和简历中的技术栈，考察专业技能
2. 行为题 (behavioral): 根据简历中的项目经历，深入追问细节
3. 情景题 (situational): 考察解决问题的能力
4. 简历相关题 (resume_based): 针对简历中具体项目/经历的追问

难度级别：{difficulty}

## 输出格式
请返回 JSON 格式，结构如下：
```json
{{
    "questions": [
        {{
            "category": "technical|behavioral|situational|resume_based",
            "question": "问题内容",
            "suggested_answer": "建议答案（300字以内）",
            "tips": ["技巧1", "技巧2", "技巧3"]
        }}
    ]
}}
```

请确保问题与候选人的实际经历相关，而不是泛泛的模板问题。
"""

INTERVIEW_PROMPT_WITHOUT_RESUME = """
你是一位资深的技术面试官和HR专家。请根据以下职位信息生成面试题目：

## 职位信息
- 职位：{job_title}
- 公司：{company}
- 职位描述：
{job_description}

## 要求
请生成 {count} 道面试题，包含以下类型：
1. 技术题 (technical): 考察专业技能和知识
2. 行为题 (behavioral): 考察过往经历和行为模式
3. 情景题 (situational): 考察解决问题的能力

难度级别：{difficulty}

## 输出格式
请返回 JSON 格式，结构如下：
```json
{{
    "questions": [
        {{
            "category": "technical|behavioral|situational",
            "question": "问题内容",
            "suggested_answer": "建议答案（300字以内）",
            "tips": ["技巧1", "技巧2", "技巧3"]
        }}
    ]
}}
```
"""

EVALUATE_ANSWER_PROMPT = """
你是一位资深面试官，请评估以下面试回答：

## 面试问题
{question}

## 候选人回答
{user_answer}

## 评估要求
请从以下维度评估：
1. 内容完整性
2. 结构清晰度
3. 具体案例支撑
4. 专业术语使用
5. 表达流畅度

## 输出格式
请返回 JSON 格式：
```json
{{
    "score": 0-100的分数,
    "strengths": ["优点1", "优点2", "优点3"],
    "improvements": ["改进建议1", "改进建议2", "改进建议3"],
    "better_answer": "优化后的参考答案"
}}
```
"""


async def generate_interview_questions(
    job_title: str,
    company: Optional[str],
    job_description: Optional[str],
    question_types: List[str],
    difficulty: str,
    count: int,
    resume_content: Optional[str] = None
) -> tuple[List[InterviewQuestion], bool]:
    """
    AI 生成面试题
    返回 (问题列表, 是否使用了简历)
    """
    # 构建 Prompt
    if resume_content:
        prompt = INTERVIEW_PROMPT_WITH_RESUME.format(
            job_title=job_title,
            company=company or "未知",
            job_description=job_description or "无详细描述",
            resume_content=resume_content[:3000],  # 限制长度
            count=count,
            difficulty=difficulty
        )
        resume_used = True
    else:
        prompt = INTERVIEW_PROMPT_WITHOUT_RESUME.format(
            job_title=job_title,
            company=company or "未知",
            job_description=job_description or "无详细描述",
            count=count,
            difficulty=difficulty
        )
        resume_used = False

    # 调用 Claude API
    response = await call_claude_api(prompt)

    if response:
        parsed = parse_json_response(response)
        if parsed and "questions" in parsed:
            questions = []
            for i, q in enumerate(parsed["questions"][:count], 1):
                questions.append(InterviewQuestion(
                    id=i,
                    category=q.get("category", "technical"),
                    question=q.get("question", ""),
                    suggested_answer=q.get("suggested_answer", ""),
                    tips=q.get("tips", []),
                    difficulty=difficulty
                ))
            return questions, resume_used

    # 如果 AI 调用失败，返回模板问题
    return generate_fallback_questions(job_title, question_types, difficulty, count), False


def generate_fallback_questions(
    job_title: str,
    question_types: List[str],
    difficulty: str,
    count: int
) -> List[InterviewQuestion]:
    """
    备用模板问题（当 AI 调用失败时）
    """
    questions = []
    question_id = 1

    tech_questions = [
        {
            "question": f"请描述一下你在{job_title}相关项目中使用过的技术栈？",
            "answer": "我在过往项目中主要使用了Python/JavaScript技术栈。后端使用FastAPI框架，前端使用React + TypeScript。数据库方面熟悉PostgreSQL和MongoDB。",
            "tips": ["具体描述项目背景", "突出技术选型理由", "强调解决的问题"]
        },
        {
            "question": "如何处理高并发场景下的性能优化？",
            "answer": "高并发优化可以从多个层面入手：1) 数据库层面：使用索引、读写分离、缓存；2) 应用层面：异步处理、连接池、限流；3) 架构层面：负载均衡、微服务拆分、CDN。",
            "tips": ["分层次回答", "结合实际经验", "提及具体工具"]
        }
    ]

    behavioral_questions = [
        {
            "question": "请分享一个你在团队中解决冲突的经历？",
            "answer": "在之前的项目中，团队成员对技术方案有分歧。我主动组织了技术评审会议，让各方充分表达观点，最终团队达成共识。",
            "tips": ["使用STAR法则", "强调你的角色", "总结学到的经验"]
        }
    ]

    situational_questions = [
        {
            "question": "如果你发现代码中有一个可能影响用户数据的bug，但修复需要较长时间，你会怎么做？",
            "answer": "首先评估bug的影响范围和严重程度。如果涉及数据安全，会立即上报并考虑临时下线相关功能。",
            "tips": ["强调安全意识", "展示决策能力", "提及预防措施"]
        }
    ]

    if "technical" in question_types:
        for q in tech_questions:
            questions.append(InterviewQuestion(
                id=question_id,
                category="technical",
                question=q["question"],
                suggested_answer=q["answer"],
                tips=q["tips"],
                difficulty=difficulty
            ))
            question_id += 1

    if "behavioral" in question_types:
        for q in behavioral_questions:
            questions.append(InterviewQuestion(
                id=question_id,
                category="behavioral",
                question=q["question"],
                suggested_answer=q["answer"],
                tips=q["tips"],
                difficulty=difficulty
            ))
            question_id += 1

    if "situational" in question_types:
        for q in situational_questions:
            questions.append(InterviewQuestion(
                id=question_id,
                category="situational",
                question=q["question"],
                suggested_answer=q["answer"],
                tips=q["tips"],
                difficulty=difficulty
            ))
            question_id += 1

    return questions[:count]


async def evaluate_answer(question: str, user_answer: str) -> dict:
    """
    AI 评估用户答案
    """
    prompt = EVALUATE_ANSWER_PROMPT.format(
        question=question,
        user_answer=user_answer
    )

    response = await call_claude_api(prompt)

    if response:
        parsed = parse_json_response(response)
        if parsed and "score" in parsed:
            return parsed

    # 备用评估
    return {
        "score": 70,
        "strengths": [
            "回答结构较清晰",
            "有一定的逻辑性"
        ],
        "improvements": [
            "可以增加更多具体案例",
            "建议使用STAR法则组织回答",
            "可以补充量化数据"
        ],
        "better_answer": f"建议在回答中补充具体的数据和结果，使用STAR法则（情境-任务-行动-结果）来组织答案，这样会更有说服力。"
    }


# ==================== API 端点 ====================

@router.post("/fetch-jd", response_model=FetchJDResponse)
async def fetch_job_description(
    request: FetchJDRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    从 URL 抓取职位描述
    支持 Indeed, LinkedIn, JobsDB
    """
    result = await fetch_jd_from_url(request.url)

    return FetchJDResponse(
        success=result.get("success", False),
        job_title=result.get("job_title", ""),
        company=result.get("company", ""),
        job_description=result.get("job_description", ""),
        error=result.get("error")
    )


@router.post("/generate", response_model=GenerateQuestionsResponse)
async def generate_questions(
    request: GenerateQuestionsRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    根据职位信息生成面试题
    如果提供 resume_id，会结合简历生成针对性问题
    """
    # 获取简历内容
    resume_content = None
    if request.resume_id:
        resume_content = await get_resume_content(
            str(current_user.id),
            request.resume_id
        )

    questions, resume_used = await generate_interview_questions(
        job_title=request.job_title,
        company=request.company,
        job_description=request.job_description,
        question_types=request.question_types,
        difficulty=request.difficulty,
        count=request.count,
        resume_content=resume_content
    )

    return GenerateQuestionsResponse(
        job_title=request.job_title,
        total_questions=len(questions),
        questions=questions,
        resume_used=resume_used
    )


@router.post("/evaluate", response_model=AnswerFeedbackResponse)
async def evaluate_user_answer(
    request: AnswerFeedbackRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    AI 评估用户的答案
    """
    if not request.user_answer.strip():
        raise HTTPException(status_code=400, detail="答案不能为空")

    result = await evaluate_answer(
        question=request.question,
        user_answer=request.user_answer
    )

    return AnswerFeedbackResponse(
        score=result["score"],
        strengths=result["strengths"],
        improvements=result["improvements"],
        better_answer=result["better_answer"]
    )


@router.get("/categories")
async def get_question_categories():
    """
    获取支持的题目类型
    """
    return {
        "categories": [
            {"id": "technical", "name": "技术题", "description": "考察专业技能和技术知识"},
            {"id": "behavioral", "name": "行为题", "description": "考察过往经历和行为模式"},
            {"id": "situational", "name": "情景题", "description": "考察解决问题和决策能力"},
            {"id": "resume_based", "name": "简历相关", "description": "针对简历内容的深入追问"}
        ],
        "difficulties": [
            {"id": "easy", "name": "初级"},
            {"id": "medium", "name": "中级"},
            {"id": "hard", "name": "高级"}
        ]
    }
