/**
 * Theme Toggle - 主题切换按钮
 */

import { Sun, Moon, Monitor } from 'lucide-react'
import { useTheme } from '@/providers/ThemeProvider'
import { useState, useRef, useEffect } from 'react'

export default function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const themes = [
    { value: 'light' as const, label: '亮色', icon: Sun },
    { value: 'dark' as const, label: '暗黑', icon: Moon },
    { value: 'system' as const, label: '跟随系统', icon: Monitor },
  ]

  const CurrentIcon = resolvedTheme === 'dark' ? Moon : Sun

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-center w-10 h-10 rounded-xl
                   bg-white/60 dark:bg-slate-800/60 backdrop-blur-md
                   border border-sky-200/60 dark:border-slate-600/60
                   hover:bg-white/80 dark:hover:bg-slate-700/80
                   transition-all duration-200 cursor-pointer"
        aria-label="切换主题"
      >
        <CurrentIcon className="w-5 h-5 text-sky-600 dark:text-sky-400" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-40 py-2
                        bg-white/90 dark:bg-slate-800/90 backdrop-blur-xl
                        border border-sky-200/60 dark:border-slate-600/60
                        rounded-xl shadow-xl z-50
                        animate-fade-in">
          {themes.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              onClick={() => {
                setTheme(value)
                setIsOpen(false)
              }}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-left
                         transition-colors duration-150 cursor-pointer
                         ${theme === value
                           ? 'bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300'
                           : 'hover:bg-sky-50 dark:hover:bg-slate-700/50 text-sky-800 dark:text-slate-200'
                         }`}
            >
              <Icon className="w-4 h-4" />
              <span className="text-sm font-medium">{label}</span>
              {theme === value && (
                <span className="ml-auto text-sky-500 dark:text-sky-400">✓</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
