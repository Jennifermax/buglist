'use client'
import { useEffect, useState } from 'react'
import './theme-toggle.css'

export default function ThemeToggle() {
  const [theme, setTheme] = useState('light')
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    // Get theme from localStorage or default to light
    const savedTheme = localStorage.getItem('theme') || 'light'
    setTheme(savedTheme)
    document.documentElement.setAttribute('data-theme', savedTheme)
  }, [])

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    localStorage.setItem('theme', newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
  }

  // Avoid hydration mismatch
  if (!mounted) {
    return (
      <button className="theme-toggle" disabled>
        <span className="theme-icon">☀</span>
      </button>
    )
  }

  return (
    <button
      className="theme-toggle"
      onClick={toggleTheme}
      aria-label={`切换到${theme === 'light' ? '深色' : '浅色'}模式`}
    >
      <div className="theme-toggle-track">
        <span className={`theme-icon sun ${theme === 'light' ? 'active' : ''}`}>☀</span>
        <span className={`theme-icon moon ${theme === 'dark' ? 'active' : ''}`}>☾</span>
      </div>
      <div className={`theme-toggle-thumb ${theme}`}></div>
    </button>
  )
}
