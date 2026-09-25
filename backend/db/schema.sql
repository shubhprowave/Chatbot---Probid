-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =====================================================
-- DOCUMENTS
-- =====================================================
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       VARCHAR(64) NOT NULL DEFAULT 'default',
    filename        TEXT NOT NULL,
    file_hash       VARCHAR(64) NOT NULL,
    mime_type       VARCHAR(128),
    size_bytes      BIGINT,
    title           TEXT,
    url             TEXT,
    source_type     VARCHAR(32),
    status          VARCHAR(32) DEFAULT 'active',
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, file_hash)
);
CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_status ON documents(status);

-- =====================================================
-- CHUNKS (with vector)
-- =====================================================
CREATE TABLE chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id       VARCHAR(64) NOT NULL DEFAULT 'default',
    chunk_index     INTEGER NOT NULL,
    text            TEXT NOT NULL,
    token_count     INTEGER,
    char_count      INTEGER,
    heading_path    TEXT,
    page_number     INTEGER,
    metadata        JSONB DEFAULT '{}'::jsonb,
    embedding       vector(1024),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_tenant ON chunks(tenant_id);

-- HNSW for dense vector search
CREATE INDEX idx_chunks_embedding_hnsw ON chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- BM25-style full-text
CREATE INDEX idx_chunks_text_fts ON chunks
USING GIN (to_tsvector('english', text));

-- Trigram for fuzzy/typo search
CREATE INDEX idx_chunks_text_trgm ON chunks
USING GIN (text gin_trgm_ops);

-- =====================================================
-- CONVERSATIONS
-- =====================================================
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       VARCHAR(64) NOT NULL DEFAULT 'default',
    session_id      VARCHAR(128) NOT NULL,
    user_id         VARCHAR(128),
    user_ip         INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_conversations_session ON conversations(session_id);
CREATE INDEX idx_conversations_tenant ON conversations(tenant_id);

-- =====================================================
-- MESSAGES
-- =====================================================
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(16) NOT NULL,
    content         TEXT NOT NULL,
    sources         JSONB,
    latency_ms      INTEGER,
    model           VARCHAR(64),
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_created ON messages(created_at DESC);

-- =====================================================
-- FEEDBACK
-- =====================================================
CREATE TABLE feedback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id      UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    rating          SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
    comment         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_feedback_message ON feedback(message_id);

-- =====================================================
-- UNANSWERED QUERIES
-- =====================================================
CREATE TABLE unanswered (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       VARCHAR(64) NOT NULL DEFAULT 'default',
    question        TEXT NOT NULL,
    top_score       REAL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_unanswered_tenant ON unanswered(tenant_id);


-- =====================================================
-- Add fields to messages for latency/cost tracking
-- =====================================================
ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS retrieval_ms INTEGER,
    ADD COLUMN IF NOT EXISTS rerank_ms INTEGER,
    ADD COLUMN IF NOT EXISTS generation_ms INTEGER,
    ADD COLUMN IF NOT EXISTS total_ms INTEGER,
    ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS kind VARCHAR(16),           -- SIMPLE | COMPLEX
    ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,6) DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_cache_hit ON messages(cache_hit);

-- =====================================================
-- EVALUATIONS (RAGAS & custom metrics)
-- =====================================================
CREATE TABLE IF NOT EXISTS eval_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(128) NOT NULL,
    dataset_name    VARCHAR(128),
    total_questions INTEGER,
    status          VARCHAR(32) DEFAULT 'running',    -- running, completed, failed
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    config          JSONB DEFAULT '{}'::jsonb,
    summary         JSONB DEFAULT '{}'::jsonb         -- avg scores per metric
);

CREATE TABLE IF NOT EXISTS eval_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id          UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    question        TEXT NOT NULL,
    ground_truth    TEXT,
    answer          TEXT,
    contexts        JSONB,
    faithfulness    REAL,
    answer_relevancy REAL,
    context_precision REAL,
    context_recall  REAL,
    answer_correctness REAL,
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_eval_results_run ON eval_results(run_id);

-- =====================================================
-- GOLDEN TEST SET (for evaluations)
-- =====================================================
CREATE TABLE IF NOT EXISTS golden_qa (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       VARCHAR(64) DEFAULT 'default',
    question        TEXT NOT NULL,
    ground_truth    TEXT NOT NULL,
    category        VARCHAR(64),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- SYSTEM METRICS SNAPSHOTS (for time-series charts)
-- =====================================================
CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    captured_at     TIMESTAMPTZ DEFAULT NOW(),
    active_users    INTEGER,
    messages_1h     INTEGER,
    avg_latency_ms  INTEGER,
    cache_hit_rate  REAL,
    error_count     INTEGER,
    chunk_count     INTEGER,
    doc_count       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics_snapshots(captured_at DESC);



CREATE INDEX IF NOT EXISTS idx_messages_role_created
    ON messages(role, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_created
    ON conversations(created_at DESC);


ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS model VARCHAR(64),
    ADD COLUMN IF NOT EXISTS tokens_in INTEGER,
    ADD COLUMN IF NOT EXISTS tokens_out INTEGER,
    ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10, 6) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS retrieval_ms INTEGER,
    ADD COLUMN IF NOT EXISTS rerank_ms INTEGER,
    ADD COLUMN IF NOT EXISTS generation_ms INTEGER,
    ADD COLUMN IF NOT EXISTS total_ms INTEGER,
    ADD COLUMN IF NOT EXISTS kind VARCHAR(16);

CREATE INDEX IF NOT EXISTS idx_messages_cache_hit ON messages(cache_hit);