'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Copy } from 'lucide-react';

export function CoverSuggestion({
  suggestion,
  rank,
}: {
  suggestion: any;
  rank: number;
}) {
  const title = suggestion?.title || `封面建议 #${rank}`;
  const lines = suggestion?.lines || suggestion?.texts || suggestion?.copy || suggestion?.suggestion || suggestion;
  const text = typeof lines === 'string' ? lines : Array.isArray(lines) ? lines.join('\n') : JSON.stringify(lines, null, 2);

  const copy = async () => {
    await navigator.clipboard.writeText(text);
  };

  return (
    <Card className="bg-white/5 border-white/10 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-white truncate">
          {title} <span className="text-xs text-white/50 font-normal">(#{rank})</span>
        </div>
        <Button variant="ghost" size="sm" onClick={copy} className="px-2">
          <Copy className="w-4 h-4" />
        </Button>
      </div>
      <pre className="mt-3 text-xs text-white/70 whitespace-pre-wrap break-words bg-black/30 border border-white/10 rounded-lg p-3">
        {text}
      </pre>
    </Card>
  );
}

