'use client';

import { useConfigStore } from '@/lib/stores/configStore';

const PLATFORMS = [
  { value: 'xiaohongshu', label: '小红书' },
  { value: 'douyin', label: '抖音' },
  { value: 'tiktok', label: 'TikTok' },
  { value: 'kuaishou', label: '快手' },
];

const CONTENT_TYPES = [
  { value: 'post', label: '图文' },
  { value: 'video_script', label: '视频脚本' },
  { value: 'story', label: '故事' },
];

export function GenerationConfigSection() {
  const { generation, updateGeneration } = useConfigStore();

  return (
    <div className="space-y-4 text-sm">
      <div>
        <label className="block text-white/70 mb-1">平台</label>
        <select
          value={generation.platform}
          onChange={(e) => updateGeneration({ platform: e.target.value as typeof generation.platform })}
          className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
        >
          {PLATFORMS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-white/70 mb-1">内容类型</label>
        <select
          value={generation.contentType}
          onChange={(e) => updateGeneration({ contentType: e.target.value as typeof generation.contentType })}
          className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white"
        >
          {CONTENT_TYPES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={generation.enableGeoKeywords}
            onChange={(e) => updateGeneration({ enableGeoKeywords: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">GEO 关键词</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={generation.enableHookStrategy}
            onChange={(e) => updateGeneration({ enableHookStrategy: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">Hook 策略</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={generation.enableCTAStrategy}
            onChange={(e) => updateGeneration({ enableCTAStrategy: e.target.checked })}
            className="rounded bg-white/10"
          />
          <span className="text-white/80">CTA 策略</span>
        </label>
      </div>
    </div>
  );
}
