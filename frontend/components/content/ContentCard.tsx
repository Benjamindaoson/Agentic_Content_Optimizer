'use client'

import { useState } from 'react'
import { Film, Clock, Camera, Lightbulb, Palette, Type } from 'lucide-react'

interface Shot {
  type: string
  subject: string
  duration_s: number
  camera_movement: string
  description?: string
}

interface Blueprint {
  scene: string
  scene_tags: string[]
  shot_list: Shot[]
  props: string[]
  optional_props: string[]
  lighting: string
  color_tone: string
  filter_preset?: string
  subtitle_style: string
  subtitle_positions: string[]
  pacing: string
  bgm_style?: string
  micro_innovation: string
  geo_text_overlay?: string[]
  estimated_production_time_min: number
  difficulty_level: string
}

interface TextStructure {
  hook: string
  body: string
  cta: string
  full_text: string
}

interface GeneratedContent {
  text_structure: TextStructure
  blueprint: Blueprint
  geo_keywords: string[]
  geo_coverage: number
  action: {
    hook: string
    body: string
    cta: string
  }
}

interface ContentCardProps {
  content: GeneratedContent
  index: number
}

export function ContentCard({ content, index }: ContentCardProps) {
  const [activeTab, setActiveTab] = useState<'text' | 'blueprint'>('text')

  const { text_structure, blueprint, geo_keywords, geo_coverage, action } = content

  // 镜头类型图标映射
  const shotTypeIcons: Record<string, string> = {
    'close-up': '🔍',
    'mid': '👤',
    'wide': '🌄',
    'pov': '👁️',
    'over-shoulder': '👥'
  }

  // 难度等级颜色
  const difficultyColors: Record<string, string> = {
    'easy': 'text-green-500',
    'medium': 'text-yellow-500',
    'hard': 'text-red-500'
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">
            内容 #{index + 1}
          </span>
          <span className="text-xs px-2 py-1 rounded bg-primary/10 text-primary">
            {action.hook} + {action.body} + {action.cta}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            GEO覆盖率: {(geo_coverage * 100).toFixed(0)}%
          </span>
          <div className="h-2 w-20 rounded-full bg-secondary">
            <div
              className="h-2 rounded-full bg-primary"
              style={{ width: `${geo_coverage * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4 border-b border-border">
        <button
          onClick={() => setActiveTab('text')}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'text'
              ? 'border-b-2 border-primary text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          文案
        </button>
        <button
          onClick={() => setActiveTab('blueprint')}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'blueprint'
              ? 'border-b-2 border-primary text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          拍摄蓝图
        </button>
      </div>

      {/* Content */}
      {activeTab === 'text' && (
        <div className="space-y-4">
          {/* Hook */}
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">
              Hook（前3秒）
            </div>
            <div className="text-sm bg-secondary/50 rounded p-3">
              {text_structure.hook}
            </div>
          </div>

          {/* Body */}
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">
              Body（主体内容）
            </div>
            <div className="text-sm bg-secondary/50 rounded p-3">
              {text_structure.body}
            </div>
          </div>

          {/* CTA */}
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">
              CTA（行动号召）
            </div>
            <div className="text-sm bg-secondary/50 rounded p-3">
              {text_structure.cta}
            </div>
          </div>

          {/* Full Text */}
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">
              完整文案
            </div>
            <div className="text-sm bg-secondary/50 rounded p-3 whitespace-pre-wrap">
              {text_structure.full_text}
            </div>
          </div>

          {/* GEO Keywords */}
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-2">
              GEO关键词
            </div>
            <div className="flex flex-wrap gap-2">
              {geo_keywords.map((keyword, i) => (
                <span
                  key={i}
                  className="text-xs px-2 py-1 rounded bg-primary/10 text-primary"
                >
                  {keyword}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'blueprint' && (
        <div className="space-y-4">
          {/* Scene */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Film className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">场景</span>
            </div>
            <div className="text-sm bg-secondary/50 rounded p-3">
              {blueprint.scene}
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {blueprint.scene_tags.map((tag, i) => (
                <span
                  key={i}
                  className="text-xs px-2 py-1 rounded bg-secondary text-foreground"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Shot List */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Camera className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">镜头列表</span>
            </div>
            <div className="space-y-2">
              {blueprint.shot_list.map((shot, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 bg-secondary/50 rounded p-3"
                >
                  <span className="text-lg">{shotTypeIcons[shot.type] || '🎬'}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium">{shot.type}</span>
                      <span className="text-xs text-muted-foreground">
                        {shot.duration_s}s
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {shot.camera_movement}
                      </span>
                    </div>
                    <div className="text-sm">{shot.subject}</div>
                    {shot.description && (
                      <div className="text-xs text-muted-foreground mt-1">
                        {shot.description}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Visual Style */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Lightbulb className="h-4 w-4 text-primary" />
                <span className="text-sm font-medium">光线</span>
              </div>
              <div className="text-sm bg-secondary/50 rounded p-2">
                {blueprint.lighting}
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Palette className="h-4 w-4 text-primary" />
                <span className="text-sm font-medium">色调</span>
              </div>
              <div className="text-sm bg-secondary/50 rounded p-2">
                {blueprint.color_tone}
              </div>
            </div>
          </div>

          {/* Props */}
          <div>
            <div className="text-sm font-medium mb-2">道具清单</div>
            <div className="space-y-2">
              <div>
                <div className="text-xs text-muted-foreground mb-1">必备道具</div>
                <div className="flex flex-wrap gap-2">
                  {blueprint.props.map((prop, i) => (
                    <span
                      key={i}
                      className="text-xs px-2 py-1 rounded bg-primary/10 text-primary"
                    >
                      {prop}
                    </span>
                  ))}
                </div>
              </div>
              {blueprint.optional_props.length > 0 && (
                <div>
                  <div className="text-xs text-muted-foreground mb-1">可选道具</div>
                  <div className="flex flex-wrap gap-2">
                    {blueprint.optional_props.map((prop, i) => (
                      <span
                        key={i}
                        className="text-xs px-2 py-1 rounded bg-secondary text-foreground"
                      >
                        {prop}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Subtitle Style */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Type className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">字幕样式</span>
            </div>
            <div className="text-sm bg-secondary/50 rounded p-2">
              {blueprint.subtitle_style}
            </div>
          </div>

          {/* Micro Innovation */}
          <div>
            <div className="text-sm font-medium mb-2">微创新点</div>
            <div className="text-sm bg-primary/10 rounded p-3 text-primary">
              {blueprint.micro_innovation}
            </div>
          </div>

          {/* Metadata */}
          <div className="flex items-center justify-between pt-4 border-t border-border">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                预计制作时长: {blueprint.estimated_production_time_min} 分钟
              </span>
            </div>
            <span className={`text-sm font-medium ${difficultyColors[blueprint.difficulty_level]}`}>
              难度: {blueprint.difficulty_level}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
