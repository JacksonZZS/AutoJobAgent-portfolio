"""
Pydantic 数据模型定义
用于 API 请求/响应的数据验证和序列化
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================
# 认证相关模型
# ============================================================

class LoginRequest(BaseModel):
    """用户登录请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, description="密码")


class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, description="密码")
    email: EmailStr = Field(..., description="邮箱地址")
    real_name: str = Field(..., min_length=1, max_length=100, description="真实姓名")
    phone: str = Field(..., description="手机号码")
    linkedin: Optional[str] = Field(None, description="LinkedIn 个人主页")
    github: Optional[str] = Field(None, description="GitHub 个人主页")


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: "UserInfo" = Field(..., description="用户信息")


class UserInfo(BaseModel):
    """用户信息"""
    id: int = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    real_name: str = Field(..., description="真实姓名")
    phone: str = Field(..., description="手机号码")
    linkedin: Optional[str] = Field(None, description="LinkedIn")
    github: Optional[str] = Field(None, description="GitHub")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "username": "john_doe",
                "email": "john@example.com",
                "real_name": "John Doe",
                "phone": "+852 9999 8888",
                "linkedin": "https://linkedin.com/in/johndoe",
                "github": "https://github.com/johndoe",
                "created_at": "2024-01-20T10:30:00"
            }
        }


# ============================================================
# 文件上传相关模型
# ============================================================

class UploadResumeResponse(BaseModel):
    """简历上传响应"""
    file_path: str = Field(..., description="文件保存路径")
    file_hash: str = Field(..., description="文件哈希值（用于缓存）")
    cached_analysis: Optional[Dict[str, Any]] = Field(None, description="缓存的分析结果")
    message: str = Field(..., description="状态消息")


class UploadTranscriptResponse(BaseModel):
    """成绩单上传响应"""
    file_path: str = Field(..., description="文件保存路径")
    message: str = Field(..., description="状态消息")


# ============================================================
# 简历分析相关模型
# ============================================================

class AnalyzeResumeRequest(BaseModel):
    """简历分析请求"""
    resume_path: Optional[str] = Field(None, description="简历文件路径（如已上传）")
    transcript_path: Optional[str] = Field(None, description="成绩单文件路径（可选）")


class AnalyzeResumeResponse(BaseModel):
    """简历分析响应"""
    keywords: str = Field(..., description="职位搜索关键词（逗号分隔）")
    blocked_companies: str = Field(..., description="公司黑名单（逗号分隔）")
    title_exclusions: str = Field(..., description="职位排除词（逗号分隔）")
    user_profile: Optional[Dict[str, Any]] = Field(None, description="用户画像分析结果")
    message: str = Field(default="分析成功", description="状态消息")

    class Config:
        json_schema_extra = {
            "example": {
                "keywords": "Python Developer, AI Engineer, Machine Learning",
                "blocked_companies": "Company A, Company B",
                "title_exclusions": "Senior, Manager, Director, Lead",
                "message": "分析成功"
            }
        }


# ============================================================
# 任务管理相关模型
# ============================================================

class TaskStatus(str, Enum):
    """任务状态枚举"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    SCRAPING = "scraping"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    MANUAL_REVIEW = "manual_review"
    APPLYING = "applying"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"


class PlatformType(str, Enum):
    """平台类型枚举"""
    JOBSDB = "jobsdb"
    INDEED = "indeed"
    LINKEDIN = "linkedin"


class StartTaskRequest(BaseModel):
    """启动任务请求"""
    keywords: str = Field(..., description="职位搜索关键词（多个用逗号分隔）")
    platform: PlatformType = Field(default=PlatformType.JOBSDB, description="目标平台")
    target_count: int = Field(default=100, ge=1, le=500, description="目标投递数量")
    company_blacklist: Optional[List[str]] = Field(default=[], description="公司黑名单")
    title_exclusions: Optional[List[str]] = Field(default=[], description="职位标题排除词")
    score_threshold: int = Field(default=60, ge=0, le=100, description="匹配分数阈值（0-100）")
    auto_skip_threshold: int = Field(default=50, ge=0, le=100, description="自动跳过阈值（分数低于此值）")
    manual_review_threshold: int = Field(default=60, ge=0, le=100, description="人工复核阈值（分数达到此值）")
    resume_path: Optional[str] = Field(None, description="简历文件路径")
    transcript_path: Optional[str] = Field(None, description="成绩单文件路径（可选）")

    class Config:
        json_schema_extra = {
            "example": {
                "keywords": "Python Developer, AI Engineer",
                "target_count": 100,
                "company_blacklist": ["Company A", "Company B"],
                "title_exclusions": ["Senior", "Manager"],
                "auto_skip_threshold": 55,
                "manual_review_threshold": 65
            }
        }


class StartTaskResponse(BaseModel):
    """启动任务响应"""
    task_id: str = Field(..., description="任务 ID")
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="状态消息")
    websocket_url: str = Field(..., description="WebSocket 连接地址")


class TaskStats(BaseModel):
    """任务统计数据"""
    total_seen: int = Field(default=0, description="扫描到的职位数")
    total_processed: int = Field(default=0, description="总处理数")
    filtered_history: int = Field(default=0, description="因历史记录跳过")
    filtered_title: int = Field(default=0, description="因标题过滤跳过")
    filtered_company: int = Field(default=0, description="因公司黑名单跳过")
    rejected_low_score: int = Field(default=0, description="低分拒绝数")
    failed_scoring: int = Field(default=0, description="评分失败数")
    manual_review: int = Field(default=0, description="进入人工复核数")
    success: int = Field(default=0, description="成功投递数")
    skipped: int = Field(default=0, description="跳过数")
    failed: int = Field(default=0, description="失败数")


class CurrentJobInfo(BaseModel):
    """当前处理职位信息"""
    title: str = Field(..., description="职位名称")
    company: str = Field(..., description="公司名称")
    score: Optional[int] = Field(None, description="匹配分数")
    jd_content: Optional[str] = Field(None, description="职位描述")
    job_url: Optional[str] = Field(None, description="职位链接")
    location: Optional[str] = Field(None, description="工作地点")


class DimensionScore(BaseModel):
    """评分维度"""
    name: str = Field(..., description="维度名称")
    weight: int = Field(..., description="权重")
    score: int = Field(..., description="得分")
    comment: str = Field(..., description="评语")


class ManualReviewData(BaseModel):
    """人工复核数据"""
    score: int = Field(..., description="匹配分数")
    dimensions: List[DimensionScore] = Field(default=[], description="评分维度")
    job_url: str = Field(..., description="职位链接")
    job_title: str = Field(..., description="职位名称")
    company_name: str = Field(..., description="公司名称")
    resume_path: str = Field(..., description="生成的简历路径")
    cl_path: str = Field(..., description="生成的求职信路径")
    cl_text: str = Field(..., description="求职信文本内容")
    base_resume_label: Optional[str] = Field(None, description="使用的基础简历标签")
    base_resume_filename: Optional[str] = Field(None, description="使用的基础简历文件名")
    tailored_resume_filename: Optional[str] = Field(None, description="生成的定制简历文件名")
    decision: Optional[str] = Field(None, description="用户决策")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="状态消息")
    progress: int = Field(default=0, ge=0, le=100, description="进度百分比")
    stats: TaskStats = Field(default_factory=TaskStats, description="统计数据")
    current_job: Optional[CurrentJobInfo] = Field(None, description="当前处理职位")
    manual_review_data: Optional[ManualReviewData] = Field(None, description="人工复核数据")
    manual_review_queue: List[ManualReviewData] = Field(default=[], description="待人工复核队列")
    last_updated: Optional[datetime] = Field(None, description="最后更新时间")


class ManualDecisionRequest(BaseModel):
    """人工决策请求"""
    decision: str = Field(..., description="决策类型：APPLY / SKIP_PERMANENT / SKIP_TEMPORARY")

    class Config:
        json_schema_extra = {
            "example": {
                "decision": "APPLY"
            }
        }


# ============================================================
# 历史记录相关模型
# ============================================================

class JobHistoryItem(BaseModel):
    """投递历史记录"""
    job_id: str = Field(..., description="职位 ID")
    title: str = Field(..., description="职位名称")
    company: str = Field(..., description="公司名称")
    link: str = Field(..., description="职位链接")
    status: str = Field(..., description="投递状态")
    score: Optional[int] = Field(None, description="匹配分数")
    reason: Optional[str] = Field(None, description="拒绝/跳过原因")
    resume_path: Optional[str] = Field(None, description="简历路径")
    cl_path: Optional[str] = Field(None, description="求职信路径")
    platform: Optional[str] = Field(None, description="来源平台：jobsdb/indeed")
    processed_at: datetime = Field(..., description="处理时间")


class HistoryListResponse(BaseModel):
    """历史记录列表响应"""
    total: int = Field(..., description="总记录数")
    items: List[JobHistoryItem] = Field(..., description="历史记录列表")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=50, description="每页数量")


class HistoryStatisticsResponse(BaseModel):
    """历史统计响应"""
    total: int = Field(default=0, description="总计")
    success: int = Field(default=0, description="成功投递")
    skipped: int = Field(default=0, description="已跳过")
    failed: int = Field(default=0, description="失败")


# ============================================================
# 物料中心相关模型
# ============================================================

class PendingMaterialResponse(BaseModel):
    """待审核物料响应"""
    has_pending: bool = Field(..., description="是否有待审核任务")
    material_data: Optional[ManualReviewData] = Field(None, description="物料数据")


# ============================================================
# 通用响应模型
# ============================================================

class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str = Field(..., description="响应消息")
    status: str = Field(default="success", description="状态：success/error")
    data: Optional[Dict[str, Any]] = Field(None, description="附加数据")


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误类型")
    detail: str = Field(..., description="错误详情")
    path: Optional[str] = Field(None, description="请求路径")


# ============================================================
# 批量操作相关模型
# ============================================================

class BatchSkipRequest(BaseModel):
    """批量跳过低分职位请求"""
    threshold: int = Field(default=60, ge=0, le=100, description="分数阈值，低于此分数的职位将被跳过")
    skip_type: str = Field(default="SKIP_PERMANENT", description="跳过类型：SKIP_PERMANENT / SKIP_TEMPORARY")

    class Config:
        json_schema_extra = {
            "example": {
                "threshold": 50,
                "skip_type": "SKIP_PERMANENT"
            }
        }


class BatchSkipResponse(BaseModel):
    """批量跳过响应"""
    skipped_count: int = Field(..., description="跳过的职位数量")
    message: str = Field(..., description="操作结果消息")
    skipped_jobs: List[Dict[str, Any]] = Field(default=[], description="被跳过的职位列表")


# ============================================================
# 统计相关模型
# ============================================================

class PlatformStats(BaseModel):
    """平台统计"""
    total: int = Field(default=0, description="总数")
    success: int = Field(default=0, description="成功数")
    avg_score: float = Field(default=0.0, description="平均分数")


class DashboardStatisticsResponse(BaseModel):
    """仪表盘统计响应"""
    total_applications: int = Field(default=0, description="总投递数")
    success_count: int = Field(default=0, description="成功数")
    skip_count: int = Field(default=0, description="跳过数")
    failed_count: int = Field(default=0, description="失败数")
    today_count: int = Field(default=0, description="今日投递数")
    week_count: int = Field(default=0, description="本周投递数")
    month_count: int = Field(default=0, description="本月投递数")
    success_rate: float = Field(default=0.0, description="成功率(%)")
    avg_score: float = Field(default=0.0, description="平均匹配分")
    platform_stats: Dict[str, PlatformStats] = Field(default={}, description="按平台分类统计")


class TrendDataPoint(BaseModel):
    """趋势数据点"""
    date: str = Field(..., description="日期")
    applications: int = Field(default=0, description="投递数")
    success: int = Field(default=0, description="成功数")


class TrendsResponse(BaseModel):
    """趋势数据响应"""
    data: List[TrendDataPoint] = Field(default=[], description="趋势数据")


class PlatformBreakdownItem(BaseModel):
    """平台分布项"""
    platform: str = Field(..., description="平台名称")
    count: int = Field(default=0, description="数量")
    percentage: float = Field(default=0.0, description="百分比")


class PlatformBreakdownResponse(BaseModel):
    """平台分布响应"""
    platforms: List[PlatformBreakdownItem] = Field(default=[], description="平台分布")


# ============================================================
# 收藏相关模型
# ============================================================

class FavoriteJob(BaseModel):
    """收藏的职位"""
    job_id: str = Field(..., description="职位 ID")
    title: str = Field(..., description="职位名称")
    company: str = Field(..., description="公司名称")
    link: str = Field(..., description="职位链接")
    score: Optional[int] = Field(None, description="匹配分数")
    platform: Optional[str] = Field(None, description="来源平台")
    notes: Optional[str] = Field(None, description="备注")
    favorited_at: datetime = Field(..., description="收藏时间")


class AddFavoriteRequest(BaseModel):
    """添加收藏请求"""
    title: str = Field(..., description="职位名称")
    company: str = Field(..., description="公司名称")
    link: str = Field(..., description="职位链接")
    score: Optional[int] = Field(None, description="匹配分数")
    platform: Optional[str] = Field(None, description="来源平台")
    notes: Optional[str] = Field(None, description="备注")


class FavoritesListResponse(BaseModel):
    """收藏列表响应"""
    total: int = Field(default=0, description="总数")
    items: List[FavoriteJob] = Field(default=[], description="收藏列表")


# ============================================================
# 多简历管理相关模型
# ============================================================

class ResumeInfo(BaseModel):
    """简历信息"""
    resume_id: str = Field(..., description="简历 ID")
    filename: str = Field(..., description="文件名")
    label: Optional[str] = Field(None, description="简历标签（如 DS/BA/PM）")
    file_path: str = Field(..., description="文件路径")
    file_hash: str = Field(..., description="文件哈希")
    is_default: bool = Field(default=False, description="是否为默认简历")
    uploaded_at: datetime = Field(..., description="上传时间")


class ResumeListResponse(BaseModel):
    """简历列表响应"""
    resumes: List[ResumeInfo] = Field(default=[], description="简历列表")
    default_resume_id: Optional[str] = Field(None, description="默认简历 ID")


class SetDefaultResumeRequest(BaseModel):
    """设置默认简历请求"""
    resume_id: str = Field(..., description="简历 ID")


# ============================================================
# Cover Letter 编辑相关模型
# ============================================================

class UpdateCoverLetterRequest(BaseModel):
    """更新求职信请求"""
    cl_text: str = Field(..., min_length=50, max_length=10000, description="求职信文本内容")


class UpdateCoverLetterResponse(BaseModel):
    """更新求职信响应"""
    message: str = Field(..., description="操作结果消息")
    new_cl_path: str = Field(..., description="新的求职信 PDF 路径")


# ============================================================
# 通知相关模型
# ============================================================

class NotificationPreferences(BaseModel):
    """通知偏好设置"""
    push_enabled: bool = Field(default=True, description="是否启用浏览器推送")
    email_enabled: bool = Field(default=False, description="是否启用邮件通知")
    email_address: Optional[str] = Field(None, description="通知邮箱地址")
    high_score_threshold: int = Field(default=80, ge=0, le=100, description="高分职位阈值")
    notify_on_complete: bool = Field(default=True, description="任务完成时通知")
    notify_on_error: bool = Field(default=True, description="任务出错时通知")


class UpdateNotificationPreferencesRequest(BaseModel):
    """更新通知偏好请求"""
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    email_address: Optional[str] = None
    high_score_threshold: Optional[int] = Field(None, ge=0, le=100)
    notify_on_complete: Optional[bool] = None
    notify_on_error: Optional[bool] = None


class WebPushSubscription(BaseModel):
    """Web Push 订阅信息"""
    endpoint: str = Field(..., description="推送端点")
    keys: Dict[str, str] = Field(..., description="加密密钥")


# ============================================================
# Market Intelligence 模型
# ============================================================

class SkillDemandItem(BaseModel):
    """技能需求项"""
    skill: str
    count: int
    category: str

class SalaryDistributionItem(BaseModel):
    """薪资分布项"""
    job_type: str
    min_avg: float
    max_avg: float
    count: int
    currency: str = "HKD"

class CompanyActivityItem(BaseModel):
    """公司招聘活跃度项"""
    company: str
    count: int
    avg_score: float = 0.0

class TitleTrendItem(BaseModel):
    """职位类型趋势项"""
    title: str
    count: int

class LocationDistributionItem(BaseModel):
    """地点分布项"""
    location: str
    count: int
    percentage: float = 0.0

class ScoreDistributionItem(BaseModel):
    """评分分布项"""
    range: str
    count: int

class DailyTrendItem(BaseModel):
    """每日趋势项"""
    date: str
    new_jobs: int
    avg_score: float = 0.0

class SkillCountItem(BaseModel):
    """技能计数项（用于按职位类型分组）"""
    skill: str
    count: int

class JobTypeSkillProfile(BaseModel):
    """职位类型技能画像"""
    job_type: str
    total_jobs: int
    categories: List[Dict[str, Any]] = []

class JobLevelItem(BaseModel):
    """职级分布项"""
    level: str
    count: int

class MarketIntelligenceResponse(BaseModel):
    """Market Intelligence 完整响应"""
    total_jobs_analyzed: int = 0
    jobs_with_jd: int = 0
    jobs_without_jd: int = 0
    avg_score: float = 0.0
    high_score_rate: float = 0.0
    weekly_new: int = 0
    skill_demand: List[SkillDemandItem] = []
    skills_by_job_type: List[JobTypeSkillProfile] = []
    salary_distribution: List[SalaryDistributionItem] = []
    company_activity: List[CompanyActivityItem] = []
    title_trends: List[TitleTrendItem] = []
    job_level_distribution: List[JobLevelItem] = []
    location_distribution: List[LocationDistributionItem] = []
    score_distribution: List[ScoreDistributionItem] = []
    daily_trends: List[DailyTrendItem] = []
    generated_at: str = ""
