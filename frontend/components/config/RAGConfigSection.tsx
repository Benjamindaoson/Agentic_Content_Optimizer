'use client';

import { useConfigStore, type RAGConfig, type RAGMode } from '@/lib/stores/configStore';

const RAG_MODES: { value: RAGMode; label: string }[] = [
  { value: 'adaptive', label: 'Adaptive' },
  { value: 'self_rag', label: 'Self-RAG' },
  { value: 'crag', label: 'CRAG' },
  { value: 'graph_rag', label: 'Graph RAG' },
  { value: 'multi_hop', label: 'Multi-Hop' },
];

export function RAGConfigSection() {
  const { rag, updateRAG } = useConfigStore();

  return (
    <div className="space-y-4 text-sm">
      <div>
        <label className="block text-white/70 mb-1">模式</label>
        <select
          value={rag.mode}
          onChange={(e) => updateRAG({ mode: e.target.value as RAGMode })}
          className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
        >
          {RAG_MODES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={rag.hybridSearch}
            onChange={(e) => updateRAG({ hybridSearch: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">混合检索</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={rag.queryExpansion}
            onChange={(e) => updateRAG({ queryExpansion: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">查询扩展</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={rag.contextCompression}
            onChange={(e) => updateRAG({ contextCompression: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">上下文压缩</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={rag.trendQualityFilter}
            onChange={(e) => updateRAG({ trendQualityFilter: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">趋势质量过滤</span>
        </label>
      </div>
      <div>
        <label className="block text-white/70 mb-1">TopK: {rag.topK}</label>
        <input
          type="range"
          min={1}
          max={20}
          value={rag.topK}
          onChange={(e) => updateRAG({ topK: Number(e.target.value) })}
          className="w-full accent-purple-500"
        />
      </div>
    </div>
  );
}
