/**
 * Viral Flywheel - 爆款追踪页面
 *
 * 功能：
 * 1. 触发爆款追踪任务
 * 2. 实时显示采集进度
 * 3. 展示爆款笔记列表
 * 4. 笔记详情预览
 */

'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Sparkles, Search, Filter, TrendingUp } from 'lucide-react';
import { api } from '@/lib/api';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { NoteCard } from '@/components/viral/NoteCard';
import { TrackingDialog } from '@/components/viral/TrackingDialog';

export default function ViralPage() {
  const [category, setCategory] = useState('美妆');
  const [timeWindow, setTimeWindow] = useState('7d');
  const [isTracking, setIsTracking] = useState(false);
  const [trackingProgress, setTrackingProgress] = useState(0);
  const [filters, setFilters] = useState({
    viral: true,
    category: '',
    search: ''
  });

  const [wsError, setWsError] = useState<string | null>(null);
  const [trackError, setTrackError] = useState<string | null>(null);

  // WebSocket 连接
  const { lastMessage, isConnected } = useWebSocket('/ws', {
    onMessage: (data) => {
      if (data.type === 'task_status' && data.status === 'running') {
        setTrackingProgress(data.progress || 0);
      } else if (data.type === 'task_status' && data.status === 'completed') {
        setIsTracking(false);
        setTrackingProgress(1);
        refetch();
      } else if (data.type === 'task_status' && data.status === 'failed') {
        setIsTracking(false);
        setTrackError(data.error || '追踪任务失败');
      }
    },
    onError: () => {
      setWsError('WebSocket 连接失败，实时进度不可用');
    },
    onOpen: () => {
      setWsError(null);
    }
  });

  // 查询爆款笔记列表
  const { data: notesData, isLoading, refetch } = useQuery({
    queryKey: ['viral-notes', filters],
    queryFn: () => api.getNotes({
      viral: filters.viral,
      category: filters.category || undefined,
      limit: 20
    })
  });

  // 触发追踪任务
  const trackMutation = useMutation({
    mutationFn: () => api.trackViralContent({
      category,
      time_window: timeWindow,
      limit: 100
    }),
    onSuccess: () => {
      setIsTracking(true);
      setTrackingProgress(0);
      setTrackError(null);
    },
    onError: (err: any) => {
      setTrackError(err?.response?.data?.detail || err.message || '启动追踪失败');
    }
  });

  const notes: any[] = notesData?.notes || [];

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <div className="border-b border-white/10 bg-black/50 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Sparkles className="w-6 h-6 text-purple-400" />
              <h1 className="text-xl font-semibold">爆款追踪</h1>
            </div>

            <Button
              onClick={() => trackMutation.mutate()}
              disabled={isTracking}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {isTracking ? '追踪中...' : '开始追踪'}
            </Button>
          </div>

          {/* 追踪进度 */}
          {isTracking && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-white/60">采集进度</span>
                <span className="text-white/90">{Math.round(trackingProgress * 100)}%</span>
              </div>
              <Progress value={trackingProgress * 100} className="h-1" />
            </div>
          )}
        </div>
      </div>

      {/* Error/Status Messages */}
      {(wsError || trackError) && (
        <div className="max-w-7xl mx-auto px-6 pt-4">
          {trackError && (
            <div className="mb-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center justify-between">
              <span>{trackError}</span>
              <button onClick={() => setTrackError(null)} className="text-red-400/60 hover:text-red-400 ml-4">✕</button>
            </div>
          )}
          {wsError && !trackError && (
            <div className="mb-2 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-sm">
              {wsError}
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="flex-1">
            <Input
              placeholder="搜索笔记..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              className="bg-white/5 border-white/10"
              icon={<Search className="w-4 h-4" />}
            />
          </div>

          <Select
            value={filters.category}
            onChange={(value) => setFilters({ ...filters, category: value })}
            options={[
              { value: '', label: '全部分类' },
              { value: '美妆', label: '美妆' },
              { value: '穿搭', label: '穿搭' },
              { value: '美食', label: '美食' },
              { value: '旅行', label: '旅行' }
            ]}
            className="w-40"
          />

          <Button
            variant="outline"
            onClick={() => setFilters({ ...filters, viral: !filters.viral })}
            className={filters.viral ? 'border-purple-500 text-purple-400' : ''}
          >
            <TrendingUp className="w-4 h-4 mr-2" />
            仅爆款
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <Card className="bg-white/5 border-white/10 p-4">
            <div className="text-sm text-white/60 mb-1">总笔记数</div>
            <div className="text-2xl font-semibold">{notesData?.total || 0}</div>
          </Card>
          <Card className="bg-white/5 border-white/10 p-4">
            <div className="text-sm text-white/60 mb-1">爆款笔记</div>
            <div className="text-2xl font-semibold text-purple-400">
              {notes.filter((n: any) => n.is_viral).length}
            </div>
          </Card>
          <Card className="bg-white/5 border-white/10 p-4">
            <div className="text-sm text-white/60 mb-1">平均爆款分</div>
            <div className="text-2xl font-semibold text-green-400">
              {notes.length > 0
                ? (notes.reduce((sum: number, n: any) => sum + (n.metrics?.viral_score || 0), 0) / notes.length).toFixed(2)
                : '0.00'}
            </div>
          </Card>
          <Card className="bg-white/5 border-white/10 p-4">
            <div className="text-sm text-white/60 mb-1">平均互动率</div>
            <div className="text-2xl font-semibold text-blue-400">
              {notes.length > 0
                ? (notes.reduce((sum: number, n: any) => sum + (n.metrics?.engagement_rate || 0), 0) / notes.length * 100).toFixed(1)
                : '0.0'}%
            </div>
          </Card>
        </div>

        {/* Notes Grid */}
        {isLoading ? (
          <div className="text-center py-12 text-white/60">加载中...</div>
        ) : notes.length === 0 ? (
          <div className="text-center py-12 text-white/60">
            暂无数据，点击"开始追踪"采集爆款笔记
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {notes.map((note: any) => (
              <NoteCard key={note.note_id} note={note} />
            ))}
          </div>
        )}
      </div>

      {/* Tracking Dialog */}
      <TrackingDialog
        open={isTracking}
        category={category}
        timeWindow={timeWindow}
        progress={trackingProgress}
        onCategoryChange={setCategory}
        onTimeWindowChange={setTimeWindow}
      />
    </div>
  );
}
