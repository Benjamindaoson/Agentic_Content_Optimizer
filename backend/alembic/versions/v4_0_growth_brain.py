"""
v4.0 数据库迁移脚本

新增表：
1. 自动化账号运营相关表
2. 多模态封面引擎相关表
3. 多平台内容引擎相关表
4. 因果推断引擎相关表
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'v4_0_growth_brain'
down_revision = None  # 初始版本
branch_labels = None
depends_on = None


def upgrade():
    """升级到 v4.0"""

    # ==================== 自动化账号运营表 ====================

    # 发现的话题表
    op.create_table(
        'discovered_topics',
        sa.Column('topic_id', sa.String(64), primary_key=True, comment='话题ID'),
        sa.Column('topic_name', sa.String(256), nullable=False, comment='话题名称'),
        sa.Column('topic_keywords', postgresql.JSON, comment='话题关键词'),
        sa.Column('source', sa.String(32), nullable=False, comment='来源'),
        sa.Column('heat_score', sa.Float, comment='热度分数'),
        sa.Column('trending_rank', sa.Integer, comment='热榜排名'),
        sa.Column('related_notes_count', sa.Integer, default=0, comment='相关笔记数'),
        sa.Column('persona_fit_score', sa.Float, comment='人设适配分数'),
        sa.Column('opportunity_score', sa.Float, comment='机会分数'),
        sa.Column('discovered_at', sa.DateTime, default=sa.func.now(), comment='发现时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='发现的话题表'
    )

    # 内容排程表
    op.create_table(
        'content_schedules',
        sa.Column('schedule_id', sa.String(64), primary_key=True, comment='排程ID'),
        sa.Column('account_id', sa.String(64), nullable=False, comment='账号ID'),
        sa.Column('topic_id', sa.String(64), comment='话题ID'),
        sa.Column('generation_id', sa.String(64), comment='生成ID'),
        sa.Column('scheduled_time', sa.DateTime, nullable=False, comment='计划时间'),
        sa.Column('strategy', sa.String(32), comment='排程策略'),
        sa.Column('predicted_performance', sa.Float, comment='预测表现'),
        sa.Column('status', sa.String(32), default='pending', comment='状态'),
        sa.Column('published_at', sa.DateTime, comment='实际发布时间'),
        sa.Column('actual_performance', sa.Float, comment='实际表现'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='内容排程表'
    )

    # 每日计划表
    op.create_table(
        'daily_plans',
        sa.Column('plan_id', sa.String(64), primary_key=True, comment='计划ID'),
        sa.Column('account_id', sa.String(64), nullable=False, comment='账号ID'),
        sa.Column('plan_date', sa.Date, nullable=False, comment='计划日期'),
        sa.Column('selected_topics', postgresql.JSON, comment='选中的话题'),
        sa.Column('schedules', postgresql.JSON, comment='排程列表'),
        sa.Column('executed_count', sa.Integer, default=0, comment='已执行数量'),
        sa.Column('avg_performance', sa.Float, comment='平均表现'),
        sa.Column('status', sa.String(32), default='pending', comment='状态'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='每日计划表'
    )

    # ==================== 多模态封面引擎表 ====================

    # 生成的封面表
    op.create_table(
        'generated_covers',
        sa.Column('cover_id', sa.String(64), primary_key=True, comment='封面ID'),
        sa.Column('generator', sa.String(32), nullable=False, comment='生成器'),
        sa.Column('prompt', sa.Text, comment='生成提示词'),
        sa.Column('negative_prompt', sa.Text, comment='负面提示词'),
        sa.Column('style', sa.String(32), comment='风格'),
        sa.Column('image_path', sa.String(1024), comment='图片路径'),
        sa.Column('image_url', sa.String(1024), comment='图片URL'),
        sa.Column('width', sa.Integer, comment='宽度'),
        sa.Column('height', sa.Integer, comment='高度'),
        sa.Column('aspect_ratio', sa.String(16), comment='宽高比'),
        sa.Column('dominant_colors', postgresql.JSON, comment='主色调'),
        sa.Column('color_distribution', postgresql.JSON, comment='色彩分布'),
        sa.Column('has_face', sa.Boolean, default=False, comment='是否有人脸'),
        sa.Column('face_position', postgresql.JSON, comment='人脸位置'),
        sa.Column('text_overlay', sa.Boolean, default=False, comment='是否有文字叠加'),
        sa.Column('text_content', sa.Text, comment='文字内容'),
        sa.Column('predicted_ctr', sa.Float, comment='预测点击率'),
        sa.Column('predicted_engagement', sa.Float, comment='预测互动率'),
        sa.Column('actual_ctr', sa.Float, comment='实际点击率'),
        sa.Column('actual_engagement', sa.Float, comment='实际互动率'),
        sa.Column('impressions', sa.Integer, default=0, comment='曝光数'),
        sa.Column('clicks', sa.Integer, default=0, comment='点击数'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='生成的封面表'
    )

    # 封面 A/B 测试表
    op.create_table(
        'cover_ab_tests',
        sa.Column('test_id', sa.String(64), primary_key=True, comment='测试ID'),
        sa.Column('generation_id', sa.String(64), comment='生成ID'),
        sa.Column('cover_variants', postgresql.JSON, comment='封面变体列表'),
        sa.Column('variant_count', sa.Integer, comment='变体数量'),
        sa.Column('traffic_split', postgresql.JSON, comment='流量分配'),
        sa.Column('test_duration_hours', sa.Integer, default=1, comment='测试时长（小时）'),
        sa.Column('status', sa.String(32), default='running', comment='状态'),
        sa.Column('started_at', sa.DateTime, comment='开始时间'),
        sa.Column('ended_at', sa.DateTime, comment='结束时间'),
        sa.Column('winner_cover_id', sa.String(64), comment='胜出封面ID'),
        sa.Column('winner_ctr', sa.Float, comment='胜出点击率'),
        sa.Column('confidence', sa.Float, comment='置信度'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='封面 A/B 测试表'
    )

    # 封面特征表
    op.create_table(
        'cover_features',
        sa.Column('feature_id', sa.String(64), primary_key=True, comment='特征ID'),
        sa.Column('cover_id', sa.String(64), nullable=False, comment='封面ID'),
        sa.Column('avg_brightness', sa.Float, comment='平均亮度'),
        sa.Column('avg_saturation', sa.Float, comment='平均饱和度'),
        sa.Column('color_variance', sa.Float, comment='色彩方差'),
        sa.Column('dominant_hue', sa.Float, comment='主色调'),
        sa.Column('composition_score', sa.Float, comment='构图分数'),
        sa.Column('rule_of_thirds', sa.Float, comment='三分法得分'),
        sa.Column('symmetry_score', sa.Float, comment='对称性得分'),
        sa.Column('face_count', sa.Integer, default=0, comment='人脸数量'),
        sa.Column('face_area_ratio', sa.Float, comment='人脸面积占比'),
        sa.Column('text_area_ratio', sa.Float, comment='文字面积占比'),
        sa.Column('object_count', sa.Integer, comment='物体数量'),
        sa.Column('edge_density', sa.Float, comment='边缘密度'),
        sa.Column('texture_complexity', sa.Float, comment='纹理复杂度'),
        sa.Column('extracted_at', sa.DateTime, default=sa.func.now(), comment='提取时间'),
        comment='封面特征表'
    )

    # ==================== 多平台内容引擎表 ====================

    # 统一内容记录表
    op.create_table(
        'unified_content_records',
        sa.Column('content_id', sa.String(64), primary_key=True, comment='内容ID'),
        sa.Column('title', sa.String(512), nullable=False, comment='标题'),
        sa.Column('body', sa.Text, nullable=False, comment='正文'),
        sa.Column('hook', sa.Text, comment='开头钩子'),
        sa.Column('call_to_action', sa.Text, comment='行动号召'),
        sa.Column('content_type', sa.String(32), nullable=False, comment='内容类型'),
        sa.Column('cover_image_path', sa.String(1024), comment='封面图片路径'),
        sa.Column('video_path', sa.String(1024), comment='视频路径'),
        sa.Column('audio_path', sa.String(1024), comment='音频路径'),
        sa.Column('additional_images', postgresql.JSON, comment='额外图片'),
        sa.Column('topic', sa.String(256), comment='话题'),
        sa.Column('tags', postgresql.JSON, comment='标签'),
        sa.Column('target_audience', postgresql.JSON, comment='目标受众'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='统一内容记录表'
    )

    # 平台适配表
    op.create_table(
        'platform_adaptations',
        sa.Column('adaptation_id', sa.String(64), primary_key=True, comment='适配ID'),
        sa.Column('content_id', sa.String(64), nullable=False, comment='内容ID'),
        sa.Column('platform', sa.String(32), nullable=False, comment='平台'),
        sa.Column('adapted_title', sa.String(512), comment='适配后标题'),
        sa.Column('adapted_body', sa.Text, comment='适配后正文'),
        sa.Column('adapted_tags', postgresql.JSON, comment='适配后标签'),
        sa.Column('platform_config', postgresql.JSON, comment='平台配置'),
        sa.Column('processed_cover', sa.String(1024), comment='处理后封面'),
        sa.Column('processed_video', sa.String(1024), comment='处理后视频'),
        sa.Column('status', sa.String(32), default='pending', comment='状态'),
        sa.Column('platform_post_id', sa.String(128), comment='平台帖子ID'),
        sa.Column('platform_url', sa.String(1024), comment='平台URL'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('published_at', sa.DateTime, comment='发布时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='平台适配表'
    )

    # 跨平台表现表
    op.create_table(
        'cross_platform_performances',
        sa.Column('performance_id', sa.String(64), primary_key=True, comment='表现ID'),
        sa.Column('content_id', sa.String(64), nullable=False, comment='内容ID'),
        sa.Column('platform', sa.String(32), nullable=False, comment='平台'),
        sa.Column('views', sa.Integer, default=0, comment='浏览数'),
        sa.Column('likes', sa.Integer, default=0, comment='点赞数'),
        sa.Column('comments', sa.Integer, default=0, comment='评论数'),
        sa.Column('shares', sa.Integer, default=0, comment='分享数'),
        sa.Column('engagement_rate', sa.Float, comment='互动率'),
        sa.Column('relative_performance', sa.Float, comment='相对表现'),
        sa.Column('collected_at', sa.DateTime, default=sa.func.now(), comment='收集时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='跨平台表现表'
    )

    # ==================== 因果推断引擎表 ====================

    # 因果图表
    op.create_table(
        'causal_graphs',
        sa.Column('graph_id', sa.String(64), primary_key=True, comment='图ID'),
        sa.Column('graph_name', sa.String(256), nullable=False, comment='图名称'),
        sa.Column('nodes', postgresql.JSON, nullable=False, comment='节点列表'),
        sa.Column('edges', postgresql.JSON, nullable=False, comment='边列表'),
        sa.Column('is_dag', sa.Boolean, default=True, comment='是否为DAG'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='因果图表'
    )

    # 因果效应表
    op.create_table(
        'causal_effects',
        sa.Column('effect_id', sa.String(64), primary_key=True, comment='效应ID'),
        sa.Column('graph_id', sa.String(64), comment='图ID'),
        sa.Column('treatment', sa.String(128), nullable=False, comment='处理变量'),
        sa.Column('outcome', sa.String(128), nullable=False, comment='结果变量'),
        sa.Column('common_causes', postgresql.JSON, comment='共同原因'),
        sa.Column('effect_size', sa.Float, comment='效应大小'),
        sa.Column('standard_error', sa.Float, comment='标准误'),
        sa.Column('confidence_interval_lower', sa.Float, comment='置信区间下界'),
        sa.Column('confidence_interval_upper', sa.Float, comment='置信区间上界'),
        sa.Column('p_value', sa.Float, comment='p值'),
        sa.Column('estimation_method', sa.String(64), comment='估计方法'),
        sa.Column('sample_size', sa.Integer, comment='样本量'),
        sa.Column('estimated_at', sa.DateTime, default=sa.func.now(), comment='估计时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='因果效应表'
    )

    # 反事实场景表
    op.create_table(
        'counterfactual_scenarios',
        sa.Column('scenario_id', sa.String(64), primary_key=True, comment='场景ID'),
        sa.Column('scenario_name', sa.String(256), nullable=False, comment='场景名称'),
        sa.Column('graph_id', sa.String(64), comment='图ID'),
        sa.Column('actual_treatment', postgresql.JSON, nullable=False, comment='实际处理'),
        sa.Column('actual_outcome', sa.Float, comment='实际结果'),
        sa.Column('counterfactual_treatment', postgresql.JSON, nullable=False, comment='反事实处理'),
        sa.Column('counterfactual_outcome', sa.Float, comment='反事实结果'),
        sa.Column('treatment_effect', sa.Float, comment='处理效应'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('metadata', postgresql.JSON, comment='其他元数据'),
        comment='反事实场景表'
    )

    # ==================== 创建索引 ====================

    # 自动化账号运营索引
    op.create_index('idx_discovered_topics_source', 'discovered_topics', ['source'])
    op.create_index('idx_discovered_topics_heat', 'discovered_topics', ['heat_score'])
    op.create_index('idx_content_schedules_account', 'content_schedules', ['account_id'])
    op.create_index('idx_content_schedules_time', 'content_schedules', ['scheduled_time'])
    op.create_index('idx_daily_plans_account_date', 'daily_plans', ['account_id', 'plan_date'])

    # 多模态封面引擎索引
    op.create_index('idx_generated_covers_generator', 'generated_covers', ['generator'])
    op.create_index('idx_generated_covers_style', 'generated_covers', ['style'])
    op.create_index('idx_cover_ab_tests_status', 'cover_ab_tests', ['status'])
    op.create_index('idx_cover_features_cover', 'cover_features', ['cover_id'])

    # 多平台内容引擎索引
    op.create_index('idx_unified_content_created', 'unified_content_records', ['created_at'])
    op.create_index('idx_platform_adaptations_content', 'platform_adaptations', ['content_id'])
    op.create_index('idx_platform_adaptations_platform', 'platform_adaptations', ['platform'])
    op.create_index('idx_cross_platform_content', 'cross_platform_performances', ['content_id'])
    op.create_index('idx_cross_platform_platform', 'cross_platform_performances', ['platform'])

    # 因果推断引擎索引
    op.create_index('idx_causal_effects_treatment', 'causal_effects', ['treatment'])
    op.create_index('idx_causal_effects_outcome', 'causal_effects', ['outcome'])
    op.create_index('idx_counterfactual_graph', 'counterfactual_scenarios', ['graph_id'])


def downgrade():
    """降级到 v3.2"""

    # 删除索引
    op.drop_index('idx_counterfactual_graph')
    op.drop_index('idx_causal_effects_outcome')
    op.drop_index('idx_causal_effects_treatment')
    op.drop_index('idx_cross_platform_platform')
    op.drop_index('idx_cross_platform_content')
    op.drop_index('idx_platform_adaptations_platform')
    op.drop_index('idx_platform_adaptations_content')
    op.drop_index('idx_unified_content_created')
    op.drop_index('idx_cover_features_cover')
    op.drop_index('idx_cover_ab_tests_status')
    op.drop_index('idx_generated_covers_style')
    op.drop_index('idx_generated_covers_generator')
    op.drop_index('idx_daily_plans_account_date')
    op.drop_index('idx_content_schedules_time')
    op.drop_index('idx_content_schedules_account')
    op.drop_index('idx_discovered_topics_heat')
    op.drop_index('idx_discovered_topics_source')

    # 删除表
    op.drop_table('counterfactual_scenarios')
    op.drop_table('causal_effects')
    op.drop_table('causal_graphs')
    op.drop_table('cross_platform_performances')
    op.drop_table('platform_adaptations')
    op.drop_table('unified_content_records')
    op.drop_table('cover_features')
    op.drop_table('cover_ab_tests')
    op.drop_table('generated_covers')
    op.drop_table('daily_plans')
    op.drop_table('content_schedules')
    op.drop_table('discovered_topics')
