-- 005_account_discovery_candidates.sql
-- Schema additions for automated pending_verification account discovery pipeline.

-- 1. Discovery & promotion tracking columns on x_accounts
ALTER TABLE x_accounts ADD COLUMN IF NOT EXISTS discovery_source TEXT;
ALTER TABLE x_accounts ADD COLUMN IF NOT EXISTS discovery_score DOUBLE PRECISION DEFAULT 0;
ALTER TABLE x_accounts ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE x_accounts ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_x_accounts_pending_discovered
    ON x_accounts (verification_status, discovered_at DESC)
    WHERE verification_status = 'pending_verification';

CREATE INDEX IF NOT EXISTS idx_x_accounts_promoted_at
    ON x_accounts (promoted_at DESC)
    WHERE promoted_at IS NOT NULL;

-- 2. Rolling-window discovery signals table (co-mentions, quotes, etc.)
CREATE TABLE IF NOT EXISTS x_account_discovery_signals (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL DEFAULT 'x',
    handle TEXT NOT NULL,
    candidate_name TEXT DEFAULT '',
    signal_type TEXT NOT NULL,
    source_handle TEXT NOT NULL DEFAULT '',
    post_id TEXT NOT NULL DEFAULT '',
    engagement INT DEFAULT 0,
    followers_count INT DEFAULT 0,
    is_blue_verified BOOLEAN DEFAULT FALSE,
    account_created_at TIMESTAMPTZ,
    nepal_relevant BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_x_discovery_signals_unique
    ON x_account_discovery_signals (platform, LOWER(handle), signal_type, LOWER(source_handle), post_id);

CREATE INDEX IF NOT EXISTS idx_x_discovery_signals_created_at
    ON x_account_discovery_signals (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_x_discovery_signals_handle_window
    ON x_account_discovery_signals (platform, LOWER(handle), signal_type, created_at DESC);
