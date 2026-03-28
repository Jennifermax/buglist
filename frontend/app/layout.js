'use client'
import { useState, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import './globals.css'
import SidebarNav from '../components/sidebar-nav'
import AuthCheck from '../components/auth-check'
import BuglistLogo from '../components/buglist-logo'

export default function RootLayout({ children }) {
  const pathname = usePathname()
  const isLoginPage = pathname === '/login'
  const [theme, setTheme] = useState('light')

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedTheme = localStorage.getItem('theme') || 'light'
      setTheme(savedTheme)
      document.documentElement.setAttribute('data-theme', savedTheme)
    }
  }, [])

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    localStorage.setItem('theme', newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
  }

  return (
    <html lang="zh-CN">
      <body>
        {isLoginPage ? (
          // Login page without sidebar
          children
        ) : (
          // Main app with sidebar and auth check
          <AuthCheck>
            {/* Theme Toggle Button */}
            <button className="theme-toggle-main" onClick={toggleTheme}>
              {theme === 'light' ? '🌙' : '☀️'}
            </button>

            <div className="app-layout">
              {/* Sidebar */}
              <aside className="sidebar">
                <div className="sidebar-logo">
                  <h1>
                    <span className="logo-icon">
                      <BuglistLogo size={28} />
                    </span>
                    <span className="brand-text-animated">
                      {'Buglist'.split('').map((char, index) => (
                        <span key={index}>
                          {char}
                        </span>
                      ))}
                    </span>
                  </h1>
                </div>

                <SidebarNav />

                <div className="sidebar-footer">
                  <p className="version">v1.0.0</p>
                </div>
              </aside>

              {/* Main Content */}
              <main className="main-content">
                {children}
              </main>
            </div>
          </AuthCheck>
        )}
      </body>
    </html>
  )
}
