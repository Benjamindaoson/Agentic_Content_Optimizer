'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuthStore } from '@/lib/stores/auth.store'

export default function RegisterPage() {
  const router = useRouter()
  const { register, isLoading, error, clearError } = useAuthStore()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [localError, setLocalError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    setLocalError('')

    // 验证密码
    if (password !== confirmPassword) {
      setLocalError('两次输入的密码不一致')
      return
    }

    if (password.length < 8) {
      setLocalError('密码长度至少为 8 个字符')
      return
    }

    try {
      await register(email, password, fullName || undefined)
      // 注册成功，跳转到登录页
      router.push('/login?registered=true')
    } catch (error) {
      // 错误已在 store 中处理
    }
  }

  const displayError = localError || error

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-8 p-8">
        {/* Logo */}
        <div className="text-center">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-transparent">
            Growth Flywheel 2.5
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            AI 驱动的内容策略进化引擎
          </p>
        </div>

        {/* 注册表单 */}
        <div className="mt-8 space-y-6 rounded-lg border border-border bg-card p-8">
          <div>
            <h2 className="text-2xl font-semibold">注册</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              创建您的账号，开始使用
            </p>
          </div>

          {displayError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {displayError}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium">
                姓名 (可选)
              </label>
              <input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="张三"
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium">
                邮箱
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="your@email.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium">
                密码
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="至少 8 个字符"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                密码必须包含至少一个字母和一个数字
              </p>
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium">
                确认密码
              </label>
              <input
                id="confirmPassword"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="再次输入密码"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? '注册中...' : '注册'}
            </button>
          </form>

          <div className="text-center text-sm">
            <span className="text-muted-foreground">已有账号？</span>{' '}
            <Link href="/login" className="text-primary hover:underline">
              立即登录
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
