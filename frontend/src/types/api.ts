/**
 * TypeScript 类型定义
 * 与后端 API 数据模型对应
 */

export interface User {
  id: number
  username: string
  email: string
  real_name: string
  phone: string
  linkedin?: string
  github?: string
  created_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  email: string
  real_name: string
  phone: string
  linkedin?: string
  github?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
  token: string  // alias for access_token
}

export enum TaskStatus {
  IDLE = 'idle',
  INITIALIZING = 'initializing',
  SCRAPING = 'scraping',
  ANALYZING = 'analyzing',
  GENERATING = 'generating',
  MANUAL_REVIEW = 'manual_review',
  APPLYING = 'applying',
  WAITING_USER = 'waiting_user',
  COMPLETED = 'completed',
  ERROR = 'error',
  STOPPED = 'stopped',
}

export interface TaskStats {
  total_seen: number
  total_processed: number
  filtered_history: number
  filtered_title: number
  filtered_company: number
  rejected_low_score: number
  failed_scoring: number
  manual_review: number
  success: number
  skipped: number
  failed: number
}

export interface CurrentJobInfo {
  title: string
  company: string
  score?: number
  jd_content?: string
  job_url?: string
  location?: string
}

export interface ManualReviewData {
  score: number
  dimensions?: Array<{
    name: string
    weight: number
    score: number
    comment: string
  }>
  job_url: string
  job_title: string
  company_name: string
  resume_path: string
  cl_path: string
  cl_text: string
  base_resume_label?: string
  base_resume_filename?: string
  tailored_resume_filename?: string
  decision?: string
}

export interface TaskStatusResponse {
  status: TaskStatus
  message: string
  progress: number
  stats: TaskStats
  current_job?: CurrentJobInfo
  manual_review_data?: ManualReviewData
  manual_review_queue?: ManualReviewData[]
  last_updated?: string
}
