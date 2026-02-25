'use client'

import { CheckCircle, XCircle, AlertCircle, TrendingUp, Award } from 'lucide-react'

interface DimensionScore {
  dimension: string
  score: number
  reasoning: string
  suggestions: string[]
}

interface CriticEvaluation {
  dimension_scores: DimensionScore[]
  overall_score: number
  approval_status: 'approved' | 'rejected' | 'needs_revision'
  summary: string
  critical_issues: string[]
  highlights: string[]
  improvement_suggestions: string[]
}

interface RewardComponents {
  quality_reward: number
  predicted_engagement: number
  predicted_completion: number
  predicted_conversion: number
  diversity_bonus: number
  geo_bonus: number
  innovation_bonus: number
}

interface RewardScore {
  components: RewardComponents
  total_reward: number
  goal_weights: {
    engagement: number
    completion: number
    conversion: number
  }
}

interface EvaluationCardProps {
  evaluation: CriticEvaluation
  reward: RewardScore
  contentId: string
}

export function EvaluationCard({ evaluation, reward, contentId }: EvaluationCardProps) {
  const statusConfig = {
    approved: {
      icon: CheckCircle,
      color: 'text-green-500',
      bg: 'bg-green-500/10',
      label: '通过'
    },
    rejected: {
      icon: XCircle,
      color: 'text-red-500',
      bg: 'bg-red-500/10',
      label: '拒绝'
    },
    needs_revision: {
      icon: AlertCircle,
      color: 'text-yellow-500',
      bg: 'bg-yellow-500/10',
      label: '需要修改'
    }
  }

  const status = statusConfig[evaluation.approval_status]
  const StatusIcon = status.icon

  // 维度名称映射
  const dimensionNames: Record<string, string> = {
    creativity: '创意性',
    executability: '可执行性',
    geo_optimization: 'GEO优化',
    platform_fit: '平台适配',
    engagement_potential: '互动潜力'
  }

  // 分数颜色
  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-green-500'
    if (score >= 0.6) return 'text-yellow-500'
    return 'text-red-500'
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <StatusIcon className={`h-6 w-6 ${status.color}`} />
          <div>
            <h3 className="text-lg font-semibold">{contentId}</h3>
            <p className="text-sm text-muted-foreground">{evaluation.summary}</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold">{evaluation.overall_score.toFixed(2)}</div>
          <div className={`text-sm font-medium ${status.color}`}>{status.label}</div>
        </div>
      </div>

      {/* Dimension Scores */}
      <div className="space-y-4 mb-6">
        <div className="text-sm font-medium">维度评分</div>
        {evaluation.dimension_scores.map((dim, i) => (
          <div key={i} className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm">{dimensionNames[dim.dimension] || dim.dimension}</span>
              <span className={`text-sm font-medium ${getScoreColor(dim.score)}`}>
                {dim.score.toFixed(2)}
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-secondary">
              <div
                className={`h-2 rounded-full ${
                  dim.score >= 0.8
                    ? 'bg-green-500'
                    : dim.score >= 0.6
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
                }`}
                style={{ width: `${dim.score * 100}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">{dim.reasoning}</p>
          </div>
        ))}
      </div>

      {/* Highlights */}
      {evaluation.highlights.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <Award className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">内容亮点</span>
          </div>
          <ul className="space-y-1">
            {evaluation.highlights.map((highlight, i) => (
              <li key={i} className="text-sm text-muted-foreground pl-4">
                • {highlight}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Critical Issues */}
      {evaluation.critical_issues.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="h-4 w-4 text-red-500" />
            <span className="text-sm font-medium">关键问题</span>
          </div>
          <ul className="space-y-1">
            {evaluation.critical_issues.map((issue, i) => (
              <li key={i} className="text-sm text-red-500 pl-4">
                • {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Improvement Suggestions */}
      {evaluation.improvement_suggestions.length > 0 && (
        <div className="mb-4">
          <div className="text-sm font-medium mb-2">改进建议</div>
          <ul className="space-y-1">
            {evaluation.improvement_suggestions.map((suggestion, i) => (
              <li key={i} className="text-sm text-muted-foreground pl-4">
                • {suggestion}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Reward Score */}
      <div className="border-t border-border pt-4">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium">奖励分数</span>
          <span className="text-lg font-bold text-primary ml-auto">
            {reward.total_reward.toFixed(3)}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <div className="text-muted-foreground">质量奖励</div>
            <div className="font-medium">{reward.components.quality_reward.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-muted-foreground">预测互动率</div>
            <div className="font-medium">{reward.components.predicted_engagement.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-muted-foreground">预测完播率</div>
            <div className="font-medium">{reward.components.predicted_completion.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-muted-foreground">预测转化率</div>
            <div className="font-medium">{reward.components.predicted_conversion.toFixed(2)}</div>
          </div>
        </div>

        {/* Bonuses */}
        {(reward.components.diversity_bonus > 0 ||
          reward.components.geo_bonus > 0 ||
          reward.components.innovation_bonus > 0) && (
          <div className="mt-3 pt-3 border-t border-border">
            <div className="text-xs text-muted-foreground mb-2">奖励加成</div>
            <div className="flex flex-wrap gap-2">
              {reward.components.diversity_bonus > 0 && (
                <span className="text-xs px-2 py-1 rounded bg-primary/10 text-primary">
                  多样性 +{reward.components.diversity_bonus.toFixed(2)}
                </span>
              )}
              {reward.components.geo_bonus > 0 && (
                <span className="text-xs px-2 py-1 rounded bg-primary/10 text-primary">
                  GEO +{reward.components.geo_bonus.toFixed(2)}
                </span>
              )}
              {reward.components.innovation_bonus > 0 && (
                <span className="text-xs px-2 py-1 rounded bg-primary/10 text-primary">
                  创新 +{reward.components.innovation_bonus.toFixed(2)}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
