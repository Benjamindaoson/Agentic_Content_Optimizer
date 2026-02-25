'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useRouter } from 'next/navigation';

interface ContentPreviewProps {
  content: {
    title?: string;
    hook?: string;
    body?: string;
    cta?: string;
    score?: number;
    policy_id?: string;
    action?: {
      hook?: string;
      body?: string;
      cta?: string;
      hook_name?: string;
      body_name?: string;
      cta_name?: string;
    };
    cover_candidates?: Array<{ cover_id: string; image_path: string }>;
  };
  traceId?: string | null;
  onPublish?: () => void;
  onSchedule?: () => void;
}

export function ContentPreview({ content, traceId, onPublish, onSchedule }: ContentPreviewProps) {
  const router = useRouter();
  const score = content.score ?? 0;
  const action = content.action ?? {};

  return (
    <div className="space-y-4">
      {/* 小红书卡片预览 */}
      <div className="max-w-sm mx-auto">
        <div className="rounded-xl overflow-hidden bg-gradient-to-b from-white/5 to-white/[0.02] border border-white/10 shadow-2xl">
          {/* 封面区域 3:4 */}
          <div className="aspect-[3/4] bg-gradient-to-br from-purple-500/20 to-pink-500/20 relative flex items-center justify-center">
            {content.cover_candidates && content.cover_candidates.length > 0 ? (
              <div className="text-sm text-white/60">
                {content.cover_candidates.length} 张封面已生成
              </div>
            ) : (
              <div className="text-center text-white/40 px-6">
                <div className="text-3xl mb-2">📸</div>
                <div className="text-xs">封面待生成或手动上传</div>
              </div>
            )}
          </div>

          {/* 内容区 */}
          <div className="p-4 space-y-3">
            <h3 className="font-bold text-base text-white leading-tight">
              {content.title || '标题生成中...'}
            </h3>

            {content.hook && (
              <p className="text-sm text-purple-300 font-medium">
                {content.hook}
              </p>
            )}

            {content.body && (
              <p className="text-sm text-white/70 line-clamp-4 whitespace-pre-wrap">
                {content.body}
              </p>
            )}

            {content.cta && (
              <p className="text-sm text-pink-300 font-medium">
                {content.cta}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* 策略标签 */}
      <div className="flex gap-2 flex-wrap justify-center">
        {action.hook_name && (
          <Badge variant="outline" className="text-xs border-purple-500/50 text-purple-300">
            Hook: {action.hook_name}
          </Badge>
        )}
        {action.body_name && (
          <Badge variant="outline" className="text-xs border-blue-500/50 text-blue-300">
            Body: {action.body_name}
          </Badge>
        )}
        {action.cta_name && (
          <Badge variant="outline" className="text-xs border-pink-500/50 text-pink-300">
            CTA: {action.cta_name}
          </Badge>
        )}
      </div>

      {/* 质量评分 */}
      <div className="text-center space-y-1">
        <div className="text-xs text-white/40">Critic 评分</div>
        <div className={cn(
          "text-3xl font-bold",
          score >= 8 ? "text-green-400" :
          score >= 6 ? "text-yellow-400" : "text-red-400"
        )}>
          {score > 0 ? `${score.toFixed(1)}/10` : '—'}
        </div>
      </div>

      {/* 快捷操作 */}
      <div className="flex gap-2 justify-center flex-wrap pt-2">
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            const text = [content.title, content.hook, content.body, content.cta]
              .filter(Boolean)
              .join('\n\n');
            navigator.clipboard.writeText(text);
          }}
          className="text-xs"
        >
          📋 复制文案
        </Button>
        {traceId && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              router.push(`/publish?traceId=${encodeURIComponent(traceId)}`);
            }}
            className="text-xs text-green-300"
          >
            🚀 跳转发布
          </Button>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-3 justify-center pt-2">
        {onSchedule && (
          <Button
            onClick={onSchedule}
            className="bg-purple-600 hover:bg-purple-700"
          >
            排程发布
          </Button>
        )}
        {onPublish && (
          <Button
            variant="outline"
            onClick={onPublish}
          >
            保存草稿
          </Button>
        )}
      </div>
    </div>
  );
}
