'use client';

import { useEffect, useMemo, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  Edge,
  MarkerType,
  MiniMap,
  Node,
  NodeProps,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useConfigStore } from '@/lib/stores/configStore';

type NodeStatus = 'idle' | 'running' | 'done' | 'error';

interface WorkflowStatusEvent {
  type: 'workflow_status';
  node: string;
  status: NodeStatus;
  timestamp?: string;
  duration_ms?: number;
  summary?: string;
  token_usage?: Record<string, unknown>;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  prompt?: string;
}

interface WorkflowNodeData {
  label: string;
  status: NodeStatus;
  durationMs?: number;
  summary?: string;
}

const STATUS_COLOR: Record<NodeStatus, string> = {
  idle: 'border-white/15',
  running: 'border-cyan-400',
  done: 'border-emerald-400',
  error: 'border-rose-400',
};

const STATUS_TEXT: Record<NodeStatus, string> = {
  idle: '空闲',
  running: '运行中',
  done: '完成',
  error: '异常',
};

function WorkflowNode({ data }: NodeProps<WorkflowNodeData>) {
  const runningClass = data.status === 'running' ? 'workflow-node-running' : '';
  return (
    <div
      className={`min-w-[180px] rounded-xl border bg-[#0f1117] px-3 py-2 shadow-lg ${STATUS_COLOR[data.status]} ${runningClass}`}
    >
      <div className="text-sm font-medium text-white">{data.label}</div>
      <div className="mt-1 text-xs text-white/60">状态：{STATUS_TEXT[data.status]}</div>
      <div className="text-xs text-white/60">耗时：{data.durationMs ?? '-'} ms</div>
      {data.summary ? <div className="mt-1 text-xs text-cyan-200">{data.summary}</div> : null}
    </div>
  );
}

const nodeTypes = {
  workflowNode: WorkflowNode,
};

const BASE_NODES: Record<string, Omit<Node<WorkflowNodeData>, 'data'>> = {
  trend_analysis: {
    id: 'trend_analysis',
    type: 'workflowNode',
    position: { x: 20, y: 120 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  },
  director_sample: {
    id: 'director_sample',
    type: 'workflowNode',
    position: { x: 250, y: 120 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  },
  content_generation: {
    id: 'content_generation',
    type: 'workflowNode',
    position: { x: 500, y: 120 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  },
  content_evaluation: {
    id: 'content_evaluation',
    type: 'workflowNode',
    position: { x: 760, y: 120 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  },
  refinement: {
    id: 'refinement',
    type: 'workflowNode',
    position: { x: 635, y: 260 },
    sourcePosition: Position.Left,
    targetPosition: Position.Top,
  },
  human_review: {
    id: 'human_review',
    type: 'workflowNode',
    position: { x: 1020, y: 120 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  },
  output: {
    id: 'output',
    type: 'workflowNode',
    position: { x: 1230, y: 120 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  },
};

const LABEL_MAP: Record<string, string> = {
  trend_analysis: 'Trend Agent',
  director_sample: 'Director (Thompson Sampling)',
  content_generation: 'Writer Agent (RAG)',
  content_evaluation: 'Critic Agent',
  refinement: 'Refinement',
  human_review: 'Human Review',
  output: 'Output',
};

const BASE_EDGES: Edge[] = [
  {
    id: 'e1',
    source: 'trend_analysis',
    target: 'director_sample',
    label: 'trend context',
    markerEnd: { type: MarkerType.ArrowClosed },
  },
  {
    id: 'e2',
    source: 'director_sample',
    target: 'content_generation',
    label: 'strategy selection',
    markerEnd: { type: MarkerType.ArrowClosed },
  },
  {
    id: 'e3',
    source: 'content_generation',
    target: 'content_evaluation',
    label: 'draft',
    markerEnd: { type: MarkerType.ArrowClosed },
  },
  {
    id: 'e4',
    source: 'content_evaluation',
    target: 'refinement',
    label: 'feedback',
    markerEnd: { type: MarkerType.ArrowClosed },
  },
  {
    id: 'e5',
    source: 'refinement',
    target: 'content_generation',
    label: 'retry',
    markerEnd: { type: MarkerType.ArrowClosed },
  },
  {
    id: 'e6',
    source: 'content_evaluation',
    target: 'human_review',
    label: 'review',
    markerEnd: { type: MarkerType.ArrowClosed },
  },
  {
    id: 'e7',
    source: 'human_review',
    target: 'output',
    label: 'approved',
    markerEnd: { type: MarkerType.ArrowClosed },
  },
];

const WS_NODE_ALIAS: Record<string, string> = {
  trend_analysis: 'trend_analysis',
  director_sample: 'director_sample',
  content_generation: 'content_generation',
  content_evaluation: 'content_evaluation',
  refinement: 'refinement',
  human_review: 'human_review',
  output: 'output',
};

interface NodeDetail {
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  prompt?: string;
  token_usage?: Record<string, unknown>;
  summary?: string;
}

export function WorkflowVisualizer() {
  const { agent } = useConfigStore();
  const [nodeState, setNodeState] = useState<Record<string, WorkflowNodeData>>({
    trend_analysis: { label: LABEL_MAP.trend_analysis, status: 'idle' },
    director_sample: { label: LABEL_MAP.director_sample, status: 'idle' },
    content_generation: { label: LABEL_MAP.content_generation, status: 'idle' },
    content_evaluation: { label: LABEL_MAP.content_evaluation, status: 'idle' },
    refinement: { label: LABEL_MAP.refinement, status: 'idle' },
    human_review: { label: LABEL_MAP.human_review, status: 'idle' },
    output: { label: LABEL_MAP.output, status: 'idle' },
  });
  const [details, setDetails] = useState<Record<string, NodeDetail>>({});
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<'connected' | 'disconnected'>('disconnected');

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    const wsUrl = `${base.replace(/^http/, 'ws')}/ws${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      setWsStatus('connected');
      socket.send(JSON.stringify({ action: 'subscribe', channel: 'workflow' }));
    };

    socket.onclose = () => setWsStatus('disconnected');
    socket.onerror = () => setWsStatus('disconnected');

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WorkflowStatusEvent;
        if (data.type !== 'workflow_status' || !data.node) {
          return;
        }

        const nodeId = WS_NODE_ALIAS[data.node];
        if (!nodeId) {
          return;
        }

        setNodeState((prev) => ({
          ...prev,
          [nodeId]: {
            label: LABEL_MAP[nodeId],
            status: data.status || 'idle',
            durationMs: data.duration_ms,
            summary: data.summary,
          },
        }));

        setDetails((prev) => ({
          ...prev,
          [nodeId]: {
            input: data.input,
            output: data.output,
            prompt: data.prompt,
            token_usage: data.token_usage,
            summary: data.summary,
          },
        }));

        if (nodeId === 'human_review' && data.status === 'done') {
          setNodeState((prev) => ({
            ...prev,
            output: {
              ...prev.output,
              label: LABEL_MAP.output,
              status: 'done',
            },
          }));
        }
      } catch {
        // Ignore malformed messages.
      }
    };

    return () => socket.close();
  }, []);

  const activeNodeIds = useMemo(() => {
    if (agent.mode === 'writer_only') {
      return ['content_generation', 'output'];
    }
    if (agent.mode === 'writer_critic') {
      return ['content_generation', 'content_evaluation', 'refinement', 'output'];
    }
    return [
      'trend_analysis',
      'director_sample',
      'content_generation',
      'content_evaluation',
      'refinement',
      'human_review',
      'output',
    ];
  }, [agent.mode]);

  const nodes = useMemo<Node<WorkflowNodeData>[]>(() => {
    return activeNodeIds.map((id) => ({
      ...BASE_NODES[id],
      data: nodeState[id],
    }));
  }, [activeNodeIds, nodeState]);

  const edges = useMemo<Edge[]>(() => {
    if (agent.mode === 'writer_only') {
      return [
        {
          id: 'w1',
          source: 'content_generation',
          target: 'output',
          label: 'final content',
          markerEnd: { type: MarkerType.ArrowClosed },
        },
      ];
    }

    if (agent.mode === 'writer_critic') {
      return [
        {
          id: 'wc1',
          source: 'content_generation',
          target: 'content_evaluation',
          label: 'draft',
          markerEnd: { type: MarkerType.ArrowClosed },
        },
        {
          id: 'wc2',
          source: 'content_evaluation',
          target: 'refinement',
          label: 'feedback',
          markerEnd: { type: MarkerType.ArrowClosed },
        },
        {
          id: 'wc3',
          source: 'refinement',
          target: 'content_generation',
          label: 'retry',
          markerEnd: { type: MarkerType.ArrowClosed },
        },
        {
          id: 'wc4',
          source: 'content_evaluation',
          target: 'output',
          label: 'approved',
          markerEnd: { type: MarkerType.ArrowClosed },
        },
      ];
    }

    return BASE_EDGES;
  }, [agent.mode]);

  const selectedDetail = selectedNode ? details[selectedNode] : null;

  return (
    <div className="w-full rounded-xl border border-white/10 bg-black/40 p-3">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm text-white/80">Workflow 实时可视化</div>
        <div className="text-xs text-white/60">
          WS: {wsStatus === 'connected' ? '已连接' : '未连接'}
        </div>
      </div>

      <div className="h-[460px] rounded-lg overflow-hidden border border-white/10">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          onNodeClick={(_, node) => setSelectedNode(node.id)}
          proOptions={{ hideAttribution: true }}
        >
          <MiniMap />
          <Controls />
          <Background />
        </ReactFlow>
      </div>

      <div className="mt-3 rounded-lg border border-white/10 bg-white/[0.03] p-3">
        <div className="text-sm text-white/80 mb-2">节点详情</div>
        {!selectedNode ? (
          <div className="text-xs text-white/60">点击任一节点查看输入 / 输出 / Prompt / Token 用量</div>
        ) : (
          <div className="space-y-2 text-xs text-white/75">
            <div>节点：{LABEL_MAP[selectedNode] || selectedNode}</div>
            <div>摘要：{selectedDetail?.summary || '-'}</div>
            <div>
              输入：
              <pre className="mt-1 whitespace-pre-wrap rounded bg-black/40 p-2">
                {JSON.stringify(selectedDetail?.input ?? {}, null, 2)}
              </pre>
            </div>
            <div>
              输出：
              <pre className="mt-1 whitespace-pre-wrap rounded bg-black/40 p-2">
                {JSON.stringify(selectedDetail?.output ?? {}, null, 2)}
              </pre>
            </div>
            <div>
              Prompt：
              <pre className="mt-1 whitespace-pre-wrap rounded bg-black/40 p-2">
                {selectedDetail?.prompt || '-'}
              </pre>
            </div>
            <div>
              Token：
              <pre className="mt-1 whitespace-pre-wrap rounded bg-black/40 p-2">
                {JSON.stringify(selectedDetail?.token_usage ?? {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
