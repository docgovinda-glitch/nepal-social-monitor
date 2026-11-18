-- 001_performance_indexes.sql
-- Idempotent performance migration for Nepal Media Monitor (Supabase PostgreSQL).
-- Formalizes runtime-created tables and adds composite cursor, filter, and trigram indexes.

-- 1. Formalize whatsapp_sent_log table in migration (removes runtime DDL from user read path)
CREATE TABLE IF NOT EXISTS whatsapp_sent_log (
    item_key TEXT PRIMARY KEY,
    group_id TEXT DEFAULT '',
    group_name TEXT DEFAULT 'Media Monitor',
    id_message TEXT DEFAULT '',
    item_link TEXT DEFAULT '',
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Drop duplicate published_dt index on articles (idx_articles_published_dt already exists)
DROP INDEX IF EXISTS idx_art_published;

-- 3. Composite filter + keyset cursor indexes on articles
CREATE INDEX IF NOT EXISTS idx_articles_source_cursor
    ON articles (source, published_dt DESC, canonical_id DESC);

CREATE INDEX IF NOT EXISTS idx_articles_lang_cursor
    ON articles (language, published_dt DESC, canonical_id DESC);

CREATE INDEX IF NOT EXISTS idx_articles_section_cursor
    ON articles (primary_section, published_dt DESC, canonical_id DESC);

-- 4. Composite sort + filter + keyset cursor indexes on x_posts
CREATE INDEX IF NOT EXISTS idx_x_posts_eng_cursor
    ON x_posts (engagement_score DESC, published_dt DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_x_posts_likes_cursor
    ON x_posts (likes DESC, published_dt DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_x_posts_rt_cursor
    ON x_posts (retweets DESC, published_dt DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_x_posts_type_cursor
    ON x_posts (author_type, published_dt DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_x_posts_cat_cursor
    ON x_posts (structured_category, published_dt DESC, id DESC);

-- 5. Borderline review partial index on indian_media_articles
CREATE INDEX IF NOT EXISTS idx_indian_borderline_score
    ON indian_media_articles (nepal_relevance_score, published_dt DESC)
    WHERE nepal_relevance_score >= 0.40;

-- 6. Trigram extension & GIN indexes for accelerated ILIKE search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_articles_search_trgm
    ON articles USING gin (
        (COALESCE(title, '') || ' ' || COALESCE(headline_english, '') || ' ' || COALESCE(summary, '') || ' ' || COALESCE(source, '') || ' ' || COALESCE(primary_section, '') || ' ' || COALESCE(language, '')) gin_trgm_ops
    );

CREATE INDEX IF NOT EXISTS idx_indian_search_trgm
    ON indian_media_articles USING gin (
        (COALESCE(title, '') || ' ' || COALESCE(headline_english, '') || ' ' || COALESCE(summary, '') || ' ' || COALESCE(source, '') || ' ' || COALESCE(primary_section, '') || ' ' || COALESCE(language, '')) gin_trgm_ops
    );

CREATE INDEX IF NOT EXISTS idx_x_posts_search_trgm
    ON x_posts USING gin (
        (COALESCE(text, '') || ' ' || COALESCE(author_name, '') || ' ' || COALESCE(handle, '') || ' ' || COALESCE(author_type, '') || ' ' || COALESCE(structured_category, '')) gin_trgm_ops
    );
