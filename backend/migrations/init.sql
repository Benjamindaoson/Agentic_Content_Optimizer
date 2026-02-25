-- Growth Flywheel 2.5 数据库初始化脚本

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS growth_flywheel;

-- 连接到数据库
\c growth_flywheel;

-- 启用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- 用于文本相似度搜索

-- 创建枚举类型
CREATE TYPE user_role AS ENUM ('admin', 'user');
CREATE TYPE platform_type AS ENUM ('xiaohongshu', 'douyin', 'tiktok', 'kuaishou');
CREATE TYPE goal_metric_type AS ENUM ('engagement', 'completion', 'conversion');
CREATE TYPE project_status_type AS ENUM ('active', 'paused', 'archived');

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role user_role DEFAULT 'user' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- 项目表
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic VARCHAR(200) NOT NULL,
    platform platform_type NOT NULL,
    goal_metric goal_metric_type NOT NULL,
    status project_status_type DEFAULT 'active',
    total_episodes INTEGER DEFAULT 0,
    avg_geo_score FLOAT DEFAULT 0.0,
    total_token_cost INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_platform ON projects(platform);
CREATE INDEX idx_projects_status ON projects(status);

-- 策略规格表
CREATE TABLE IF NOT EXISTS strategy_specs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic_id VARCHAR(100) NOT NULL,
    geo_constraints JSONB DEFAULT '{}',
    target_audience VARCHAR(200),
    content_style VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_strategy_specs_project_id ON strategy_specs(project_id);
CREATE INDEX idx_strategy_specs_topic_id ON strategy_specs(topic_id);

-- 爆款内容表
CREATE TABLE IF NOT EXISTS viral_contents (
    id SERIAL PRIMARY KEY,
    platform platform_type NOT NULL,
    content_id VARCHAR(100) UNIQUE NOT NULL,
    author_id VARCHAR(100) NOT NULL,
    text TEXT NOT NULL,
    image_urls JSONB DEFAULT '[]',
    video_url VARCHAR(500),
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    collects INTEGER DEFAULT 0,
    engagement_score FLOAT DEFAULT 0,
    hook_type VARCHAR(50),
    body_structure VARCHAR(50),
    cta_type VARCHAR(50),
    visual_blueprint JSONB,
    author_baseline FLOAT DEFAULT 0,
    relative_lift FLOAT DEFAULT 0,
    geo_score FLOAT,
    geo_keywords JSONB DEFAULT '[]',
    published_at TIMESTAMP WITH TIME ZONE,
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_viral_contents_platform ON viral_contents(platform);
CREATE INDEX idx_viral_contents_content_id ON viral_contents(content_id);
CREATE INDEX idx_viral_contents_author_id ON viral_contents(author_id);
CREATE INDEX idx_viral_contents_engagement ON viral_contents(engagement_score DESC);
CREATE INDEX idx_viral_contents_hook ON viral_contents(hook_type);
CREATE INDEX idx_viral_contents_body ON viral_contents(body_structure);

-- 飞轮事实表
CREATE TABLE IF NOT EXISTS fact_episodes (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    episode_id VARCHAR(50) UNIQUE NOT NULL,
    trace_id VARCHAR(50) NOT NULL,
    topic_id VARCHAR(100) NOT NULL,
    group_actions JSONB NOT NULL,
    pred_rewards JSONB NOT NULL,
    ranked_actions JSONB NOT NULL,
    policy_update_summary JSONB,
    policy_version VARCHAR(50),
    geo_coverage_avg FLOAT,
    diversity_score FLOAT,
    admit_rate FLOAT,
    director_version VARCHAR(50) DEFAULT 'v1.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_fact_episodes_project_id ON fact_episodes(project_id);
CREATE INDEX idx_fact_episodes_episode_id ON fact_episodes(episode_id);
CREATE INDEX idx_fact_episodes_trace_id ON fact_episodes(trace_id);
CREATE INDEX idx_fact_episodes_topic_id ON fact_episodes(topic_id);

-- 内容实验表
CREATE TABLE IF NOT EXISTS content_experiments (
    id SERIAL PRIMARY KEY,
    episode_id INTEGER NOT NULL REFERENCES fact_episodes(id) ON DELETE CASCADE,
    reference_id INTEGER REFERENCES viral_contents(id) ON DELETE SET NULL,
    hook_strategy VARCHAR(10) NOT NULL,
    body_strategy VARCHAR(10) NOT NULL,
    cta_strategy VARCHAR(10) NOT NULL,
    generated_text TEXT NOT NULL,
    text_structure JSONB NOT NULL,
    geo_keywords JSONB DEFAULT '[]',
    geo_coverage FLOAT,
    blueprint JSONB NOT NULL,
    published BOOLEAN DEFAULT FALSE,
    actual_engagement FLOAT,
    reward_score FLOAT,
    predicted_reward FLOAT,
    prediction_error FLOAT,
    group_id VARCHAR(50),
    rank_in_group INTEGER,
    group_size INTEGER,
    critic_approved BOOLEAN DEFAULT FALSE,
    critic_score FLOAT,
    critic_feedback TEXT,
    trace_id VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_content_experiments_episode_id ON content_experiments(episode_id);
CREATE INDEX idx_content_experiments_reference_id ON content_experiments(reference_id);
CREATE INDEX idx_content_experiments_group_id ON content_experiments(group_id);
CREATE INDEX idx_content_experiments_trace_id ON content_experiments(trace_id);

-- Reference Pool 元数据表
CREATE TABLE IF NOT EXISTS reference_pool_metadata (
    id SERIAL PRIMARY KEY,
    ref_id VARCHAR(100) UNIQUE NOT NULL,
    style VARCHAR(100),
    scene_tags JSONB DEFAULT '[]',
    platform platform_type NOT NULL,
    stats JSONB DEFAULT '{}',
    vector_id VARCHAR(100) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_reference_pool_ref_id ON reference_pool_metadata(ref_id);
CREATE INDEX idx_reference_pool_platform ON reference_pool_metadata(platform);

-- 动作空间字典表
CREATE TABLE IF NOT EXISTS action_space_dict (
    code VARCHAR(10) PRIMARY KEY,
    category VARCHAR(10) NOT NULL,
    name VARCHAR(50) NOT NULL,
    description TEXT,
    usage_count INTEGER DEFAULT 0,
    avg_reward FLOAT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 插入 Hook 字典
INSERT INTO action_space_dict (code, category, name, description) VALUES
('H01', 'hook', '利益点前置', '开头直接说结果："3天瘦5斤"'),
('H02', 'hook', '痛点反问', '疑问句开场:"还在为XX烦恼吗？"'),
('H03', 'hook', '数字冲击', '数据震撼："99%的人不知道"'),
('H04', 'hook', '反常识', '颠覆认知："你以为XX，其实..."'),
('H05', 'hook', '身份认同', '群体归属："姐妹们！"'),
('H06', 'hook', '场景代入', '情景描述："下班回家..."'),
('H07', 'hook', '悬念设置', '引发好奇："最后一个绝了"'),
('H08', 'hook', '对比震撼', '前后对比："before/after"'),
('H09', 'hook', '权威背书', '专家推荐："医生推荐"'),
('H10', 'hook', '限时紧迫', '制造紧迫："今天最后一天"');

-- 插入 Body 字典
INSERT INTO action_space_dict (code, category, name, description) VALUES
('B01', 'body', '避坑指南', '强调"千万别"："这3个坑千万别踩"'),
('B02', 'body', '分点教学', '结构化呈现："1. 2. 3."'),
('B03', 'body', '对比测评', '横向比较："A vs B"'),
('B04', 'body', '故事叙事', '个人经历："我之前..."'),
('B05', 'body', '数据说话', '实测结果："实测7天效果"'),
('B06', 'body', '案例展示', '他人案例："看看小红的变化"'),
('B07', 'body', '步骤拆解', '流程指导："第一步...第二步..."'),
('B08', 'body', '清单罗列', '列表呈现："必备清单"');

-- 插入 CTA 字典
INSERT INTO action_space_dict (code, category, name, description) VALUES
('C01', 'cta', '互动指令', '引导互动："评论区扣1"'),
('C02', 'cta', '利益诱导', '收藏引导："点赞收藏不迷路"'),
('C03', 'cta', '悬念引导', '预告下期："下期揭秘"'),
('C04', 'cta', '社交证明', '从众效应："已有1000+姐妹"'),
('C05', 'cta', '限时促销', '限时优惠："前100名"');

-- 创建自动更新 updated_at 的触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为所有表添加触发器
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_strategy_specs_updated_at BEFORE UPDATE ON strategy_specs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_viral_contents_updated_at BEFORE UPDATE ON viral_contents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_fact_episodes_updated_at BEFORE UPDATE ON fact_episodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_experiments_updated_at BEFORE UPDATE ON content_experiments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reference_pool_metadata_updated_at BEFORE UPDATE ON reference_pool_metadata
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 创建视图：策略演进分析
CREATE OR REPLACE VIEW v_policy_evolution AS
SELECT
    DATE_TRUNC('day', ce.created_at) AS date,
    ce.hook_strategy,
    ce.body_strategy,
    ce.cta_strategy,
    COUNT(*) AS sample_count,
    AVG(ce.predicted_reward) AS avg_pred_reward,
    AVG(CASE WHEN ce.published THEN ce.reward_score END) AS avg_actual_reward,
    AVG(ce.critic_score) AS avg_critic_score,
    SUM(CASE WHEN ce.critic_approved THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS admit_rate
FROM content_experiments ce
GROUP BY DATE_TRUNC('day', ce.created_at), ce.hook_strategy, ce.body_strategy, ce.cta_strategy
ORDER BY date DESC;

-- 完成
COMMENT ON DATABASE growth_flywheel IS 'Growth Flywheel 2.5 - AI 驱动的内容策略进化引擎';
