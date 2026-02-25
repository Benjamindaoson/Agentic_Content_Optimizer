'use client';

import { useMemo, useState } from 'react';
import { apiClient } from '@/lib/api';
import { useConfigStore } from '@/lib/stores/configStore';
import { RAGConfigSection } from '@/components/config/RAGConfigSection';
import { RLConfigSection } from '@/components/config/RLConfigSection';
import { AgentConfigSection } from '@/components/config/AgentConfigSection';
import { LLMConfigSection } from '@/components/config/LLMConfigSection';
import { TrainingConfigSection } from '@/components/config/TrainingConfigSection';
import { GenerationConfigSection } from '@/components/config/GenerationConfigSection';

interface ConfigPanelProps {
  className?: string;
  onGenerated?: (result: unknown) => void;
  defaultTopic?: string;
}

interface SectionProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

function Section({ title, defaultOpen = false, children }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/[0.03]"
      >
        <span className="text-sm font-medium text-white/90">{title}</span>
        <span className="text-white/60">{open ? '▼' : '▶'}</span>
      </button>
      {open ? <div className="px-4 pb-4">{children}</div> : null}
    </div>
  );
}

function PanelContent({ onGenerated, defaultTopic }: Pick<ConfigPanelProps, 'onGenerated' | 'defaultTopic'>) {
  const {
    expertMode,
    setExpertMode,
    generation,
    updateGeneration,
    updateRL,
    applyPreset,
    resetToDefaults,
    toAPIRequest,
    rag,
    rl,
    agent,
    llm,
    training,
  } = useConfigStore();

  const [topic, setTopic] = useState(defaultTopic || '');
  const [statusText, setStatusText] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [lastEffective, setLastEffective] = useState<{ applied: string[]; recorded_only: string[] } | null>(null);

  const previewJSON = useMemo(
    () =>
      JSON.stringify(
        {
          expertMode,
          rag,
          rl,
          agent,
          llm,
          training,
          generation,
        },
        null,
        2
      ),
    [expertMode, rag, rl, agent, llm, training, generation]
  );

  const runGenerate = async () => {
    if (!topic.trim()) {
      setStatusText('请输入话题后再生成');
      return;
    }

    setGenerating(true);
    setStatusText('正在生成...');
    try {
      const payload = {
        ...toAPIRequest(),
        topic: topic.trim(),
      };
      const response = await apiClient.post('/v1/workflow/generate', payload);
      const data = response.data?.data ?? response.data;
      const effective = data?.metadata?.effective;
      if (effective?.applied && effective?.recorded_only) {
        setLastEffective(effective);
      }
      onGenerated?.(data);
      setStatusText('生成完成');
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || '生成失败';
      setStatusText(`生成失败：${detail}`);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-2 rounded-lg bg-white/[0.03] p-1">
        <button
          type="button"
          onClick={() => {
            setExpertMode(false);
            applyPreset('quick');
          }}
          className={`rounded-md px-3 py-2 text-sm ${
            !expertMode ? 'bg-purple-600 text-white' : 'text-white/70 hover:bg-white/5'
          }`}
        >
          快速模式
        </button>
        <button
          type="button"
          onClick={() => setExpertMode(true)}
          className={`rounded-md px-3 py-2 text-sm ${
            expertMode ? 'bg-purple-600 text-white' : 'text-white/70 hover:bg-white/5'
          }`}
        >
          专家模式
        </button>
      </div>

      <div className="space-y-4 rounded-lg border border-white/10 p-4">
        <div>
          <label className="block text-white/70 mb-1 text-sm">平台</label>
          <select
            value={generation.platform}
            onChange={(e) => updateGeneration({ platform: e.target.value as typeof generation.platform })}
            className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white text-sm"
          >
            <option value="xiaohongshu">小红书</option>
            <option value="douyin">抖音</option>
            <option value="tiktok">TikTok</option>
            <option value="kuaishou">快手</option>
          </select>
        </div>

        <div>
          <label className="block text-white/70 mb-1 text-sm">话题</label>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="输入要生成的话题"
            className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white text-sm"
          />
        </div>

        <div className="space-y-2">
          <div className="text-white/70 text-sm">风格预设</div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                applyPreset('quick');
                updateRL({ rewardPreset: 'balanced' });
              }}
              className="px-3 py-1.5 rounded border border-white/20 text-sm text-white/80 hover:bg-white/10"
            >
              均衡
            </button>
            <button
              type="button"
              onClick={() => {
                applyPreset('quick');
                updateRL({
                  rewardPreset: 'engagement',
                  thompsonSamplingEnabled: true,
                  grpoEnabled: false,
                });
              }}
              className="px-3 py-1.5 rounded border border-white/20 text-sm text-white/80 hover:bg-white/10"
            >
              互动优先
            </button>
            <button
              type="button"
              onClick={() => {
                applyPreset('quality');
                updateRL({ rewardPreset: 'quality' });
              }}
              className="px-3 py-1.5 rounded border border-white/20 text-sm text-white/80 hover:bg-white/10"
            >
              质量优先
            </button>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={runGenerate}
            disabled={generating}
            className="flex-1 rounded bg-purple-600 hover:bg-purple-500 disabled:opacity-60 px-4 py-2 text-sm font-medium"
          >
            {generating ? '生成中...' : '🚀 一键生成'}
          </button>
          <button
            type="button"
            onClick={resetToDefaults}
            className="rounded border border-white/20 px-3 py-2 text-sm text-white/80 hover:bg-white/5"
          >
            重置
          </button>
        </div>
        {statusText ? <div className="text-xs text-white/60">{statusText}</div> : null}
      </div>

      {expertMode ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-xs text-white/70">
            <div className="font-medium text-white/80 mb-1">配置生效范围</div>
            <div>已生效：agent_mode / max_refinement_loops / quality_threshold + 基础输入（topic/platform等）</div>
            <div>其余开关当前仅“记录到 metadata + 前端展示”，后端 pipeline 尚未完全接入。</div>
            {lastEffective ? (
              <div className="mt-2 text-white/60">
                最近一次返回：applied={lastEffective.applied.length} 项，recorded_only={lastEffective.recorded_only.length} 项
              </div>
            ) : null}
          </div>
          <Section title="RAG 检索配置" defaultOpen>
            <RAGConfigSection />
          </Section>
          <Section title="策略优化 (RL)">
            <RLConfigSection />
          </Section>
          <Section title="Agent 编排">
            <AgentConfigSection />
          </Section>
          <Section title="LLM 设置">
            <LLMConfigSection />
          </Section>
          <Section title="模型训练">
            <TrainingConfigSection />
          </Section>
          <Section title="内容生成">
            <GenerationConfigSection />
          </Section>

          <div className="rounded-lg border border-white/10 bg-black/30 p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white/80">当前配置 JSON</span>
              <button
                type="button"
                onClick={() => navigator.clipboard.writeText(previewJSON)}
                className="text-xs px-2 py-1 rounded border border-white/20 text-white/70 hover:bg-white/5"
              >
                复制
              </button>
            </div>
            <pre className="text-xs text-white/70 overflow-x-auto whitespace-pre-wrap">{previewJSON}</pre>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function ConfigPanel({ className, onGenerated, defaultTopic }: ConfigPanelProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      <div className={`hidden md:block rounded-xl border border-white/10 bg-black/40 p-4 ${className || ''}`}>
        <PanelContent onGenerated={onGenerated} defaultTopic={defaultTopic} />
      </div>

      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        className="md:hidden fixed bottom-4 right-4 z-40 rounded-full bg-purple-600 px-4 py-2 text-sm font-medium shadow-lg"
      >
        打开配置
      </button>

      <div
        className={`md:hidden fixed inset-0 z-50 transition ${
          mobileOpen ? 'pointer-events-auto' : 'pointer-events-none'
        }`}
      >
        <div
          className={`absolute inset-0 bg-black/60 transition-opacity ${
            mobileOpen ? 'opacity-100' : 'opacity-0'
          }`}
          onClick={() => setMobileOpen(false)}
        />
        <div
          className={`absolute left-0 right-0 bottom-0 max-h-[88vh] overflow-y-auto rounded-t-2xl border-t border-white/10 bg-[#0c0c12] p-4 transition-transform ${
            mobileOpen ? 'translate-y-0' : 'translate-y-full'
          }`}
        >
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-white font-medium">配置面板</h3>
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="text-sm text-white/70 px-2 py-1 rounded hover:bg-white/5"
            >
              关闭
            </button>
          </div>
          <PanelContent onGenerated={onGenerated} defaultTopic={defaultTopic} />
        </div>
      </div>
    </>
  );
}
