'use client';

import { useConfigStore } from '@/lib/stores/configStore';

export function TrainingConfigSection() {
  const { training, updateTraining } = useConfigStore();

  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={training.sftEnabled}
            onChange={(e) => updateTraining({ sftEnabled: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">SFT 微调</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={training.dpoEnabled}
            onChange={(e) => updateTraining({ dpoEnabled: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">DPO 对齐</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={training.autoTrainOnFeedback}
            onChange={(e) => updateTraining({ autoTrainOnFeedback: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">自动训练</span>
        </label>
      </div>
      <div>
        <label className="block text-white/70 mb-1">反馈阈值: {training.feedbackThreshold}</label>
        <input
          type="number"
          min={10}
          max={500}
          value={training.feedbackThreshold}
          onChange={(e) => updateTraining({ feedbackThreshold: Number(e.target.value) })}
          className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
        />
      </div>
    </div>
  );
}
