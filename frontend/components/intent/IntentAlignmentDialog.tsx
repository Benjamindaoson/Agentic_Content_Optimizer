'use client'

import { useState } from 'react'
import { X } from 'lucide-react'

interface IntentAlignmentDialogProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: IntentData) => void
}

export interface IntentData {
  topic: string
  platform: string
  goalMetric: string
  targetAudience?: string
  contentStyle?: string
}

export function IntentAlignmentDialog({
  isOpen,
  onClose,
  onSubmit
}: IntentAlignmentDialogProps) {
  const [step, setStep] = useState(1)
  const [formData, setFormData] = useState<IntentData>({
    topic: '',
    platform: 'xiaohongshu',
    goalMetric: 'engagement'
  })

  if (!isOpen) return null

  const handleNext = () => {
    if (step < 3) {
      setStep(step + 1)
    } else {
      onSubmit(formData)
      onClose()
    }
  }

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl rounded-lg border border-border bg-card p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold">策略对齐</h2>
            <p className="text-sm text-muted-foreground mt-1">
              步骤 {step} / 3
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-2 hover:bg-secondary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="h-2 w-full rounded-full bg-secondary">
            <div
              className="h-2 rounded-full bg-primary transition-all duration-300"
              style={{ width: `${(step / 3) * 100}%` }}
            />
          </div>
        </div>

        {/* Step 1: 基础信息 */}
        {step === 1 && (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium mb-2">
                话题/产品 *
              </label>
              <input
                type="text"
                value={formData.topic}
                onChange={(e) => setFormData({ ...formData, topic: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-4 py-2 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="例如：AI 提效工具"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                目标平台 *
              </label>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { value: 'xiaohongshu', label: '小红书' },
                  { value: 'douyin', label: '抖音' },
                  { value: 'tiktok', label: 'TikTok' },
                  { value: 'kuaishou', label: '快手' }
                ].map((platform) => (
                  <button
                    key={platform.value}
                    onClick={() => setFormData({ ...formData, platform: platform.value })}
                    className={`rounded-md border px-4 py-3 text-sm font-medium transition-colors ${
                      formData.platform === platform.value
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border hover:bg-secondary'
                    }`}
                  >
                    {platform.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 2: 目标指标 */}
        {step === 2 && (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium mb-2">
                目标指标 *
              </label>
              <div className="space-y-3">
                {[
                  { value: 'engagement', label: '互动率', desc: '点赞、评论、分享' },
                  { value: 'completion', label: '完播率', desc: '视频完整观看' },
                  { value: 'conversion', label: '转化率', desc: '引导行动' }
                ].map((metric) => (
                  <button
                    key={metric.value}
                    onClick={() => setFormData({ ...formData, goalMetric: metric.value })}
                    className={`w-full rounded-md border px-4 py-3 text-left transition-colors ${
                      formData.goalMetric === metric.value
                        ? 'border-primary bg-primary/10'
                        : 'border-border hover:bg-secondary'
                    }`}
                  >
                    <div className="font-medium">{metric.label}</div>
                    <div className="text-sm text-muted-foreground">{metric.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 3: 可选信息 */}
        {step === 3 && (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium mb-2">
                目标受众（可选）
              </label>
              <input
                type="text"
                value={formData.targetAudience || ''}
                onChange={(e) => setFormData({ ...formData, targetAudience: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-4 py-2 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="例如：25-35岁职场人士"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                内容风格（可选）
              </label>
              <input
                type="text"
                value={formData.contentStyle || ''}
                onChange={(e) => setFormData({ ...formData, contentStyle: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-4 py-2 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="例如：专业、轻松、幽默"
              />
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-between mt-8">
          <button
            onClick={handleBack}
            disabled={step === 1}
            className="rounded-md bg-secondary px-6 py-2 text-sm font-medium hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            上一步
          </button>
          <button
            onClick={handleNext}
            disabled={!formData.topic}
            className="rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {step === 3 ? '开始生成' : '下一步'}
          </button>
        </div>
      </div>
    </div>
  )
}
