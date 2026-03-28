'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const NAV_ITEMS = [
  { href: '/', label: '测试平台', icon: '▸', match: path => path === '/' },
  { href: '/settings', label: '设置', icon: '⚙', match: path => path === '/settings' },
]

export default function SidebarNav() {
  const pathname = usePathname()

  return (
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
  )
}
