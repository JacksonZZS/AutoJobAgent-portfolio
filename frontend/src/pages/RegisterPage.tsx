/**
 * 注册页面 - Professional Glassmorphism (Light Theme)
 */

import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authAPI } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'
import { Sparkles, ArrowRight, Lock, User, Mail, Phone, UserCircle, CheckCircle } from 'lucide-react'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    email: '',
    real_name: '',
    phone: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      // 1. 注册
      await authAPI.register(formData)

      // 2. 自动登录
      const loginResponse = await authAPI.login({
        username: formData.username,
        password: formData.password
      })

      // 3. 保存认证状态
      setAuth(loginResponse.user, loginResponse.access_token)

      // 4. 跳转到 Dashboard
      navigate('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || '注册失败，请重试')
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
            创建您的账户，开启智能求职之旅
          </p>
        </div>

        {/* Register Card */}
        <div className="glass-card p-8 animate-slide-up">
          <form className="space-y-5" onSubmit={handleSubmit}>
            {error && (
              <div className="bg-red-50/80 border border-red-200 text-red-700 text-sm py-3 px-4 rounded-xl backdrop-blur-md animate-fade-in">
                {error}
              </div>
            )}

            <div className="space-y-4">
              {/* Username Input */}
              <div>
                <label htmlFor="username" className="block text-sm font-semibold text-sky-800 mb-2">
                  用户名 <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-sky-500" />
                  <input
                    id="username"
                    type="text"
                    required
                    placeholder="选择一个用户名"
                    className="glass-input pl-11"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  />
                </div>
              </div>

              {/* Password Input */}
              <div>
                <label htmlFor="password" className="block text-sm font-semibold text-sky-800 mb-2">
                  密码 <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-sky-500" />
                  <input
                    id="password"
                    type="password"
                    required
                    placeholder="设置安全密码"
                    className="glass-input pl-11"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  />
                </div>
              </div>

              {/* Email Input */}
              <div>
                <label htmlFor="email" className="block text-sm font-semibold text-sky-800 mb-2">
                  邮箱 <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-sky-500" />
                  <input
                    id="email"
                    type="email"
                    required
                    placeholder="your@email.com"
                    className="glass-input pl-11"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />
                </div>
              </div>

              {/* Real Name Input */}
              <div>
                <label htmlFor="real_name" className="block text-sm font-semibold text-sky-800 mb-2">
                  真实姓名 <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <UserCircle className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-sky-500" />
                  <input
                    id="real_name"
                    type="text"
                    required
                    placeholder="您的真实姓名"
                    className="glass-input pl-11"
                    value={formData.real_name}
                    onChange={(e) => setFormData({ ...formData, real_name: e.target.value })}
                  />
                </div>
              </div>

              {/* Phone Input */}
              <div>
                <label htmlFor="phone" className="block text-sm font-semibold text-sky-800 mb-2">
                  手机号码 <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-sky-500" />
                  <input
                    id="phone"
                    type="tel"
                    required
                    placeholder="您的手机号码"
                    className="glass-input pl-11"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
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
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>注册中...</span>
                </>
              ) : (
                <>
                  <CheckCircle className="w-5 h-5" />
                  <span>创建账户</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          {/* Login Link */}
          <div className="text-center pt-6 mt-6 border-t border-sky-200/60">
            <Link
              to="/login"
              className="text-sm text-sky-600 hover:text-sky-700 transition-colors duration-200 inline-flex items-center gap-2 group cursor-pointer"
            >
              已有账户？
              <span className="font-semibold text-sky-700 group-hover:text-sky-800">立即登录</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>

        {/* Bottom Decoration */}
        <div className="mt-8 text-center text-sm text-sky-600/70">
          注册即表示您同意我们的服务条款和隐私政策
        </div>
      </div>
    </div>
  )
}
