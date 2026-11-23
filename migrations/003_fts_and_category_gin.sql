-- 003_fts_and_category_gin.sql
-- Adds Full-Text Search (tsvector) and Category Optimization for Nepal Media Monitor

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Full-text search tsvector GIN indexes for fast natural language matching
CREATE INDEX IF NOT EXISTS idx_articles_fts_gin
    ON articles USING gin (
        to_tsvector('simple', COALESCE(title, '') || ' ' || COALESCE(headline_english, '') || ' ' || COALESCE(summary, ''))
    );

CREATE INDEX IF NOT EXISTS idx_indian_fts_gin
    ON indian_media_articles USING gin (
        to_tsvector('simple', COALESCE(title, '') || ' ' || COALESCE(headline_english, '') || ' ' || COALESCE(summary, ''))
    );

CREATE INDEX IF NOT EXISTS idx_x_posts_fts_gin
    ON x_posts USING gin (
        to_tsvector('simple', COALESCE(text, '') || ' ' || COALESCE(author_name, '') || ' ' || COALESCE(handle, ''))
    );

-- 2. Fast category lookup and section indexing
CREATE INDEX IF NOT EXISTS idx_articles_sections_trgm
    ON articles USING gin (COALESCE(sections, '') gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_indian_sections_trgm
    ON indian_media_articles USING gin (COALESCE(sections, '') gin_trgm_ops);
