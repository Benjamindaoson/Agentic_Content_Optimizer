'use client';

import { useConfigStore } from '@/lib/stores/configStore';

const PROVIDERS = [
  { value: 'claude', label: 'Claude' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'vllm', label: 'vLLM' },
];

const MODELS: Record<string, string[]> = {
  claude: ['claude-sonnet-4-5-20250929', 'claude-haiku-4-5-20251001', 'claude-opus-4-6'],
  openai: ['gpt-4.5-turbo', 'gpt-4o', 'o1-mini'],
  deepseek: ['deepseek-v3', 'deepseek-coder'],
  gemini: ['gemini-2.0-flash', 'gemini-2.0-pro'],
  vllm: ['meta-llama/Llama-3.1-8B-Instruct'],
};

export function LLMConfigSection() {
  const { llm, updateLLM } = useConfigStore();
  const models = MODELS[llm.provider] || [llm.model];

  return (
    <div className="space-y-4 text-sm">
      <div>
        <label className="block text-white/70 mb-1">提供商</label>
        <select
          value={llm.provider}
          onChange={(e) => {
            const p = e.target.value as 'claude' | 'openai' | 'deepseek' | 'gemini' | 'vllm';
            updateLLM({ provider: p, model: MODELS[p]?.[0] || llm.model });
          }}
          className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
        >
          {PROVIDERS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-white/70 mb-1">模型</label>
        <select
          value={llm.model}
          onChange={(e) => updateLLM({ model: e.target.value })}
          className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
        >
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-white/70 mb-1">Temperature: {llm.temperature.toFixed(1)}</label>
        <input
          type="range"
          min={0}
          max={1.5}
          step={0.1}
          value={llm.temperature}
          onChange={(e) => updateLLM({ temperature: Number(e.target.value) })}
          className="w-full accent-purple-500"
        />
      </div>
      <div>
        <label className="block text-white/70 mb-1">Max Tokens: {llm.maxTokens}</label>
        <input
          type="number"
          min={256}
          max={8192}
          value={llm.maxTokens}
          onChange={(e) => updateLLM({ maxTokens: Number(e.target.value) })}
          className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
        />
      </div>
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={llm.enableModelRouter}
            onChange={(e) => updateLLM({ enableModelRouter: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">智能路由</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={llm.enableGrayRelease}
            onChange={(e) => updateLLM({ enableGrayRelease: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">灰度发布</span>
        </label>
      </div>
    </div>
  );
}
