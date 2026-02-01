-- Dynamic Weight Distribution System (MVP)
-- PostgreSQL schema (idempotent when applied to a fresh DB).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'node_type') THEN
        CREATE TYPE node_type AS ENUM ('task', 'idea', 'discussion');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_level') THEN
        CREATE TYPE user_level AS ENUM ('novice', 'skilled', 'expert', 'master');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'revenue_source') THEN
        CREATE TYPE revenue_source AS ENUM ('direct', 'propagation');
    END IF;
END
$$;

-- Users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL UNIQUE,
    reputation_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    contribution_score INT NOT NULL DEFAULT 0,
    level user_level NOT NULL DEFAULT 'novice',
    violation_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Nodes (knowledge graph)
CREATE TABLE IF NOT EXISTS nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    type node_type NOT NULL DEFAULT 'task',
    creator_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    api_call_count INT NOT NULL DEFAULT 0,
    citation_count INT NOT NULL DEFAULT 0,
    -- Optional provenance fields for CSV import / external systems
    source TEXT NOT NULL DEFAULT 'manual',
    source_ref TEXT NULL
);

-- Citations (directed edges: from_node references to_node)
CREATE TABLE IF NOT EXISTS citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    to_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    weight NUMERIC(5,4) NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT citations_no_self CHECK (from_node_id <> to_node_id),
    CONSTRAINT citations_unique_edge UNIQUE (from_node_id, to_node_id)
);

-- Revenue distribution records
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

-- Indexes
CREATE INDEX IF NOT EXISTS idx_nodes_creator_id ON nodes (creator_id);
CREATE INDEX IF NOT EXISTS idx_nodes_source_ref ON nodes (source, source_ref);

CREATE INDEX IF NOT EXISTS idx_citations_from_node_id ON citations (from_node_id);
CREATE INDEX IF NOT EXISTS idx_citations_to_node_id ON citations (to_node_id);

CREATE INDEX IF NOT EXISTS idx_revenue_distributions_task_id ON revenue_distributions (task_id);
CREATE INDEX IF NOT EXISTS idx_revenue_distributions_node_id ON revenue_distributions (node_id);
CREATE INDEX IF NOT EXISTS idx_revenue_distributions_user_id ON revenue_distributions (user_id);

