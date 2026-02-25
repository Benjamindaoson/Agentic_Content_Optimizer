'use client';

import { useMemo, useState } from 'react';
import { apiClient } from '@/lib/api';

type Props = {
  traceId?: string | null;
};

export function OutcomeUpsertForm({ traceId }: Props) {
  const [timeBucket, setTimeBucket] = useState<'1h' | '6h' | '24h' | '7d'>('24h');
  const [impressions, setImpressions] = useState(0);
  const [clicks, setClicks] = useState(0);
  const [readTimeAvg, setReadTimeAvg] = useState(0);
  const [completionRate, setCompletionRate] = useState(0);
  const [likes, setLikes] = useState(0);
  const [comments, setComments] = useState(0);
  const [saves, setSaves] = useState(0);
  const [shares, setShares] = useState(0);
  const [follows, setFollows] = useState(0);
  const [dms, setDms] = useState(0);
  const [purchases, setPurchases] = useState(0);

  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<string>('');

  const disabled = useMemo(() => !traceId || submitting, [traceId, submitting]);

  const submit = async () => {
    if (!traceId) {
      setStatus('请先生成内容，拿到 trace_id 后再回填。');
      return;
    }
    setSubmitting(true);
    setStatus('提交中...');
    try {
      const payload = {
        trace_id: traceId,
        time_bucket: timeBucket,
        impressions,
        clicks,
        read_time_avg: readTimeAvg,
        completion_rate: completionRate,
        likes,
        comments,
        saves,
        shares,
        follows,
        dms,
        purchases,
      };
      const resp = await apiClient.post('/v1/outcomes/upsert', payload);
      const data = resp.data?.data ?? resp.data;
      setStatus(`回填成功：engagement_score=${data?.engagement_score ?? 'n/a'}`);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '回填失败';
      setStatus(`回填失败：${detail}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-xl border border-white/10 bg-black/40 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm text-white/80">Outcome 回填（闭环观测）</div>
          <div className="text-xs text-white/50 mt-1">
            trace_id: <span className="font-mono">{traceId || '（暂无）'}</span>
          </div>
        </div>
        <button
          type="button"
          disabled={disabled}
          onClick={submit}
          className={`px-3 py-2 rounded-md text-sm ${
            disabled ? 'bg-white/10 text-white/40' : 'bg-emerald-600 hover:bg-emerald-500 text-white'
          }`}
        >
          提交回填
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <label className="space-y-1">
          <div className="text-white/60 text-xs">时间窗口</div>
          <select
            value={timeBucket}
            onChange={(e) => setTimeBucket(e.target.value as any)}
            className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
          >
            <option value="1h">1h</option>
            <option value="6h">6h</option>
            <option value="24h">24h</option>
            <option value="7d">7d</option>
          </select>
        </label>

        <Field label="曝光 impressions" value={impressions} setValue={setImpressions} />
        <Field label="点击 clicks" value={clicks} setValue={setClicks} />
        <Field label="平均阅读(s)" value={readTimeAvg} setValue={setReadTimeAvg} />
        <Field label="完读率(0-1)" value={completionRate} setValue={setCompletionRate} step={0.01} />

        <Field label="点赞 likes" value={likes} setValue={setLikes} />
        <Field label="评论 comments" value={comments} setValue={setComments} />
        <Field label="收藏 saves" value={saves} setValue={setSaves} />
        <Field label="分享 shares" value={shares} setValue={setShares} />

        <Field label="关注 follows" value={follows} setValue={setFollows} />
        <Field label="私信 dms" value={dms} setValue={setDms} />
        <Field label="购买 purchases" value={purchases} setValue={setPurchases} />
      </div>

      {status ? <div className="text-xs text-white/60">{status}</div> : null}
    </div>
  );
}

function Field(props: {
  label: string;
  value: number;
  setValue: (v: number) => void;
  step?: number;
}) {
  const step = props.step ?? 1;
  return (
    <label className="space-y-1">
      <div className="text-white/60 text-xs">{props.label}</div>
      <input
        type="number"
        step={step}
        value={Number.isFinite(props.value) ? props.value : 0}
        onChange={(e) => props.setValue(Number(e.target.value))}
        className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
      />
    </label>
  );
}

