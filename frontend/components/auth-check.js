'use client'
import { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'

export default function AuthCheck({ children }) {
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const isLoggedIn = localStorage.getItem('isLoggedIn')

      // If not logged in and not on login page, redirect to login
      if (isLoggedIn !== 'true' && pathname !== '/login') {
        router.push('/login')
      }
    }
  }, [pathname, router])

  return <>{children}</>
}
