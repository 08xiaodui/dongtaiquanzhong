-- Idempotent migration: indexes for core MVP tables

CREATE INDEX IF NOT EXISTS idx_nodes_creator_id ON nodes (creator_id);
CREATE INDEX IF NOT EXISTS idx_nodes_source_ref ON nodes (source, source_ref);

CREATE INDEX IF NOT EXISTS idx_citations_from_node_id ON citations (from_node_id);
CREATE INDEX IF NOT EXISTS idx_citations_to_node_id ON citations (to_node_id);

CREATE INDEX IF NOT EXISTS idx_revenue_distributions_task_id ON revenue_distributions (task_id);
CREATE INDEX IF NOT EXISTS idx_revenue_distributions_node_id ON revenue_distributions (node_id);
CREATE INDEX IF NOT EXISTS idx_revenue_distributions_user_id ON revenue_distributions (user_id);

