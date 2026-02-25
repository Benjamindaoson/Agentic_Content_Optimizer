'use client';

import { Card } from '@/components/ui/card';
import { Select } from '@/components/ui/select';

export function TrackingDialog({
  open,
  category,
  timeWindow,
  progress,
  onCategoryChange,
  onTimeWindowChange,
}: {
  open: boolean;
  category: string;
  timeWindow: string;
  progress: number;
  onCategoryChange: (v: string) => void;
  onTimeWindowChange: (v: string) => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/70" />
      <div className="absolute left-1/2 top-1/2 w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2">
        <Card className="bg-[#0c0c12] border-white/10 p-4">
          <div className="text-sm font-medium text-white">追踪任务进行中</div>
          <div className="text-xs text-white/60 mt-1">进度：{Math.round(progress * 100)}%</div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-white/60 mb-1">分类</div>
              <Select
                value={category}
                onChange={onCategoryChange}
                options={[
                  { value: '美妆', label: '美妆' },
                  { value: '穿搭', label: '穿搭' },
                  { value: '美食', label: '美食' },
                  { value: '旅行', label: '旅行' },
                ]}
              />
            </div>
            <div>
              <div className="text-xs text-white/60 mb-1">时间窗口</div>
              <Select
                value={timeWindow}
                onChange={onTimeWindowChange}
                options={[
                  { value: '24h', label: '24 小时' },
                  { value: '7d', label: '7 天' },
                  { value: '30d', label: '30 天' },
                ]}
              />
            </div>
          </div>
          <div className="mt-4 text-xs text-white/50">该对话框为占位实现，用于保证页面可编译。</div>
        </Card>
      </div>
    </div>
  );
}

