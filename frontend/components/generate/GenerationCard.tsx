'use client';

import { Copy, Download } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export function GenerationCard({
  generation,
  rank,
}: {
  generation: any;
  rank: number;
}) {
  const title = generation?.title || generation?.content?.title || `候选 #${rank}`;
  const body = generation?.content || generation?.text || generation?.body || generation?.generated_text || generation?.output || '';
  const score = generation?.score ?? generation?.quality_score ?? generation?.final_score;

  const copy = async () => {
    const text = typeof body === 'string' ? body : JSON.stringify(body, null, 2);
    await navigator.clipboard.writeText(text);
  };

  const download = () => {
    const text = typeof body === 'string' ? body : JSON.stringify(body, null, 2);
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title || 'generation'}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="bg-white/5 border-white/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-white truncate">{title}</div>
          <div className="text-xs text-white/60 mt-1">
            排名 #{rank}
            {score != null ? <span className="ml-2">Score: {Number(score).toFixed?.(2) ?? score}</span> : null}
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="ghost" size="sm" onClick={copy} className="px-2">
            <Copy className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={download} className="px-2">
            <Download className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <pre className="mt-3 text-xs text-white/70 whitespace-pre-wrap break-words bg-black/30 border border-white/10 rounded-lg p-3">
        {typeof body === 'string' ? body : JSON.stringify(body, null, 2)}
      </pre>
    </Card>
  );
}

