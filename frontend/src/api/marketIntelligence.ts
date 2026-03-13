/**
 * Market Intelligence API
 */

import apiClient from './client'

export interface SkillDemandItem {
  skill: string
  count: number
  category: string
}

export interface SkillCountItem {
  skill: string
  count: number
}

export interface CategorySkills {
  category: string
  skills: SkillCountItem[]
}

export interface JobTypeSkillProfile {
  job_type: string
  total_jobs: number
  categories: CategorySkills[]
}

export interface SalaryDistributionItem {
  job_type: string
  min_avg: number
  max_avg: number
  count: number
  currency: string
}

export interface CompanyActivityItem {
  company: string
  count: number
  avg_score: number
}

export interface TitleTrendItem {
  title: string
  count: number
}

export interface JobLevelItem {
  level: string
  count: number
}

export interface LocationDistributionItem {
  location: string
  count: number
  percentage: number
}

export interface ScoreDistributionItem {
  range: string
  count: number
}

export interface DailyTrendItem {
  date: string
  new_jobs: number
  avg_score: number
}

export interface MarketIntelligenceResponse {
  total_jobs_analyzed: number
  jobs_with_jd: number
  jobs_without_jd: number
  avg_score: number
  high_score_rate: number
  weekly_new: number
  skill_demand: SkillDemandItem[]
  skills_by_job_type: JobTypeSkillProfile[]
  salary_distribution: SalaryDistributionItem[]
  company_activity: CompanyActivityItem[]
  title_trends: TitleTrendItem[]
  job_level_distribution: JobLevelItem[]
  location_distribution: LocationDistributionItem[]
  score_distribution: ScoreDistributionItem[]
  daily_trends: DailyTrendItem[]
  generated_at: string
}

export const marketIntelligenceAPI = {
  getOverview: async (days?: number): Promise<MarketIntelligenceResponse> => {
    const params = days ? `?days=${days}` : ''
    const response = await apiClient.get(`/api/v1/market-intelligence/overview${params}`)
    return response.data
  },

  getSkills: async (topN: number = 20): Promise<{ skills: SkillDemandItem[]; total_jobs: number }> => {
    const response = await apiClient.get(`/api/v1/market-intelligence/skills?top_n=${topN}`)
    return response.data
  },

  getSalary: async (): Promise<{ salary_distribution: SalaryDistributionItem[]; total_jobs: number }> => {
    const response = await apiClient.get('/api/v1/market-intelligence/salary')
    return response.data
  },
}
