-- Idempotent migration: core MVP tables

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL UNIQUE,
    reputation_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    contribution_score INT NOT NULL DEFAULT 0,
    level user_level NOT NULL DEFAULT 'novice',
    violation_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    type node_type NOT NULL DEFAULT 'task',
    creator_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    api_call_count INT NOT NULL DEFAULT 0,
    citation_count INT NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual',
    source_ref TEXT NULL
);

CREATE TABLE IF NOT EXISTS citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    to_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    weight NUMERIC(5,4) NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT citations_no_self CHECK (from_node_id <> to_node_id),
    CONSTRAINT citations_unique_edge UNIQUE (from_node_id, to_node_id)
);

-- Note: For MVP we treat `task_id` as a task node id (nodes.id).
CREATE TABLE IF NOT EXISTS revenue_distributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount NUMERIC(10,2) NOT NULL CHECK (amount >= 0),
    source revenue_source NOT NULL,
    propagation_level INT NOT NULL DEFAULT 0 CHECK (propagation_level >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

