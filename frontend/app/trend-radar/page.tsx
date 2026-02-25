'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface TrendItem {
  keyword: string;
  score: number;
  heat: number;
  sources: string[];
  category: string;
  account_fit: number;
}

const SOURCE_COLORS: Record<string, string> = {
  weibo: 'bg-orange-500/20 text-orange-300 border-orange-500/50',
  baidu: 'bg-blue-500/20 text-blue-300 border-blue-500/50',
  xhs: 'bg-pink-500/20 text-pink-300 border-pink-500/50',
};

export default function TrendRadarPage() {
  const router = useRouter();
  const [niche, setNiche] = useState('');
  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchTrends = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: '50' });
      if (niche.trim()) params.set('niche', niche.trim());

      const res = await fetch(`/api/v1/trends/radar?${params}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
      });
      const data = await res.json();
      setTrends(data.trends ?? []);
    } catch {
      console.error('Failed to fetch trends');
    } finally {
      setLoading(false);
    }
  }, [niche]);

  const goGenerate = (keyword: string) => {
    router.push(`/control-center?topic=${encodeURIComponent(keyword)}`);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold mb-1">热点雷达</h1>
          <p className="text-white/40 text-sm">
            跨平台实时热搜聚合。选中热点 → 一键跳转生成内容。
          </p>
        </div>

        {/* 搜索栏 */}
        <div className="flex gap-3 items-center">
          <Input
            placeholder="输入你的账号定位（如：护肤、穿搭、程序员）"
            value={niche}
            onChange={(e) => setNiche(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchTrends()}
            className="bg-white/5 border-white/10 placeholder:text-white/30"
          />
          <Button
            onClick={fetchTrends}
            disabled={loading}
            className="bg-purple-600 hover:bg-purple-700 whitespace-nowrap"
          >
            {loading ? '扫描中...' : '扫描热点'}
          </Button>
        </div>

        {/* 热点列表 */}
        {trends.length > 0 && (
          <div className="space-y-2">
            {trends.map((t, i) => (
              <div
                key={`${t.keyword}-${i}`}
                className="flex items-center gap-4 p-3 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:border-purple-500/30 transition-colors group"
              >
                <span className="text-white/30 text-sm w-6 text-right shrink-0">
                  {i + 1}
                </span>

                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{t.keyword}</div>
                  <div className="flex gap-1.5 mt-1">
                    {t.sources.map((s) => (
                      <Badge
                        key={s}
                        variant="outline"
                        className={`text-[10px] ${SOURCE_COLORS[s] ?? 'text-white/50'}`}
                      >
                        {s}
                      </Badge>
                    ))}
                    {t.category && (
                      <Badge variant="outline" className="text-[10px] text-white/40 border-white/10">
                        {t.category}
                      </Badge>
                    )}
                  </div>
                </div>

                {/* 评分柱 */}
                <div className="w-24 shrink-0">
                  <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all"
                      style={{ width: `${Math.round(t.score * 100)}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-white/30 mt-0.5 text-right">
                    {(t.score * 100).toFixed(0)}分
                  </div>
                </div>

                {t.account_fit > 0.6 && (
                  <Badge className="bg-green-500/20 text-green-300 border-green-500/50 text-[10px] shrink-0">
                    匹配
                  </Badge>
                )}

                <Button
                  size="sm"
                  variant="ghost"
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-purple-300 hover:text-purple-100 shrink-0"
                  onClick={() => goGenerate(t.keyword)}
                >
                  生成 →
                </Button>
              </div>
            ))}
          </div>
        )}

        {trends.length === 0 && !loading && (
          <div className="text-center text-white/20 py-20">
            点击「扫描热点」开始捕获全网热搜
          </div>
        )}
      </div>
    </div>
  );
}
