'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import StrategyHeatmap from '@/components/analytics/StrategyHeatmap';
import { BarChart3, TrendingUp, Users, Target, Activity } from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    LineChart, Line
} from 'recharts';

export default function StrategyAnalyticsPage() {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

    // 获取策略概览数据
    const { data: metrics, isLoading } = useQuery({
        queryKey: ['strategy-metrics'],
        queryFn: async () => {
            const res = await axios.get(`${apiBase}/api/monitoring/metrics`);
            return res.data;
        }
    });

    // Mock 一些热力图数据 (实际应从 API 获取)
    const heatmapData = [
        { hook: "悬念式", body: "干货型", success_rate: 0.15, pulls: 120 },
        { hook: "悬念式", body: "故事型", success_rate: 0.08, pulls: 45 },
        { hook: "痛点式", body: "干货型", success_rate: 0.22, pulls: 200 },
        { hook: "痛点式", body: "避坑型", success_rate: 0.18, pulls: 150 },
        { hook: "利益式", body: "合集型", success_rate: 0.12, pulls: 80 },
        { hook: "提问式", body: "故事型", success_rate: 0.05, pulls: 30 },
    ];

    if (isLoading) return <div className="flex h-screen items-center justify-center">加载数据中...</div>;

    return (
        <div className="min-h-screen bg-background p-8">
            <div className="max-w-7xl mx-auto space-y-8">
                <header className="flex justify-between items-end">
                    <div>
                        <h1 className="text-4xl font-bold text-accent">策略进化看板</h1>
                        <p className="text-muted-foreground mt-2">基于 Thompson Sampling 和 GRPO 的实时策略表现分析</p>
                    </div>
                    <div className="text-right">
                        <span className="bg-primary/20 text-primary px-3 py-1 rounded-full text-xs font-bold border border-primary/30">
                            Live RL Training
                        </span>
                    </div>
                </header>

                {/* Top KPI Cards */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <KpiCard title="平均互动率" value="8.4%" icon={<TrendingUp />} color="text-green-400" />
                    <KpiCard title="探索比率 (Exploration)" value="12.5%" icon={<Target />} color="text-blue-400" />
                    <KpiCard title="覆盖受众" value="124.2k" icon={<Users />} color="text-purple-400" />
                    <KpiCard title="生成效能 (Score)" value="88.5" icon={<Activity />} color="text-orange-400" />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Main Heatmap */}
                    <div className="lg:col-span-2">
                        <StrategyHeatmap data={heatmapData} />
                    </div>

                    {/* Side Chart: Top 5 Categories */}
                    <div className="bg-card border border-border p-6 rounded-2xl">
                        <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                            <BarChart3 className="text-primary" />
                            高表现分类排名
                        </h3>
                        <div className="h-[300px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={[
                                    { name: "穿搭", value: 85 },
                                    { name: "美食", value: 72 },
                                    { name: "美妆", value: 68 },
                                    { name: "家居", value: 54 },
                                    { name: "萌宠", value: 45 },
                                ]}>
                                    <XAxis dataKey="name" stroke="#888" fontSize={12} />
                                    <YAxis stroke="#888" fontSize={12} />
                                    <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
                                    <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>

                {/* Bottom Line Chart: Trend Over Time */}
                <div className="bg-card border border-border p-6 rounded-2xl">
                    <h3 className="text-lg font-semibold mb-6">策略收益趋势 (Reward Curve)</h3>
                    <div className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={[
                                { time: 'T-10', reward: 0.2 },
                                { time: 'T-8', reward: 0.35 },
                                { time: 'T-6', reward: 0.42 },
                                { time: 'T-4', reward: 0.58 },
                                { time: 'T-2', reward: 0.75 },
                                { time: 'Now', reward: 0.82 },
                            ]}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#222" />
                                <XAxis dataKey="time" stroke="#888" />
                                <YAxis stroke="#888" />
                                <Tooltip />
                                <Legend />
                                <Line type="monotone" dataKey="reward" stroke="#10b981" strokeWidth={3} dot={{ r: 6 }} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>
        </div>
    );
}

function KpiCard({ title, value, icon, color }: any) {
    return (
        <div className="bg-card border border-border p-6 rounded-2xl hover:border-accent transition-all">
            <div className="flex justify-between items-start mb-4">
                <div className={`p-2 rounded-lg bg-accent/10 ${color}`}>{icon}</div>
            </div>
            <div className="text-2xl font-bold">{value}</div>
            <div className="text-xs text-muted-foreground mt-1 uppercase tracking-wider">{title}</div>
        </div>
    );
}
