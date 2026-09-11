-- ============================================
-- AI Tutor 数据库初始化
-- ============================================

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- 用户表
-- ============================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(500),
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

-- ============================================
-- Thread 管理 (Agent 对话)
-- ============================================

CREATE TABLE threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused')),
    state JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_threads_user ON threads(user_id);
CREATE INDEX idx_threads_status ON threads(status);

-- Agent 执行记录
CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'waiting_hitl')),
    input JSONB NOT NULL,
    output JSONB,
    error_message TEXT,
    hitl_required BOOLEAN DEFAULT FALSE,
    hitl_action VARCHAR(100),
    hitl_options JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_runs_thread ON runs(thread_id);
CREATE INDEX idx_runs_status ON runs(status);

-- ============================================
-- 知识库管理
-- ============================================

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('url', 'file', 'manual')),
    source_url VARCHAR(2000),
    file_path VARCHAR(500),
    file_hash VARCHAR(64),
    content TEXT,
    raw_html TEXT,
    scrape_method VARCHAR(20) DEFAULT 'trafilatura',
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    chunk_count INT DEFAULT 0,
    batch_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_documents_user ON documents(user_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_hash ON documents(file_hash);
CREATE INDEX idx_documents_batch ON documents(batch_id);

-- 批量导入记录
CREATE TABLE import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    total_count INT NOT NULL,
    completed_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    skipped_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'partial')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_import_batches_user ON import_batches(user_id);

-- 知识块
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(1024),
    metadata JSONB DEFAULT '{}',
    chunk_index INT NOT NULL,
    token_count INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- ============================================
-- 测验系统
-- ============================================

CREATE TABLE quizzes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    thread_id UUID REFERENCES threads(id),
    scope VARCHAR(20) NOT NULL CHECK (scope IN ('daily', 'topic', 'time_range', 'wrong_review')),
    topic VARCHAR(500),
    time_range JSONB,
    difficulty VARCHAR(20) DEFAULT 'medium',
    questions JSONB NOT NULL,
    answers JSONB,
    score DECIMAL(5,2),
    total_questions INT NOT NULL,
    correct_count INT DEFAULT 0,
    time_spent_seconds INT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_quizzes_user ON quizzes(user_id);

-- 错题本
CREATE TABLE wrong_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    quiz_id UUID REFERENCES quizzes(id),
    question JSONB NOT NULL,
    user_answer TEXT,
    correct_answer TEXT,
    explanation TEXT,
    chunk_ids UUID[],
    error_type VARCHAR(50),
    review_count INT DEFAULT 0,
    mastered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_reviewed_at TIMESTAMPTZ
);

CREATE INDEX idx_wrong_questions_user ON wrong_questions(user_id);
CREATE INDEX idx_wrong_questions_mastered ON wrong_questions(mastered);

-- ============================================
-- 复习调度
-- ============================================

CREATE TABLE review_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    chunk_id UUID REFERENCES chunks(id),
    topic VARCHAR(500),
    answer TEXT,
    source VARCHAR(50) DEFAULT 'feynman',
    reason VARCHAR(50),
    next_review TIMESTAMPTZ NOT NULL,
    last_reviewed_at TIMESTAMPTZ,
    interval_days DECIMAL(10,2) DEFAULT 1.0,
    ease_factor DECIMAL(5,2) DEFAULT 2.5,
    review_count INT DEFAULT 0,
    mastery_score DECIMAL(5,2) DEFAULT 0.0,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'mastered')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_review_schedule_user ON review_schedule(user_id);
CREATE INDEX idx_review_schedule_next ON review_schedule(next_review);
CREATE INDEX idx_review_schedule_status ON review_schedule(status);

-- 复习日志
CREATE TABLE review_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    schedule_id UUID NOT NULL REFERENCES review_schedule(id),
    chunk_id UUID NOT NULL REFERENCES chunks(id),
    result VARCHAR(20) NOT NULL CHECK (result IN ('easy', 'good', 'hard', 'forgot')),
    old_interval DECIMAL(10,2),
    new_interval DECIMAL(10,2),
    ease_factor_change DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 进度追踪
-- ============================================

CREATE TABLE mastery_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    chunk_id UUID NOT NULL REFERENCES chunks(id),
    topic VARCHAR(500),
    mastery_score DECIMAL(5,2) DEFAULT 0.0,
    quiz_accuracy DECIMAL(5,2) DEFAULT 0.0,
    feynman_score DECIMAL(5,2) DEFAULT 0.0,
    review_count INT DEFAULT 0,
    last_quiz_at TIMESTAMPTZ,
    last_feynman_at TIMESTAMPTZ,
    last_review_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, chunk_id)
);

CREATE INDEX idx_mastery_user ON mastery_records(user_id);

-- 学习统计
CREATE TABLE learning_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    date DATE NOT NULL,
    total_time_seconds INT DEFAULT 0,
    documents_read INT DEFAULT 0,
    quizzes_taken INT DEFAULT 0,
    quiz_avg_score DECIMAL(5,2),
    feynman_sessions INT DEFAULT 0,
    feynman_avg_score DECIMAL(5,2),
    reviews_completed INT DEFAULT 0,
    new_concepts_learned INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- ============================================
-- LLM 日志
-- ============================================

CREATE TABLE llm_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    thread_id UUID REFERENCES threads(id),
    run_id UUID REFERENCES runs(id),
    agent_type VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    input_tokens INT,
    output_tokens INT,
    latency_ms INT,
    cost_usd DECIMAL(10,6),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 插入默认测试用户
-- ============================================

INSERT INTO users (email, username, hashed_password) VALUES
('demo@aitutor.com', 'Demo User', '$2b$12$LJ3m4ys3Lz0QfQJxQZxQZeKJxQZxQZeKJxQZxQZeKJxQZxQZeKJx');
