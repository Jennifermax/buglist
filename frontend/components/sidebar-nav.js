'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'

const NAV_ITEMS = [
  { href: '/', label: '测试平台', icon: '▸', match: path => path === '/' },
  { href: '/chat', label: '聊天 Chat', icon: '✦', match: path => path === '/chat' },
  { href: '/vision', label: '视觉识别', icon: '◈', match: path => path === '/vision' },
  { href: '/settings', label: '设置', icon: '⚙', match: path => path === '/settings' },
]

export default function SidebarNav() {
  const pathname = usePathname()
  const router = useRouter()

  const handleLogout = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('isLoggedIn')
      localStorage.removeItem('username')
      router.push('/login')
    }
  }

  return (
    <>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map(item => {
          const isActive = item.match(pathname)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div style={{ padding: '16px 12px', marginTop: 'auto' }}>
        <button
          onClick={handleLogout}
          className="nav-item"
          style={{
            width: '100%',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontFamily: 'inherit',
            fontSize: 'inherit'
          }}
        >
          <span className="nav-icon">⎋</span>
          退出登录
        </button>
      </div>
    </>
  )
}
