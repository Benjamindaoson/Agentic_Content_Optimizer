'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/lib/stores/auth.store'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { isAuthenticated, isLoading, fetchCurrentUser } = useAuthStore()

  useEffect(() => {
    // 尝试获取当前用户信息
    fetchCurrentUser()
  }, [fetchCurrentUser])

  useEffect(() => {
    // 如果未登录且不在加载中，跳转到登录页
    if (!isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [isAuthenticated, isLoading, router])

  // 加载中显示加载状态
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent"></div>
          <p className="mt-4 text-sm text-muted-foreground">加载中...</p>
        </div>
      </div>
    )
  }

  // 未登录不渲染内容
  if (!isAuthenticated) {
    return null
  }

  // 已登录，渲染子组件
  return <>{children}</>
}
