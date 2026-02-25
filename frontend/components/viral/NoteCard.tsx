'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export function NoteCard({ note }: { note: any }) {
  return (
    <Card className="bg-white/5 border-white/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-white truncate">{note?.title || note?.note_id || '未命名笔记'}</div>
          <div className="text-xs text-white/60 mt-1 line-clamp-2">
            {note?.content || note?.desc || note?.summary || ''}
          </div>
        </div>
        {note?.is_viral ? <Badge className="border-purple-500/40 text-purple-300">爆款</Badge> : null}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-white/60">
        <div>互动率：{((note?.metrics?.engagement_rate || 0) * 100).toFixed(1)}%</div>
        <div>爆款分：{(note?.metrics?.viral_score || 0).toFixed?.(2) ?? note?.metrics?.viral_score ?? 0}</div>
        <div>点赞：{note?.metrics?.likes ?? note?.likes ?? 0}</div>
      </div>
    </Card>
  );
}

