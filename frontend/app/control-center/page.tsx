'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { ConfigPanel } from '@/components/config/ConfigPanel';
import { WorkflowVisualizer } from '@/components/workflow/WorkflowVisualizer';
import { EvolutionDashboard } from '@/components/dashboard/EvolutionDashboard';
import { ContentPreview } from '@/components/content/ContentPreview';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { OutcomeUpsertForm } from '@/components/outcomes/OutcomeUpsertForm';

function extractContent(raw: any) {
  if (!raw) return null;
  const data = raw?.data ?? raw;
  return {
    title: data?.title ?? data?.final_content?.title ?? '',
    hook: data?.final_content?.hook ?? '',
    body: data?.final_content?.body ?? data?.content ?? '',
    cta: data?.final_content?.cta ?? '',
    score: data?.final_score ?? data?.evaluation?.overall_score ?? 0,
    policy_id: data?.policy_id ?? '',
    action: data?.selected_action ?? {},
    cover_candidates: data?.cover_candidates ?? [],
  };
}

export default function ControlCenterPage() {
  const [generated, setGenerated] = useState<any>(null);
  const traceId = generated?.trace_id ?? generated?.data?.trace_id ?? null;
  const content = extractContent(generated);
  const searchParams = useSearchParams();

  const [showRawJson, setShowRawJson] = useState(false);

  const topicFromUrl = searchParams?.get('topic') ?? '';

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="border-b border-white/[0.04] bg-black/30">
        <div className="max-w-7xl mx-auto px-6 py-3">
          <div className="text-xs text-white/40">
            配置 → 生成 → 预览 → 发布
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        <Tabs defaultValue="config">
          <TabsList>
            <TabsTrigger value="config">配置与生成</TabsTrigger>
            <TabsTrigger value="workflow">工作流可视化</TabsTrigger>
            <TabsTrigger value="dashboard">效果看板</TabsTrigger>
          </TabsList>

          <TabsContent value="config">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ConfigPanel
                onGenerated={(r) => setGenerated(r)}
                defaultTopic={topicFromUrl}
              />

              <div className="space-y-4">
                {content ? (
                  <div className="rounded-xl border border-white/10 bg-black/40 p-6">
                    <div className="flex items-center justify-between mb-4">
                      <span className="text-sm text-white/80 font-medium">小红书笔记预览</span>
                      <button
                        onClick={() => setShowRawJson(!showRawJson)}
                        className="text-xs text-white/30 hover:text-white/60 transition-colors"
                      >
                        {showRawJson ? '切换预览' : '查看 JSON'}
                      </button>
                    </div>

                    {showRawJson ? (
                      <pre className="text-xs text-white/50 whitespace-pre-wrap break-words overflow-x-auto max-h-[600px] overflow-y-auto">
                        {JSON.stringify(generated, null, 2)}
                      </pre>
                    ) : (
                      <ContentPreview content={content} traceId={traceId} />
                    )}
                  </div>
                ) : (
                  <div className="rounded-xl border border-white/10 bg-black/40 p-16 text-center">
                    <div className="text-3xl mb-3 opacity-20">✍️</div>
                    <div className="text-sm text-white/30">在左侧配置参数并点击生成</div>
                  </div>
                )}

                <OutcomeUpsertForm traceId={traceId} />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="workflow">
            <WorkflowVisualizer />
          </TabsContent>

          <TabsContent value="dashboard">
            <EvolutionDashboard />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
