import Link from 'next/link'
import './globals.css'
import SidebarNav from '../components/sidebar-nav'

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="app-layout">
          {/* Sidebar */}
          <aside className="sidebar">
            <div className="sidebar-logo">
              <h1>
                <span className="logo-icon">⬡</span>
                Buglist
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
      </body>
    </html>
  )
}
