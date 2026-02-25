'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

interface PublishRecord {
  traceId: string;
  platformPostUrl: string;
  publishedAt: string;
}

export default function PublishPage() {
  const searchParams = useSearchParams();
  const urlTraceId = searchParams?.get('traceId') ?? '';

  const [traceId, setTraceId] = useState(urlTraceId);
  const [platformPostUrl, setPlatformPostUrl] = useState('');

  useEffect(() => {
    if (urlTraceId) setTraceId(urlTraceId);
  }, [urlTraceId]);
  const [records, setRecords] = useState<PublishRecord[]>([]);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState('');

  const markPublished = async () => {
    if (!traceId.trim()) {
      setFeedback('请输入 Trace ID');
      return;
    }

    setSaving(true);
    try {
      setRecords((prev) => [
        {
          traceId: traceId.trim(),
          platformPostUrl: platformPostUrl.trim(),
          publishedAt: new Date().toLocaleString('zh-CN'),
        },
        ...prev,
      ]);

      setFeedback(`已标记 ${traceId} 为已发布`);
      setTraceId('');
      setPlatformPostUrl('');
    } finally {
      setSaving(false);
    }
  };

  const submitOutcome = async (record: PublishRecord) => {
    try {
      const res = await fetch('/api/v1/outcomes/upsert', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify({
          trace_id: record.traceId,
          time_bucket: '24h',
          impressions: 0,
          likes: 0,
          comments: 0,
          saves: 0,
          shares: 0,
          follows: 0,
        }),
      });
      const data = await res.json();
      setFeedback(
        data.success
          ? `Outcome 数据已提交（rl_synced: ${data.rl_synced}）`
          : '提交失败'
      );
    } catch {
      setFeedback('网络错误');
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      <div className="max-w-3xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold mb-1">发布管理</h1>
          <p className="text-white/40 text-sm">
            手动标记已发布的内容，然后回填平台数据形成 RL 闭环。
          </p>
          <p className="text-white/30 text-xs mt-2">
            流程：生成内容 → 手动发布到小红书 → 在这里标记 → 24h 后回填效果数据 → RL 自动学习
          </p>
        </div>

        {/* 标记发布 */}
        <div className="rounded-xl border border-white/10 bg-black/40 p-6 space-y-4">
          <h2 className="text-sm font-medium text-white/80">标记已发布</h2>
          <div className="flex gap-3">
            <Input
              placeholder="Trace ID（生成结果中的 trace_id）"
              value={traceId}
              onChange={(e) => setTraceId(e.target.value)}
              className="bg-white/5 border-white/10"
            />
            <Input
              placeholder="平台帖子链接（可选）"
              value={platformPostUrl}
              onChange={(e) => setPlatformPostUrl(e.target.value)}
              className="bg-white/5 border-white/10"
            />
            <Button
              onClick={markPublished}
              disabled={saving}
              className="bg-green-600 hover:bg-green-700 whitespace-nowrap"
            >
              标记发布
            </Button>
          </div>
          {feedback && (
            <div className="text-xs text-purple-300">{feedback}</div>
          )}
        </div>

        {/* 发布记录 */}
        {records.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-medium text-white/80">本次会话记录</h2>
            {records.map((r, i) => (
              <div
                key={`${r.traceId}-${i}`}
                className="flex items-center gap-4 p-4 rounded-lg border border-white/[0.06] bg-white/[0.02]"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-mono truncate">{r.traceId}</div>
                  {r.platformPostUrl && (
                    <a
                      href={r.platformPostUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-purple-400 hover:underline"
                    >
                      {r.platformPostUrl}
                    </a>
                  )}
                  <div className="text-xs text-white/30 mt-1">{r.publishedAt}</div>
                </div>
                <Badge className="bg-green-500/20 text-green-300 border-green-500/50">已发布</Badge>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => submitOutcome(r)}
                  className="text-xs"
                >
                  回填数据
                </Button>
              </div>
            ))}
          </div>
        )}

        <div className="text-center text-white/20 text-xs py-4">
          回填效果数据后，Thompson Sampling 会自动更新策略权重
        </div>
      </div>
    </div>
  );
}
