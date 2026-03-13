# core/market_analyzer.py
"""
Market Intelligence Analyzer
Regex-based extraction of skills, salary, location from job data.
No LLM calls -- pure pattern matching and aggregation.
"""

import re
from collections import Counter, defaultdict
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta


# ============================================================
# Skills Dictionary (~120 skills, organized by category)
# ============================================================

SKILLS_DICTIONARY: Dict[str, List[str]] = {
    "Programming": [
        "Python", "SQL", "Java", "JavaScript", "TypeScript", "C++", "C#",
        "Go", "Rust", "Scala", "Ruby", "PHP", "Swift", "Kotlin",
        "Shell", "Bash", "MATLAB", "SAS", "VBA", "Perl",
    ],
    "Data & ML": [
        "Machine Learning", "Deep Learning", "NLP",
        "Natural Language Processing", "Computer Vision",
        "TensorFlow", "PyTorch", "Scikit-learn", "Keras",
        "XGBoost", "LightGBM", "Random Forest",
        "Neural Network", "Reinforcement Learning",
        "LLM", "Large Language Model", "GenAI", "Generative AI",
        "RAG", "Fine-tuning", "Prompt Engineering",
        "Feature Engineering", "A/B Testing",
    ],
    "Data Tools": [
        "Excel", "Tableau", "Power BI", "Looker", "Qlik",
        "Jupyter", "Pandas", "NumPy", "Matplotlib", "Seaborn",
        "Spark", "Hadoop", "Airflow", "dbt", "Databricks",
        "ETL", "Data Pipeline", "Data Warehouse",
        "Google Analytics", "Mixpanel", "Amplitude",
    ],
    "Cloud & DevOps": [
        "AWS", "GCP", "Azure", "Docker", "Kubernetes",
        "Terraform", "CI/CD", "Jenkins", "GitHub Actions",
        "Linux", "Nginx", "Serverless", "Lambda",
        "CloudFormation", "Ansible",
    ],
    "Databases": [
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "DynamoDB", "Cassandra", "SQLite", "Oracle", "SQL Server",
        "Snowflake", "BigQuery", "Redshift", "Clickhouse",
        "Neo4j", "Supabase", "Firebase",
    ],
    "Frameworks": [
        "React", "Next.js", "Vue", "Angular", "Node.js",
        "Django", "Flask", "FastAPI", "Spring", "Express",
        "Playwright", "Selenium", "GraphQL", "REST API",
        "Tailwind", "Bootstrap",
    ],
    "Soft Skills": [
        "Agile", "Scrum", "Kanban", "Jira",
        "Communication", "Leadership", "Teamwork",
        "Problem Solving", "Critical Thinking",
        "Project Management", "Stakeholder Management",
    ],
}

# Pre-compile regex patterns for each skill
_SKILL_PATTERNS: List[tuple] = []


def _build_skill_patterns():
    """Build word-boundary regex patterns for each skill."""
    global _SKILL_PATTERNS
    if _SKILL_PATTERNS:
        return

    for category, skills in SKILLS_DICTIONARY.items():
        for skill in skills:
            # Special handling for short/ambiguous skills
            if skill == "R":
                # Avoid matching React, Redis, Ruby, REST, etc.
                pattern = re.compile(
                    r'\bR\b(?!\s*(?:eact|edis|uby|ails|ust|EST|andom))',
                    re.IGNORECASE
                )
            elif skill == "Go":
                pattern = re.compile(
                    r'\bGo(?:lang)?\b(?!\s*(?:ogle|od|ing|al))',
                    re.IGNORECASE
                )
            elif skill == "C#":
                pattern = re.compile(r'\bC#\b', re.IGNORECASE)
            elif skill == "C++":
                pattern = re.compile(r'\bC\+\+\b', re.IGNORECASE)
            elif skill == "Node.js":
                pattern = re.compile(r'\bNode\.?js\b', re.IGNORECASE)
            elif skill == "Next.js":
                pattern = re.compile(r'\bNext\.?js\b', re.IGNORECASE)
            elif skill == "CI/CD":
                pattern = re.compile(r'\bCI\s*/\s*CD\b', re.IGNORECASE)
            elif skill == "A/B Testing":
                pattern = re.compile(r'\bA\s*/\s*B\s+[Tt]est', re.IGNORECASE)
            elif skill == "REST API":
                pattern = re.compile(r'\bREST(?:ful)?\s*API\b', re.IGNORECASE)
            elif len(skill) <= 3:
                # Short skills need strict word boundary
                pattern = re.compile(
                    r'\b' + re.escape(skill) + r'\b', re.IGNORECASE
                )
            else:
                pattern = re.compile(
                    r'\b' + re.escape(skill) + r'\b', re.IGNORECASE
                )
            _SKILL_PATTERNS.append((skill, category, pattern))


# ============================================================
# Salary Extraction Patterns
# ============================================================

SALARY_PATTERNS = [
    # HK$XX,XXX - HK$YY,YYY per month
    (re.compile(
        r'HK\$\s*([\d,]+)\s*[-–~to]+\s*HK\$\s*([\d,]+)\s*(?:per\s+month|/\s*month|monthly)?',
        re.IGNORECASE
    ), "HKD", "monthly"),
    # HK$XXK - HK$YYK
    (re.compile(
        r'HK\$\s*(\d+(?:\.\d+)?)\s*[Kk]\s*[-–~to]+\s*(?:HK\$\s*)?(\d+(?:\.\d+)?)\s*[Kk]',
        re.IGNORECASE
    ), "HKD", "monthly_k"),
    # $XXK - $YYK (default HKD)
    (re.compile(
        r'(?<!\w)\$\s*(\d+(?:\.\d+)?)\s*[Kk]\s*[-–~to]+\s*\$?\s*(\d+(?:\.\d+)?)\s*[Kk]',
        re.IGNORECASE
    ), "HKD", "monthly_k"),
    # $XX,XXX - $YY,YYY
    (re.compile(
        r'(?<!\w)\$\s*([\d,]+)\s*[-–~to]+\s*\$?\s*([\d,]+)',
        re.IGNORECASE
    ), "HKD", "monthly"),
    # ~$XXK or $XXK+
    (re.compile(
        r'[~～]?\s*\$?\s*(\d+(?:\.\d+)?)\s*[Kk]\s*\+?',
        re.IGNORECASE
    ), "HKD", "monthly_k_single"),
    # XXK+ (without dollar sign, common in titles)
    (re.compile(
        r'(?<!\d)(\d{2,3})\s*[Kk]\s*\+',
        re.IGNORECASE
    ), "HKD", "monthly_k_single"),
    # Chinese: 月薪 XX,XXX - YY,YYY
    (re.compile(
        r'月薪\s*([\d,]+)\s*[-–~至到]+\s*([\d,]+)',
    ), "HKD", "monthly"),
    # Chinese: 年薪 XXX,XXX - YYY,YYY
    (re.compile(
        r'年薪\s*([\d,]+)\s*[-–~至到]+\s*([\d,]+)',
    ), "HKD", "annual"),
]


# ============================================================
# Extraction Functions
# ============================================================

def extract_skills(text: str) -> List[str]:
    """
    Match text against SKILLS_DICTIONARY using word-boundary regex.
    Returns deduplicated list of matched skill names.
    """
    if not text:
        return []

    _build_skill_patterns()
    found = []
    seen = set()

    for skill_name, _category, pattern in _SKILL_PATTERNS:
        if skill_name.lower() not in seen and pattern.search(text):
            found.append(skill_name)
            seen.add(skill_name.lower())

    return found


def extract_skills_with_category(text: str) -> List[Dict[str, str]]:
    """
    Extract skills with their category.
    Returns: [{"skill": "Python", "category": "Programming"}, ...]
    """
    if not text:
        return []

    _build_skill_patterns()
    found = []
    seen = set()

    for skill_name, category, pattern in _SKILL_PATTERNS:
        if skill_name.lower() not in seen and pattern.search(text):
            found.append({"skill": skill_name, "category": category})
            seen.add(skill_name.lower())

    return found


def extract_salary(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract salary range from JD text or title.
    Returns: {"min": 18000, "max": 25000, "currency": "HKD",
              "period": "monthly", "raw": "HK$18,000 - HK$25,000"}
    """
    if not text:
        return None

    for pattern, currency, period_type in SALARY_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue

        try:
            if period_type == "monthly_k":
                sal_min = float(match.group(1)) * 1000
                sal_max = float(match.group(2)) * 1000
                period = "monthly"
            elif period_type == "monthly_k_single":
                sal_val = float(match.group(1)) * 1000
                sal_min = sal_val
                sal_max = sal_val
                period = "monthly"
            elif period_type == "annual":
                sal_min = float(match.group(1).replace(",", ""))
                sal_max = float(match.group(2).replace(",", ""))
                period = "annual"
            else:
                sal_min = float(match.group(1).replace(",", ""))
                sal_max = float(match.group(2).replace(",", "")) if match.lastindex >= 2 else sal_min
                period = "monthly"

            # Sanity checks
            if sal_min <= 0 or sal_max <= 0:
                continue
            if sal_min > 10_000_000 or sal_max > 10_000_000:
                continue
            if sal_max < sal_min:
                sal_min, sal_max = sal_max, sal_min

            return {
                "min": sal_min,
                "max": sal_max,
                "currency": currency,
                "period": period,
                "raw": match.group(0).strip(),
            }
        except (ValueError, IndexError):
            continue

    return None


def detect_platform(link: str) -> str:
    """Detect job platform from URL."""
    if not link:
        return "unknown"
    link_lower = link.lower()
    if "indeed.com" in link_lower:
        return "indeed"
    if "jobsdb.com" in link_lower:
        return "jobsdb"
    if "linkedin.com" in link_lower:
        return "linkedin"
    return "unknown"


def extract_job_type(title: str) -> str:
    """Classify job into broad categories from title."""
    if not title:
        return "Other"

    title_lower = title.lower()
    patterns = [
        (r'\bdata\s+analyst', "Data Analyst"),
        (r'\bdata\s+scien', "Data Scientist"),
        (r'\bdata\s+engineer', "Data Engineer"),
        (r'\bmachine\s+learn|ml\s+engineer', "ML Engineer"),
        (r'\bai\s+engineer|artificial\s+intellig', "AI Engineer"),
        (r'\bbusiness\s+analyst|bi\s+analyst', "Business Analyst"),
        (r'\bsoftware\s+engineer|software\s+develop', "Software Engineer"),
        (r'\bfull\s*stack|fullstack', "Full Stack Developer"),
        (r'\bfrontend|front\s*end|react|vue\s+develop', "Frontend Developer"),
        (r'\bbackend|back\s*end', "Backend Developer"),
        (r'\bdevops|sre|site\s+reliab', "DevOps/SRE"),
        (r'\bproduct\s+manager|pm\b', "Product Manager"),
        (r'\bproject\s+manager|project\s+coord', "Project Manager"),
        (r'\bqa|quality\s+assur|test\s+engineer', "QA Engineer"),
        (r'\bsecurity|cyber|infosec', "Security Engineer"),
        (r'\bcloud\s+engineer|cloud\s+arch', "Cloud Engineer"),
        (r'\bnlp|natural\s+language', "NLP Engineer"),
        (r'\banalyst', "Analyst"),
        (r'\bengineer|developer|programmer', "Engineer"),
    ]

    for pattern, job_type in patterns:
        if re.search(pattern, title_lower):
            return job_type

    return "Other"


def extract_job_level(title: str) -> str:
    """Extract seniority level from job title."""
    if not title:
        return "Unspecified"

    title_lower = title.lower()
    patterns = [
        (r'\bintern\b', "Intern"),
        (r'\bjunior\b|\bjr\.?\b|\bentry[\s-]?level\b|\bgraduate\b|\bgrad\b', "Junior"),
        (r'\bsenior\b|\bsr\.?\b|\blead\b|\bprincipal\b|\bstaff\b', "Senior"),
        (r'\bmanager\b|\bdirector\b|\bhead\s+of\b|\bvp\b|\bchief\b', "Manager+"),
    ]

    for pattern, level in patterns:
        if re.search(pattern, title_lower):
            return level

    return "Mid"


# ============================================================
# Aggregation Functions
# ============================================================

def aggregate_skill_demand(jobs: List[Dict]) -> List[Dict]:
    """
    Aggregate skills across all jobs with JD content.
    Returns top 20 skills sorted by count.
    """
    skill_counter: Dict[str, int] = Counter()
    skill_category: Dict[str, str] = {}

    for job in jobs:
        # Use pre-extracted skills if available
        skills = job.get("extracted_skills")
        if skills:
            for s in skills:
                skill_counter[s] += 1
        elif job.get("jd_content"):
            for item in extract_skills_with_category(job["jd_content"]):
                skill_counter[item["skill"]] += 1
                skill_category[item["skill"]] = item["category"]

    # Build category lookup
    if not skill_category:
        for category, skills in SKILLS_DICTIONARY.items():
            for skill in skills:
                skill_category[skill] = category

    result = [
        {
            "skill": skill,
            "count": count,
            "category": skill_category.get(skill, "Other"),
        }
        for skill, count in skill_counter.most_common(20)
    ]
    return result


def aggregate_skills_by_job_type(jobs: List[Dict]) -> List[Dict]:
    """
    Cross-tabulate: for each job type, which skills appear and how often.
    Groups skills by category. Only includes job types with >= 2 jobs.
    """
    # Build category lookup
    skill_to_category: Dict[str, str] = {}
    for category, skills in SKILLS_DICTIONARY.items():
        for skill in skills:
            skill_to_category[skill] = category

    # Group jobs by type
    type_jobs: Dict[str, List[Dict]] = defaultdict(list)
    for job in jobs:
        job_type = extract_job_type(job.get("title", ""))
        if job_type != "Other":
            type_jobs[job_type].append(job)

    result = []
    for job_type, jt_jobs in sorted(
        type_jobs.items(), key=lambda x: len(x[1]), reverse=True
    ):
        if len(jt_jobs) < 2:
            continue

        # Count skills across all jobs of this type
        skill_counter: Dict[str, int] = Counter()
        for job in jt_jobs:
            skills = job.get("extracted_skills")
            if skills:
                for s in skills:
                    skill_counter[s] += 1
            elif job.get("jd_content"):
                for s in extract_skills(job["jd_content"]):
                    skill_counter[s] += 1

        if not skill_counter:
            continue

        # Organize by category
        cat_skills: Dict[str, List[Dict]] = defaultdict(list)
        for skill, count in skill_counter.most_common():
            cat = skill_to_category.get(skill, "Other")
            cat_skills[cat].append({"skill": skill, "count": count})

        # Top 5 per category, sort categories by total count
        categories = []
        for cat, skills_list in cat_skills.items():
            top_skills = skills_list[:5]
            cat_total = sum(s["count"] for s in top_skills)
            categories.append({
                "category": cat,
                "skills": top_skills,
                "total": cat_total,
            })
        categories.sort(key=lambda x: x["total"], reverse=True)

        # Remove helper "total" field
        for cat in categories:
            del cat["total"]

        result.append({
            "job_type": job_type,
            "total_jobs": len(jt_jobs),
            "categories": categories,
        })

    return result


def aggregate_salary_distribution(jobs: List[Dict]) -> List[Dict]:
    """Group salary data by job type."""
    salary_by_type: Dict[str, List[Dict]] = defaultdict(list)

    for job in jobs:
        job_type = extract_job_type(job.get("title", ""))
        salary = None

        # Try pre-extracted salary
        raw_salary = job.get("salary_raw")
        if raw_salary:
            salary = extract_salary(raw_salary)

        # Try from JD content
        if not salary and job.get("jd_content"):
            salary = extract_salary(job["jd_content"])

        # Try from title
        if not salary:
            salary = extract_salary(job.get("title", ""))

        if salary and salary["period"] == "monthly":
            salary_by_type[job_type].append(salary)

    result = []
    for job_type, salaries in sorted(
        salary_by_type.items(), key=lambda x: len(x[1]), reverse=True
    ):
        if len(salaries) < 1:
            continue
        min_vals = [s["min"] for s in salaries]
        max_vals = [s["max"] for s in salaries]
        result.append({
            "job_type": job_type,
            "min_avg": round(sum(min_vals) / len(min_vals), 0),
            "max_avg": round(sum(max_vals) / len(max_vals), 0),
            "count": len(salaries),
            "currency": "HKD",
        })

    return result


def aggregate_company_activity(jobs: List[Dict]) -> List[Dict]:
    """Top 15 most active hiring companies."""
    company_jobs: Dict[str, List[Dict]] = defaultdict(list)

    for job in jobs:
        company = job.get("company", "").strip()
        if company and company != "Unknown Company":
            company_jobs[company].append(job)

    result = []
    for company, c_jobs in sorted(
        company_jobs.items(), key=lambda x: len(x[1]), reverse=True
    )[:15]:
        scores = [j["score"] for j in c_jobs if j.get("score")]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        result.append({
            "company": company,
            "count": len(c_jobs),
            "avg_score": avg_score,
        })

    return result


def aggregate_title_trends(jobs: List[Dict]) -> List[Dict]:
    """Top 15 most common job types."""
    type_counter: Counter = Counter()

    for job in jobs:
        job_type = extract_job_type(job.get("title", ""))
        type_counter[job_type] += 1

    return [
        {"title": title, "count": count}
        for title, count in type_counter.most_common(15)
        if title != "Other"
    ]


def aggregate_location_distribution(jobs: List[Dict]) -> List[Dict]:
    """Location distribution."""
    loc_counter: Counter = Counter()

    for job in jobs:
        location = job.get("location", "").strip()
        if not location:
            # Try to extract from link
            link = job.get("link", "") or job.get("cleaned_link", "")
            if "hk." in link or "hong-kong" in link.lower():
                location = "Hong Kong"
            elif "sg." in link:
                location = "Singapore"
        if location:
            loc_counter[location] += 1

    total = sum(loc_counter.values()) or 1
    return [
        {
            "location": loc,
            "count": count,
            "percentage": round(count / total * 100, 1),
        }
        for loc, count in loc_counter.most_common(10)
    ]


def aggregate_score_distribution(jobs: List[Dict]) -> List[Dict]:
    """Score histogram in 10-point buckets."""
    buckets: Dict[str, int] = {}
    for start in range(0, 100, 10):
        end = start + 9 if start < 90 else 100
        buckets[f"{start}-{end}"] = 0

    for job in jobs:
        score = job.get("score")
        if score is not None:
            bucket_start = min((score // 10) * 10, 90)
            end = bucket_start + 9 if bucket_start < 90 else 100
            key = f"{bucket_start}-{end}"
            buckets[key] = buckets.get(key, 0) + 1

    return [
        {"range": r, "count": c}
        for r, c in buckets.items()
    ]


def aggregate_daily_trends(jobs: List[Dict], days: int = 30) -> List[Dict]:
    """Daily job volume over time."""
    cutoff = datetime.now() - timedelta(days=days)
    daily: Dict[str, List[Dict]] = defaultdict(list)

    for job in jobs:
        processed_at = job.get("processed_at", "")
        if not processed_at:
            continue
        try:
            dt = datetime.fromisoformat(processed_at)
            if dt >= cutoff:
                date_str = dt.strftime("%Y-%m-%d")
                daily[date_str].append(job)
        except (ValueError, TypeError):
            continue

    result = []
    current = cutoff
    while current <= datetime.now():
        date_str = current.strftime("%Y-%m-%d")
        day_jobs = daily.get(date_str, [])
        scores = [j["score"] for j in day_jobs if j.get("score")]
        result.append({
            "date": date_str,
            "new_jobs": len(day_jobs),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        })
        current += timedelta(days=1)

    return result


def aggregate_job_level_distribution(jobs: List[Dict]) -> List[Dict]:
    """Count jobs by seniority level (Intern/Junior/Mid/Senior/Manager+)."""
    level_counter: Dict[str, int] = Counter()
    for job in jobs:
        level = extract_job_level(job.get("title", ""))
        level_counter[level] += 1

    order = ["Intern", "Junior", "Mid", "Senior", "Manager+", "Unspecified"]
    return [
        {"level": lvl, "count": level_counter.get(lvl, 0)}
        for lvl in order
        if level_counter.get(lvl, 0) > 0
    ]


# ============================================================
# Main Analysis Entry Point
# ============================================================

def analyze_market(
    history_data: Dict[str, Dict],
    days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Main entry point. Takes raw history dict, runs all aggregations.

    Args:
        history_data: Raw dict from HistoryManager.history
        days: Optional filter for recent N days only
    """
    # Convert to list and optionally filter by date
    jobs = list(history_data.values())

    if days:
        cutoff = datetime.now() - timedelta(days=days)
        filtered = []
        for job in jobs:
            try:
                dt = datetime.fromisoformat(job.get("processed_at", "2000-01-01"))
                if dt >= cutoff:
                    filtered.append(job)
            except (ValueError, TypeError):
                filtered.append(job)
        jobs = filtered

    jobs_with_jd = [j for j in jobs if j.get("jd_content") or j.get("extracted_skills")]
    jobs_without_jd = len(jobs) - len(jobs_with_jd)

    # Summary metrics
    all_scores = [j["score"] for j in jobs if j.get("score") is not None]
    avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0
    high_score_count = sum(1 for s in all_scores if s >= 70)
    high_score_rate = round(high_score_count / len(all_scores) * 100, 1) if all_scores else 0.0

    week_cutoff = datetime.now() - timedelta(days=7)
    weekly_new = 0
    for job in jobs:
        try:
            dt = datetime.fromisoformat(job.get("processed_at", "2000-01-01"))
            if dt >= week_cutoff:
                weekly_new += 1
        except (ValueError, TypeError):
            pass

    return {
        "total_jobs_analyzed": len(jobs),
        "jobs_with_jd": len(jobs_with_jd),
        "jobs_without_jd": jobs_without_jd,
        "avg_score": avg_score,
        "high_score_rate": high_score_rate,
        "weekly_new": weekly_new,
        "skill_demand": aggregate_skill_demand(jobs),
        "skills_by_job_type": aggregate_skills_by_job_type(jobs),
        "salary_distribution": aggregate_salary_distribution(jobs),
        "company_activity": aggregate_company_activity(jobs),
        "title_trends": aggregate_title_trends(jobs),
        "job_level_distribution": aggregate_job_level_distribution(jobs),
        "location_distribution": aggregate_location_distribution(jobs),
        "score_distribution": aggregate_score_distribution(jobs),
        "daily_trends": aggregate_daily_trends(jobs),
        "generated_at": datetime.now().isoformat(),
    }
