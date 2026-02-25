'use client'

import './globals.css'
import { Inter } from 'next/font/google'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { TopNav } from '@/components/layout/TopNav'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: 1,
      },
    },
  }))

  return (
    <html lang="zh-CN" className="dark">
      <head>
        <title>Growth Flywheel 3.0</title>
        <meta name="description" content="AI 驱动的内容策略进化引擎" />
      </head>
      <body className={inter.className}>
        <QueryClientProvider client={queryClient}>
          <TopNav />
          {children}
        </QueryClientProvider>
      </body>
    </html>
  )
}
