-- One-time cleanup script for x_posts:
-- 1. Deduplicate historical x_<sid> vs <sid> pairs and normalize remaining bare numeric X IDs to x_<sid>.
-- 2. Deduplicate legacy rows sharing the same canonical link.
-- 3. Clear false is_real_api = TRUE flags (and zero synthetic metrics) on pre-fix RSS/Facebook rows.

BEGIN;

-- 1a. Keep the higher-engagement metrics on x_<sid> when both x_<sid> and bare <sid> exist.
UPDATE x_posts AS target
SET likes = GREATEST(COALESCE(target.likes, 0), COALESCE(dup.likes, 0)),
    retweets = GREATEST(COALESCE(target.retweets, 0), COALESCE(dup.retweets, 0)),
    replies = GREATEST(COALESCE(target.replies, 0), COALESCE(dup.replies, 0)),
    impressions = GREATEST(COALESCE(target.impressions, 0), COALESCE(dup.impressions, 0)),
    engagement_score = GREATEST(COALESCE(target.engagement_score, 0), COALESCE(dup.engagement_score, 0)),
    is_real_api = (COALESCE(target.is_real_api, FALSE) OR COALESCE(dup.is_real_api, FALSE)),
    updated_at = NOW()
FROM x_posts AS dup
WHERE dup.id ~ '^\d{15,22}$'
  AND target.id = 'x_' || dup.id;

-- 1b. Delete bare numeric <sid> rows that now have a canonical x_<sid> twin.
DELETE FROM x_posts AS dup
USING x_posts AS canon
WHERE dup.id ~ '^\d{15,22}$'
  AND canon.id = 'x_' || dup.id;

-- 1c. Canonicalize any remaining bare numeric X status IDs to x_<sid>.
UPDATE x_posts
SET id = 'x_' || id,
    updated_at = NOW()
WHERE id ~ '^\d{15,22}$'
  AND (platform = 'x' OR platform IS NULL)
  AND NOT EXISTS (
      SELECT 1 FROM x_posts AS existing WHERE existing.id = 'x_' || x_posts.id
  );

-- 2. Deduplicate legacy rows sharing the same non-empty normalized link (strip query params & trailing slash).
WITH ranked_links AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(REGEXP_REPLACE(REGEXP_REPLACE(COALESCE(link, ''), '\?.*$', ''), '/+$', ''))
            ORDER BY
                COALESCE(is_real_api, FALSE) DESC,
                (CASE WHEN id ~ '^(x|fb)_\d+$' THEN 1 ELSE 0 END) DESC,
                COALESCE(engagement_score, 0) DESC,
                updated_at DESC NULLS LAST,
                id ASC
        ) AS rn
    FROM x_posts
    WHERE COALESCE(link, '') <> ''
)
DELETE FROM x_posts
WHERE id IN (SELECT id FROM ranked_links WHERE rn > 1);

-- 3. Clear false is_real_api = TRUE flags on pre-fix Facebook / RSS / hashed rows.
UPDATE x_posts
SET is_real_api = FALSE,
    likes = 0,
    retweets = 0,
    replies = 0,
    impressions = 0,
    engagement_score = 0,
    updated_at = NOW()
WHERE COALESCE(is_real_api, FALSE) = TRUE
  AND (
      platform = 'facebook'
      OR COALESCE(link, '') ILIKE '%facebook.com%'
      OR COALESCE(link, '') ILIKE '%news.google.com%'
      OR COALESCE(link, '') ILIKE '%bing.com%'
      OR (
          id ~ '^(x|fb)_[0-9a-f]{16,24}$'
          AND COALESCE(likes, 0) = 0
          AND COALESCE(retweets, 0) = 0
          AND COALESCE(replies, 0) = 0
      )
  );

COMMIT;
