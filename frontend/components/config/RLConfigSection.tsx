'use client';

import { useConfigStore, type RewardPreset } from '@/lib/stores/configStore';

const PRESETS: { value: RewardPreset; label: string }[] = [
  { value: 'balanced', label: '均衡' },
  { value: 'engagement', label: '互动优先' },
  { value: 'quality', label: '质量优先' },
  { value: 'custom', label: '自定义' },
];

function normalizeWeights(rw: number, q: number, sh: number) {
  const total = rw + q + sh;
  if (total === 0) return { realWorld: 60, quality: 30, systemHealth: 10 };
  return {
    realWorld: Math.round((rw / total) * 100),
    quality: Math.round((q / total) * 100),
    systemHealth: Math.round((sh / total) * 100),
  };
}

export function RLConfigSection() {
  const { rl, updateRL } = useConfigStore();
  const w = rl.customRewardWeights;

  const handleWeightChange = (key: 'realWorld' | 'quality' | 'systemHealth', value: number) => {
    const next = { ...w, [key]: value };
    const total = next.realWorld + next.quality + next.systemHealth;
    if (total !== 100) {
      const normalized = normalizeWeights(next.realWorld, next.quality, next.systemHealth);
      updateRL({ customRewardWeights: normalized });
    } else {
      updateRL({ customRewardWeights: next });
    }
  };

  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={rl.thompsonSamplingEnabled}
            onChange={(e) => updateRL({ thompsonSamplingEnabled: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">Thompson Sampling</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={rl.grpoEnabled}
            onChange={(e) => updateRL({ grpoEnabled: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">GRPO</span>
        </label>
      </div>
      <div>
        <label className="block text-white/70 mb-1">奖励预设</label>
        <select
          value={rl.rewardPreset}
          onChange={(e) => updateRL({ rewardPreset: e.target.value as RewardPreset })}
          className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
        >
          {PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-2">
        <label className="block text-white/70">奖励权重 (总和=100)</label>
        <div className="grid grid-cols-3 gap-2">
          <div>
            <span className="text-xs text-white/60">真实世界</span>
            <input
              type="range"
              min={0}
              max={100}
              value={w.realWorld}
              onChange={(e) => handleWeightChange('realWorld', Number(e.target.value))}
              className="w-full accent-purple-500"
            />
            <span className="text-xs text-white/80">{w.realWorld}</span>
          </div>
          <div>
            <span className="text-xs text-white/60">质量</span>
            <input
              type="range"
              min={0}
              max={100}
              value={w.quality}
              onChange={(e) => handleWeightChange('quality', Number(e.target.value))}
              className="w-full accent-purple-500"
            />
            <span className="text-xs text-white/80">{w.quality}</span>
          </div>
          <div>
            <span className="text-xs text-white/60">系统健康</span>
            <input
              type="range"
              min={0}
              max={100}
              value={w.systemHealth}
              onChange={(e) => handleWeightChange('systemHealth', Number(e.target.value))}
              className="w-full accent-purple-500"
            />
            <span className="text-xs text-white/80">{w.systemHealth}</span>
          </div>
        </div>
      </div>
      <div>
        <label className="block text-white/70 mb-1">探索率: {rl.explorationRate.toFixed(2)}</label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={rl.explorationRate}
          onChange={(e) => updateRL({ explorationRate: Number(e.target.value) })}
          className="w-full accent-purple-500"
        />
      </div>
    </div>
  );
}
