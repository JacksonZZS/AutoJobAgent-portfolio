/**
 * 登录页面 - Professional Glassmorphism (Light Theme)
 */

import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authAPI } from '@/api/auth'
import { Sparkles, ArrowRight, Lock, User as UserIcon } from 'lucide-react'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()
  const [formData, setFormData] = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await authAPI.login(formData)
      setAuth(response.user, response.access_token)
      navigate('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || '登录失败，请检查用户名和密码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden p-4">
      {/* Decorative Background */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute top-1/4 -left-20 w-[500px] h-[500px] bg-sky-400/30 rounded-full filter blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 -right-20 w-[500px] h-[500px] bg-cyan-400/30 rounded-full filter blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-400/20 rounded-full filter blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <div className="w-full max-w-md animate-scale-in">
        {/* Logo Section */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-sky-500 to-cyan-500 rounded-2xl shadow-2xl shadow-sky-500/30 mb-4 floating">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-5xl font-bold tracking-tight mb-3 text-gradient">
            AutoJobAgent
          </h1>
          <p className="text-lg text-sky-600">
            AI 驱动的智能求职平台
          </p>
        </div>

        {/* Login Card */}
        <div className="glass-card p-8 animate-slide-up">
          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div className="bg-red-50/80 border border-red-200 text-red-700 text-sm py-3 px-4 rounded-xl backdrop-blur-md animate-fade-in">
                {error}
              </div>
            )}

            <div className="space-y-5">
              {/* Username Input */}
              <div>
                <label htmlFor="username" className="block text-sm font-semibold text-sky-800 mb-2">
                  用户名
                </label>
                <div className="relative">
                  <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-sky-500" />
                  <input
                    id="username"
                    type="text"
                    required
                    placeholder="输入用户名"
                    className="glass-input pl-11"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  />
                </div>
              </div>

              {/* Password Input */}
              <div>
                <label htmlFor="password" className="block text-sm font-semibold text-sky-800 mb-2">
                  密码
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-sky-500" />
                  <input
                    id="password"
                    type="password"
                    required
                    placeholder="输入密码"
                    className="glass-input pl-11"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  />
                </div>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="glass-button w-full mt-8 flex items-center justify-center gap-2 group"
            >
              <span>{loading ? '登录中...' : '登录'}</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
          </form>

          {/* Register Link */}
          <div className="text-center pt-6 mt-6 border-t border-sky-200/60">
            <Link
              to="/register"
              className="text-sm text-sky-600 hover:text-sky-700 transition-colors duration-200 inline-flex items-center gap-2 group cursor-pointer"
            >
              还没有账户？
              <span className="font-semibold text-sky-700 group-hover:text-sky-800">立即注册</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>

        {/* Bottom Decoration */}
        <div className="mt-8 text-center text-sm text-sky-600/70">
          由 AI 技术驱动 · 让求职更简单
        </div>
      </div>
    </div>
  )
}
