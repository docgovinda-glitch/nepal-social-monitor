-- 004_unified_social_media.sql
-- Idempotent schema extension for Unified Social Media Monitoring (Facebook & X/Twitter).
-- Consolidates Facebook and X into high-performance social posts and accounts tables.

-- 1. Add platform column to x_posts (default 'x', allows 'facebook' and 'x')
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'x_posts' AND column_name = 'platform'
    ) THEN
        ALTER TABLE x_posts ADD COLUMN platform TEXT DEFAULT 'x';
    END IF;
END $$;

-- 2. Add platform column to x_accounts
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'x_accounts' AND column_name = 'platform'
    ) THEN
        ALTER TABLE x_accounts ADD COLUMN platform TEXT DEFAULT 'x';
    END IF;
END $$;

-- 3. Composite cursor indexes on platform + published_dt
CREATE INDEX IF NOT EXISTS idx_x_posts_platform_cursor
    ON x_posts (platform, published_dt DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_x_posts_platform_cat_cursor
    ON x_posts (platform, structured_category, published_dt DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_x_posts_platform_eng_cursor
    ON x_posts (platform, engagement_score DESC, published_dt DESC, id DESC);

-- 4. Convenient views for unified queries
CREATE OR REPLACE VIEW social_posts AS 
    SELECT * FROM x_posts;

CREATE OR REPLACE VIEW social_accounts AS 
    SELECT * FROM x_accounts;
