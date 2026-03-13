/**
 * 邮件设置组件 - 配置 SMTP 和邮件偏好
 */

import { useState, useEffect } from 'react'
import {
  Mail,
  Settings,
  Bell,
  Send,
  CheckCircle,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  Save
} from 'lucide-react'

interface EmailConfig {
  enabled: boolean
  smtp_configured: boolean
  from_name: string
}

interface EmailPreferences {
  job_alerts: boolean
  min_match_score: number
  daily_digest: boolean
  instant_notify: boolean
}

export default function EmailSettings() {
  const [config, setConfig] = useState<EmailConfig | null>(null)
  const [preferences, setPreferences] = useState<EmailPreferences>({
    job_alerts: true,
    min_match_score: 80,
    daily_digest: false,
    instant_notify: true
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  
  // SMTP 配置表单
  const [smtpForm, setSmtpForm] = useState({
    host: 'smtp.gmail.com',
    port: '587',
    user: '',
    password: '',
    from_name: 'AutoJob Agent'
  })

  // 获取邮件配置状态
  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      const response = await fetch('/api/v1/email/config', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })
      if (response.ok) {
        const data = await response.json()
        setConfig(data)
      }
    } catch (error) {
      console.error('获取邮件配置失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSavePreferences = async () => {
    setSaving(true)
    setMessage(null)

    try {
      const response = await fetch('/api/v1/email/config', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          ...smtpForm,
          preferences
        })
      })

      if (response.ok) {
        setMessage({ type: 'success', text: '设置保存成功！' })
      } else {
        const error = await response.json()
        setMessage({ type: 'error', text: error.detail || '保存失败' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: '保存失败，请重试' })
    } finally {
      setSaving(false)
    }
  }

  const handleTestEmail = async () => {
    setSaving(true)
    setMessage(null)

    try {
      const response = await fetch('/api/v1/email/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          type: 'test',
          to: smtpForm.user // 发送到自己的邮箱
        })
      })

      if (response.ok) {
        setMessage({ type: 'success', text: '测试邮件已发送！请检查收件箱' })
      } else {
        const error = await response.json()
        setMessage({ type: 'error', text: error.detail || '发送失败，请检查配置' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: '发送失败，请检查配置' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-sky-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/30">
            <Mail className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-sky-900">邮件设置</h1>
            <p className="text-sm text-sky-600">配置邮件通知和 SMTP 服务器</p>
          </div>
        </div>
      </div>

      {/* 消息提示 */}
      {message && (
        <div className={`p-4 rounded-xl flex items-center gap-2 ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-700 border border-green-200' 
            : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle className="w-5 h-5" />
          ) : (
            <AlertCircle className="w-5 h-5" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左侧：SMTP 配置 */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-bold text-sky-900 mb-4 flex items-center gap-2">
            <Settings className="w-5 h-5 text-sky-600" />
            SMTP 服务器配置
          </h2>

          <div className="space-y-4">
            {/* 状态指示 */}
            <div className={`p-3 rounded-lg flex items-center gap-2 ${
              config?.smtp_configured 
                ? 'bg-green-50 text-green-700' 
                : 'bg-yellow-50 text-yellow-700'
            }`}>
              {config?.smtp_configured ? (
                <>
                  <CheckCircle className="w-4 h-4" />
                  <span className="text-sm">SMTP 已配置</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-4 h-4" />
                  <span className="text-sm">SMTP 未配置，请在 .env 文件中设置</span>
                </>
              )}
            </div>

            {/* SMTP Host */}
            <div>
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                SMTP 服务器
              </label>
              <input
                type="text"
                value={smtpForm.host}
                onChange={(e) => setSmtpForm({ ...smtpForm, host: e.target.value })}
                placeholder="smtp.gmail.com"
                className="glass-input"
              />
            </div>

            {/* SMTP Port */}
            <div>
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                端口
              </label>
              <input
                type="text"
                value={smtpForm.port}
                onChange={(e) => setSmtpForm({ ...smtpForm, port: e.target.value })}
                placeholder="587"
                className="glass-input"
              />
            </div>

            {/* SMTP User */}
            <div>
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                邮箱账号
              </label>
              <input
                type="email"
                value={smtpForm.user}
                onChange={(e) => setSmtpForm({ ...smtpForm, user: e.target.value })}
                placeholder="your-email@gmail.com"
                className="glass-input"
              />
            </div>

            {/* SMTP Password */}
            <div>
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                应用密码
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={smtpForm.password}
                  onChange={(e) => setSmtpForm({ ...smtpForm, password: e.target.value })}
                  placeholder="••••••••"
                  className="glass-input pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-sky-500 hover:text-sky-700"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-xs text-sky-500 mt-1">
                Gmail 需要使用"应用专用密码"
              </p>
            </div>

            {/* 发件人名称 */}
            <div>
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                发件人名称
              </label>
              <input
                type="text"
                value={smtpForm.from_name}
                onChange={(e) => setSmtpForm({ ...smtpForm, from_name: e.target.value })}
                placeholder="AutoJob Agent"
                className="glass-input"
              />
            </div>

            {/* 测试按钮 */}
            <button
              onClick={handleTestEmail}
              disabled={saving}
              className="w-full glass-button flex items-center justify-center gap-2"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              发送测试邮件
            </button>
          </div>
        </div>

        {/* 右侧：通知偏好 */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-bold text-sky-900 mb-4 flex items-center gap-2">
            <Bell className="w-5 h-5 text-sky-600" />
            通知偏好
          </h2>

          <div className="space-y-4">
            {/* 启用邮件通知 */}
            <div className="flex items-center justify-between p-3 bg-sky-50/50 rounded-lg">
              <div>
                <p className="font-semibold text-sky-800">高分职位通知</p>
                <p className="text-xs text-sky-600">当发现高匹配度职位时发送邮件</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.job_alerts}
                  onChange={(e) => setPreferences({ ...preferences, job_alerts: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-500"></div>
              </label>
            </div>

            {/* 最低匹配分数 */}
            <div>
              <label className="block text-sm font-semibold text-sky-800 mb-2">
                最低匹配分数: {preferences.min_match_score}%
              </label>
              <input
                type="range"
                min="50"
                max="100"
                value={preferences.min_match_score}
                onChange={(e) => setPreferences({ ...preferences, min_match_score: parseInt(e.target.value) })}
                className="w-full h-2 bg-sky-100 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-sky-500 mt-1">
                <span>50%</span>
                <span>100%</span>
              </div>
            </div>

            {/* 每日摘要 */}
            <div className="flex items-center justify-between p-3 bg-sky-50/50 rounded-lg">
              <div>
                <p className="font-semibold text-sky-800">每日摘要</p>
                <p className="text-xs text-sky-600">每天早上发送职位汇总</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.daily_digest}
                  onChange={(e) => setPreferences({ ...preferences, daily_digest: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-500"></div>
              </label>
            </div>

            {/* 即时通知 */}
            <div className="flex items-center justify-between p-3 bg-sky-50/50 rounded-lg">
              <div>
                <p className="font-semibold text-sky-800">即时通知</p>
                <p className="text-xs text-sky-600">发现高分职位立即通知</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.instant_notify}
                  onChange={(e) => setPreferences({ ...preferences, instant_notify: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-500"></div>
              </label>
            </div>

            {/* 保存按钮 */}
            <button
              onClick={handleSavePreferences}
              disabled={saving}
              className="w-full glass-button-success flex items-center justify-center gap-2"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              保存设置
            </button>
          </div>
        </div>
      </div>

      {/* 使用说明 */}
      <div className="glass-card p-6">
        <h3 className="font-bold text-sky-900 mb-3">📝 配置说明</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-sky-700">
          <div className="bg-sky-50/50 p-4 rounded-lg">
            <p className="font-semibold mb-2">Gmail 配置</p>
            <ul className="space-y-1 text-xs">
              <li>• 服务器: smtp.gmail.com</li>
              <li>• 端口: 587</li>
              <li>• 需开启两步验证</li>
              <li>• 使用"应用专用密码"</li>
            </ul>
          </div>
          <div className="bg-sky-50/50 p-4 rounded-lg">
            <p className="font-semibold mb-2">QQ 邮箱配置</p>
            <ul className="space-y-1 text-xs">
              <li>• 服务器: smtp.qq.com</li>
              <li>• 端口: 587</li>
              <li>• 需开启 SMTP 服务</li>
              <li>• 使用授权码作为密码</li>
            </ul>
          </div>
          <div className="bg-sky-50/50 p-4 rounded-lg">
            <p className="font-semibold mb-2">163 邮箱配置</p>
            <ul className="space-y-1 text-xs">
              <li>• 服务器: smtp.163.com</li>
              <li>• 端口: 465</li>
              <li>• 需开启 SMTP 服务</li>
              <li>• 使用授权码作为密码</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
