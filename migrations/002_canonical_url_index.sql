-- 002_canonical_url_index.sql
-- Adds index on articles.canonical_url for fast normalized URL lookup and in-place RSS/HTML upgrade reconciliation.

CREATE INDEX IF NOT EXISTS idx_articles_canonical_url
    ON articles (canonical_url);
