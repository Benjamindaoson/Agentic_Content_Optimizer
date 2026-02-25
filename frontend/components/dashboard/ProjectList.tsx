'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export function ProjectList({
  projects,
  onRefresh,
}: {
  projects: any[];
  onRefresh?: () => void;
}) {
  if (!projects || projects.length === 0) {
    return (
      <div className="text-sm text-white/60">
        暂无项目。
        {onRefresh ? (
          <Button variant="ghost" size="sm" className="ml-2" onClick={onRefresh}>
            刷新
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {projects.map((p, idx) => (
        <Card key={p?.id ?? idx} className="bg-white/5 border-white/10 p-4">
          <div className="text-sm font-medium text-white">{p?.name ?? p?.title ?? `Project #${idx + 1}`}</div>
          <div className="text-xs text-white/60 mt-1">{p?.description ?? ''}</div>
        </Card>
      ))}
    </div>
  );
}

