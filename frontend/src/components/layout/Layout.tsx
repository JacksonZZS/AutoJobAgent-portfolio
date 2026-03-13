/**
 * 新版布局组件 - 分组导航 + 暗黑模式 + 移动端适配
 */

import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useState, useRef, useEffect } from 'react'
import {
  LayoutDashboard,
  LogOut,
  User,
  Sparkles,
  BarChart3,
  ChevronDown,
  Briefcase,
  Star,
  History,
  Brain,
  FileText,
  GraduationCap,
  Menu,
  X,
  Home,
  Search,
  Bookmark,
  UserCircle,
  Mail,
  Settings,
  TrendingUp,
  PieChart
} from 'lucide-react'
import ThemeToggle from '@/components/ui/ThemeToggle'

// 导航分组定义
const navGroups = [
  {
    id: 'dashboard',
    label: '主控台',
    icon: LayoutDashboard,
    href: '/',
    color: 'from-sky-600 to-sky-500',
    shadowColor: 'shadow-sky-500/30'
  },
  {
    id: 'jobs',
    label: '职位管理',
    icon: Briefcase,
    color: 'from-amber-500 to-orange-500',
    shadowColor: 'shadow-amber-500/30',
    submenu: [
      { id: 'favorites', label: '我的收藏', href: '/favorites', icon: Star },
      { id: 'history', label: '投递历史', href: '/history', icon: History },
    ]
  },
  {
    id: 'prepare',
    label: '面试准备',
    icon: GraduationCap,
    color: 'from-purple-600 to-pink-500',
    shadowColor: 'shadow-purple-500/30',
    submenu: [
      { id: 'interview', label: '面试题库', href: '/interview', icon: Brain },
      { id: 'optimizer', label: '简历优化', href: '/optimizer', icon: Sparkles },
      { id: 'resumes', label: '简历管理', href: '/resumes', icon: FileText },
    ]
  },
  {
    id: 'analytics',
    label: '数据分析',
    icon: BarChart3,
    color: 'from-green-600 to-emerald-500',
    shadowColor: 'shadow-green-500/30',
    submenu: [
      { id: 'statistics', label: '投递统计', href: '/statistics', icon: PieChart },
      { id: 'market', label: '市场洞察', href: '/market-intelligence', icon: TrendingUp },
    ]
  },
  {
    id: 'settings',
    label: '设置',
    icon: Settings,
    color: 'from-slate-600 to-slate-500',
    shadowColor: 'shadow-slate-500/30',
    submenu: [
      { id: 'email', label: '邮件通知', href: '/email-settings', icon: Mail },
    ]
  },
]

// 移动端底部 Tab Bar
const mobileTabBar = [
  { id: 'home', label: '主页', href: '/', icon: Home },
  { id: 'search', label: '投递', href: '/', icon: Search },
  { id: 'favorites', label: '收藏', href: '/favorites', icon: Bookmark },
  { id: 'profile', label: '我的', href: '/resumes', icon: UserCircle },
]

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const dropdownRefs = useRef<{ [key: string]: HTMLDivElement | null }>({})

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // 检查路径是否激活
  const isActive = (path: string) => location.pathname === path
  const isGroupActive = (group: typeof navGroups[0]) => {
    if (group.href) return isActive(group.href)
    return group.submenu?.some(item => isActive(item.href))
  }

  // 点击外部关闭下拉菜单
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const isOutside = Object.values(dropdownRefs.current).every(
        ref => !ref?.contains(event.target as Node)
      )
      if (isOutside) setOpenDropdown(null)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Decorative Background Blobs */}
      <div className="fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute top-0 -left-20 w-96 h-96 bg-sky-200/40 dark:bg-sky-600/10 rounded-full filter blur-3xl animate-pulse" />
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-indigo-200/40 dark:bg-cyan-600/10 rounded-full filter blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-purple-100/30 dark:bg-blue-600/5 rounded-full filter blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />
      </div>

      {/* Glass Header */}
      <header className="sticky top-0 z-50 glass-card border-b border-sky-200/60 dark:border-slate-700/60 mx-4 mt-4 rounded-2xl animate-slide-down">
        <div className="max-w-7xl mx-auto px-4 md:px-6 py-4 flex justify-between items-center">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-sky-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-lg shadow-sky-500/30 cursor-pointer hover:scale-105 transition-transform">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-gradient">
              AutoJobAgent
            </h1>
          </div>

          {/* Desktop User Menu */}
          <div className="hidden md:flex items-center gap-3">
            <ThemeToggle />
            <div className="flex items-center gap-2 px-4 py-2 bg-white/60 dark:bg-slate-800/60 backdrop-blur-md rounded-xl border border-sky-200/60 dark:border-slate-600/60">
              <User className="w-4 h-4 text-sky-600 dark:text-sky-400" />
              <span className="text-sm text-sky-700 dark:text-sky-300 font-medium">{user?.real_name}</span>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 bg-white/60 dark:bg-slate-800/60 backdrop-blur-md hover:bg-white/80 dark:hover:bg-slate-700/80 rounded-xl border border-sky-200/60 dark:border-slate-600/60 hover:border-red-300 dark:hover:border-red-500/50 transition-all duration-200 group cursor-pointer"
            >
              <LogOut className="w-4 h-4 text-sky-600 dark:text-sky-400 group-hover:text-red-600 dark:group-hover:text-red-400 transition-colors" />
              <span className="text-sm text-sky-700 dark:text-sky-300 group-hover:text-red-600 dark:group-hover:text-red-400 font-medium transition-colors">登出</span>
            </button>
          </div>

          {/* Mobile Menu Button */}
          <div className="flex md:hidden items-center gap-2">
            <ThemeToggle />
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 bg-white/60 dark:bg-slate-800/60 backdrop-blur-md rounded-xl border border-sky-200/60 dark:border-slate-600/60 cursor-pointer"
            >
              {mobileMenuOpen ? (
                <X className="w-5 h-5 text-sky-600 dark:text-sky-400" />
              ) : (
                <Menu className="w-5 h-5 text-sky-600 dark:text-sky-400" />
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden" onClick={() => setMobileMenuOpen(false)}>
          <div
            className="absolute top-20 left-4 right-4 glass-card p-4 rounded-2xl animate-fade-in"
            onClick={e => e.stopPropagation()}
          >
            <div className="space-y-2">
              {navGroups.map(group => (
                <div key={group.id}>
                  {group.href ? (
                    <Link
                      to={group.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={`flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all ${
                        isActive(group.href)
                          ? `bg-gradient-to-r ${group.color} text-white shadow-lg ${group.shadowColor}`
                          : 'text-sky-700 dark:text-sky-300 hover:bg-white/60 dark:hover:bg-slate-700/60'
                      }`}
                    >
                      <group.icon className="w-5 h-5" />
                      <span>{group.label}</span>
                    </Link>
                  ) : (
                    <>
                      <div className="flex items-center gap-3 px-4 py-3 text-sky-700 dark:text-sky-300 font-medium">
                        <group.icon className="w-5 h-5" />
                        <span>{group.label}</span>
                      </div>
                      <div className="ml-8 space-y-1">
                        {group.submenu?.map(item => (
                          <Link
                            key={item.id}
                            to={item.href}
                            onClick={() => setMobileMenuOpen(false)}
                            className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-all ${
                              isActive(item.href)
                                ? 'bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300'
                                : 'text-sky-600 dark:text-sky-400 hover:bg-sky-50 dark:hover:bg-slate-700/50'
                            }`}
                          >
                            <item.icon className="w-4 h-4" />
                            <span>{item.label}</span>
                          </Link>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-sky-200/60 dark:border-slate-600/60">
              <div className="flex items-center gap-2 px-4 py-2 text-sky-700 dark:text-sky-300">
                <User className="w-4 h-4" />
                <span className="text-sm font-medium">{user?.real_name}</span>
              </div>
              <button
                onClick={() => {
                  handleLogout()
                  setMobileMenuOpen(false)
                }}
                className="w-full flex items-center gap-2 px-4 py-3 mt-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-colors cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
                <span className="font-medium">登出</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop Navigation */}
      <nav className="sticky top-20 z-40 mx-4 mt-4 animate-fade-in hidden md:block">
        <div className="max-w-7xl mx-auto glass-card px-2 py-2 rounded-2xl">
          <div className="flex gap-1">
            {navGroups.map(group => (
              <div
                key={group.id}
                className="relative"
                ref={el => dropdownRefs.current[group.id] = el}
              >
                {group.href ? (
                  // 直接链接
                  <Link
                    to={group.href}
                    className={`flex items-center gap-2 px-5 py-3 rounded-xl font-semibold transition-all duration-200 cursor-pointer ${
                      isActive(group.href)
                        ? `bg-gradient-to-r ${group.color} text-white shadow-lg ${group.shadowColor}`
                        : 'text-sky-700 dark:text-sky-300 hover:bg-white/60 dark:hover:bg-slate-700/60 hover:text-sky-800 dark:hover:text-sky-200'
                    }`}
                  >
                    <group.icon className="w-5 h-5" />
                    <span>{group.label}</span>
                  </Link>
                ) : (
                  // 下拉菜单
                  <>
                    <button
                      onClick={() => setOpenDropdown(openDropdown === group.id ? null : group.id)}
                      className={`flex items-center gap-2 px-5 py-3 rounded-xl font-semibold transition-all duration-200 cursor-pointer ${
                        isGroupActive(group)
                          ? `bg-gradient-to-r ${group.color} text-white shadow-lg ${group.shadowColor}`
                          : 'text-sky-700 dark:text-sky-300 hover:bg-white/60 dark:hover:bg-slate-700/60 hover:text-sky-800 dark:hover:text-sky-200'
                      }`}
                    >
                      <group.icon className="w-5 h-5" />
                      <span>{group.label}</span>
                      <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${openDropdown === group.id ? 'rotate-180' : ''}`} />
                    </button>

                    {/* Dropdown Menu */}
                    {openDropdown === group.id && (
                      <div className="absolute top-full left-0 mt-2 w-48 py-2 glass-card rounded-xl shadow-xl animate-fade-in z-50">
                        {group.submenu?.map(item => (
                          <Link
                            key={item.id}
                            to={item.href}
                            onClick={() => setOpenDropdown(null)}
                            className={`flex items-center gap-3 px-4 py-2.5 transition-colors cursor-pointer ${
                              isActive(item.href)
                                ? 'bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300'
                                : 'text-sky-700 dark:text-sky-300 hover:bg-sky-50 dark:hover:bg-slate-700/50'
                            }`}
                          >
                            <item.icon className="w-4 h-4" />
                            <span className="text-sm font-medium">{item.label}</span>
                          </Link>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8 pb-24 md:pb-8 animate-fade-in">
        <Outlet />
      </main>

      {/* Mobile Bottom Tab Bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden">
        <div className="mx-4 mb-4 glass-card rounded-2xl border border-sky-200/60 dark:border-slate-700/60">
          <div className="flex justify-around py-2">
            {mobileTabBar.map(item => (
              <Link
                key={item.id}
                to={item.href}
                className={`flex flex-col items-center gap-1 px-4 py-2 rounded-xl transition-all cursor-pointer ${
                  isActive(item.href)
                    ? 'text-sky-600 dark:text-sky-400'
                    : 'text-sky-500/60 dark:text-sky-500/60 hover:text-sky-600 dark:hover:text-sky-400'
                }`}
              >
                <item.icon className={`w-5 h-5 ${isActive(item.href) ? 'scale-110' : ''} transition-transform`} />
                <span className="text-xs font-medium">{item.label}</span>
              </Link>
            ))}
          </div>
        </div>
      </nav>

      {/* Footer Decoration */}
      <div className="fixed bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-sky-300/50 dark:via-sky-600/30 to-transparent pointer-events-none hidden md:block" />
    </div>
  )
}
