'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Wand2 } from 'lucide-react';
import { ConfigPanel } from '@/components/config/ConfigPanel';

export default function GeneratePage() {
  const [generated, setGenerated] = useState<any>(null);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <div className="border-b border-white/10 bg-black/50 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Wand2 className="w-6 h-6 text-purple-400" />
              <h1 className="text-xl font-semibold">自动生成</h1>
            </div>
            <Link
              href="/control-center"
              className="text-sm text-white/70 hover:text-white underline underline-offset-4"
            >
              打开控制中心
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ConfigPanel onGenerated={(r) => setGenerated(r)} />

          <div className="rounded-xl border border-white/10 bg-black/40 p-4">
            <div className="text-sm text-white/80 mb-2">最新生成结果（原样展示）</div>
            <pre className="text-xs text-white/70 whitespace-pre-wrap break-words overflow-x-auto">
              {generated ? JSON.stringify(generated, null, 2) : '尚未生成。'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
