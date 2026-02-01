-- Idempotent migration: required extension and enum types

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

