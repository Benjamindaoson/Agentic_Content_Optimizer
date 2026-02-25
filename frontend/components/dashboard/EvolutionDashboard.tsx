'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { apiClient } from '@/lib/api';

export function EvolutionDashboard() {
  const thompsonQuery = useQuery({
    queryKey: ['dashboard', 'thompson', 30],
    queryFn: async () => (await apiClient.get('/v1/dashboard/thompson-sampling/history?days=30')).data,
  });

  const rewardQuery = useQuery({
    queryKey: ['dashboard', 'reward', 30],
    queryFn: async () => (await apiClient.get('/v1/dashboard/reward/trends?days=30')).data,
  });

  const qualityQuery = useQuery({
    queryKey: ['dashboard', 'quality', 'weekly'],
    queryFn: async () => (await apiClient.get('/v1/dashboard/quality/distribution?window=weekly')).data,
  });

  const abQuery = useQuery({
    queryKey: ['dashboard', 'ab'],
    queryFn: async () =>
      (await apiClient.get('/v1/dashboard/ab-comparison?baseline_date=2026-01-01&current_date=2026-02-01')).data,
  });

  const thompsonData = useMemo(
    () =>
      (thompsonQuery.data?.history || []).map((item: any) => ({
        time: item.time,
        hook_focus: item.arms?.hook_focus ?? 0,
        cta_focus: item.arms?.cta_focus ?? 0,
        story_focus: item.arms?.story_focus ?? 0,
        balanced: item.arms?.balanced ?? 0,
      })),
    [thompsonQuery.data]
  );

  const rewardData = rewardQuery.data?.trends || [];

  const qualityData = useMemo(
    () =>
      (qualityQuery.data?.distribution || []).map((item: any) => ({
        bucket: item.bucket,
        min: item.min,
        q1: item.q1,
        median: item.median,
        q3: item.q3,
        max: item.max,
        iqrBase: item.q1,
        iqrSize: item.q3 - item.q1,
      })),
    [qualityQuery.data]
  );

  const ab = abQuery.data;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-xl border border-white/10 bg-black/40 p-4">
          <h3 className="text-sm font-medium text-white/90 mb-3">Thompson Sampling 臂选择分布</h3>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={thompsonData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis dataKey="time" stroke="rgba(255,255,255,0.5)" />
                <YAxis stroke="rgba(255,255,255,0.5)" />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="hook_focus" stackId="1" stroke="#22d3ee" fill="#22d3ee" />
                <Area type="monotone" dataKey="cta_focus" stackId="1" stroke="#a78bfa" fill="#a78bfa" />
                <Area type="monotone" dataKey="story_focus" stackId="1" stroke="#34d399" fill="#34d399" />
                <Area type="monotone" dataKey="balanced" stackId="1" stroke="#f59e0b" fill="#f59e0b" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-black/40 p-4">
          <h3 className="text-sm font-medium text-white/90 mb-3">奖励趋势（含置信区间）</h3>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rewardData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis dataKey="time" stroke="rgba(255,255,255,0.5)" />
                <YAxis stroke="rgba(255,255,255,0.5)" />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="real_world" stroke="#22d3ee" dot={false} name="真实世界奖励" />
                <Line type="monotone" dataKey="quality" stroke="#34d399" dot={false} name="质量奖励" />
                <Line type="monotone" dataKey="blended" stroke="#a78bfa" dot={false} name="综合奖励" />
                <Line type="monotone" dataKey="ci_lower" stroke="#64748b" dot={false} strokeDasharray="6 4" name="CI 下界" />
                <Line type="monotone" dataKey="ci_upper" stroke="#64748b" dot={false} strokeDasharray="6 4" name="CI 上界" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-xl border border-white/10 bg-black/40 p-4">
          <h3 className="text-sm font-medium text-white/90 mb-3">内容质量分布（箱线近似）</h3>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={qualityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis dataKey="bucket" stroke="rgba(255,255,255,0.5)" />
                <YAxis domain={[0, 100]} stroke="rgba(255,255,255,0.5)" />
                <Tooltip />
                <Legend />
                <Bar dataKey="iqrBase" stackId="q" fill="transparent" />
                <Bar dataKey="iqrSize" stackId="q" fill="#6366f1" name="Q1-Q3" />
                <Line type="monotone" dataKey="median" stroke="#22d3ee" dot={{ r: 2 }} name="Median" />
                <Line type="monotone" dataKey="min" stroke="#94a3b8" dot={false} name="Min" />
                <Line type="monotone" dataKey="max" stroke="#94a3b8" dot={false} name="Max" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-black/40 p-4">
          <h3 className="text-sm font-medium text-white/90 mb-3">A/B 对比（优化前 vs 后）</h3>
          <div className="grid grid-cols-1 gap-3">
            <div className="rounded-lg border border-white/10 p-3">
              <div className="text-xs text-white/60">互动率</div>
              <div className="mt-1 text-sm text-white">
                {(ab?.baseline?.engagement_rate * 100 || 0).toFixed(2)}% → {(ab?.current?.engagement_rate * 100 || 0).toFixed(2)}%
              </div>
              <div className="text-xs text-emerald-300 mt-1">提升 {ab?.improvements?.engagement_rate_pct ?? 0}%</div>
            </div>
            <div className="rounded-lg border border-white/10 p-3">
              <div className="text-xs text-white/60">质量分</div>
              <div className="mt-1 text-sm text-white">
                {(ab?.baseline?.quality_score || 0).toFixed(1)} → {(ab?.current?.quality_score || 0).toFixed(1)}
              </div>
              <div className="text-xs text-emerald-300 mt-1">提升 {ab?.improvements?.quality_score_pct ?? 0}%</div>
            </div>
            <div className="rounded-lg border border-white/10 p-3">
              <div className="text-xs text-white/60">生成耗时</div>
              <div className="mt-1 text-sm text-white">
                {ab?.baseline?.generation_latency_ms || 0}ms → {ab?.current?.generation_latency_ms || 0}ms
              </div>
              <div className="text-xs text-emerald-300 mt-1">变化 {ab?.improvements?.generation_latency_pct ?? 0}%</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
