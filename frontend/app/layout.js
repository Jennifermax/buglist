import Link from 'next/link'
import './globals.css'

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

            <nav className="sidebar-nav">
              <Link href="/" className="nav-item active">
                <span className="nav-icon">▸</span>
                测试平台
              </Link>
              <Link href="/settings" className="nav-item">
                <span className="nav-icon">⚙</span>
                设置
              </Link>
            </nav>

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
