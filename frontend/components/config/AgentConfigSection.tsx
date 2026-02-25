'use client';

import { useConfigStore, type AgentMode } from '@/lib/stores/configStore';

const AGENT_MODES: { value: AgentMode; label: string }[] = [
  { value: 'full_pipeline', label: '完整流水线' },
  { value: 'writer_only', label: '仅 Writer' },
  { value: 'writer_critic', label: 'Writer + Critic' },
];

export function AgentConfigSection() {
  const { agent, updateAgent } = useConfigStore();

  return (
    <div className="space-y-4 text-sm">
      <div>
        <label className="block text-white/70 mb-1">模式</label>
        <select
          value={agent.mode}
          onChange={(e) => updateAgent({ mode: e.target.value as AgentMode })}
          className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
        >
          {AGENT_MODES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-white/70 mb-1">最大优化轮次: {agent.maxRefinementLoops}</label>
        <input
          type="range"
          min={1}
          max={5}
          value={agent.maxRefinementLoops}
          onChange={(e) => updateAgent({ maxRefinementLoops: Number(e.target.value) })}
          className="w-full accent-purple-500"
        />
      </div>

      <div>
        <label className="block text-white/70 mb-1">质量阈值: {agent.qualityThreshold}</label>
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={agent.qualityThreshold}
          onChange={(e) => updateAgent({ qualityThreshold: Number(e.target.value) })}
          className="w-full accent-purple-500"
        />
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={agent.humanReviewEnabled}
          onChange={(e) => updateAgent({ humanReviewEnabled: e.target.checked })}
          className="rounded bg-white/10"
        />
        <span className="text-white/80">人工审核</span>
      </label>
    </div>
  );
}
