# Social Media Monitoring Engineering Runbook & Rulebook

This runbook documents the production architecture, mandatory guardrails, discovery rules, query contracts, and verification procedures for the Nepal Social Media Monitor (`X` and `Facebook`).

---

## 1. Account Tracking & Directory Rules

### Live Registry & 1:1 Sync
- **Database table**: `x_accounts` in Supabase PostgreSQL (unified for both `platform = 'x'` and `platform = 'facebook'`).
- **Curated baseline**: [`nepal_social_directory.py`](../nepal_social_directory.py) (`VERIFIED_NEPAL_SOCIAL_DIRECTORY`, `DIRECTORY_BY_PLATFORM_HANDLE`) holds **242** enabled curated accounts (**184** `x`, **58** `facebook`) across `CANONICAL_SOCIAL_CATEGORIES`.
- **Fallback directory**: [`nepal_verified_x_directory.py`](../nepal_verified_x_directory.py) (`VERIFIED_NEPAL_X_DIRECTORY`) is used **only** as a fallback when `x_accounts` has `< 50` X rows and `nepal_social_directory.py` is unavailable.
- **Platform isolation**: `get_monitored_x_accounts(enabled_only=True)` in [`nepal_x_scanner.py`](../nepal_x_scanner.py) filters strictly to `platform == 'x'`; `get_monitored_social_accounts(enabled_only=True)` in [`nepal_social_scanner.py`](../nepal_social_scanner.py) returns both `x` and `facebook` enabled accounts.

### Portal X Bridge / Boost Isolation
- Portal X handles (e.g., `@Annapurna_Post`, `@TheKathmanduPost`) are merged into X discovery via `_with_portal_x_accounts(accounts)` in [`nepal_x_scanner.py`](../nepal_x_scanner.py) and bridged into the `articles` table via `bridge_x_portals_to_articles(x_posts=all_posts)`.
- Portal X handles are excluded from `x_account_discovery_signals` candidate generation (`_get_portal_x_handle_set()`) and from monitored non-portal greeting stripping (`is_portal_bridge`).
- Social-only workspace views exclude `"Media Houses and News Outlets"` / `"Media Houses & News Outlets"` via `exclude_media_houses=True` so portal bridge/boost posts stay in the news/live portal streams.

---

## 2. Scheduled Ingestion & Polling Cadence

### Scheduler Loop ([`nepal_news_scheduler.py`](../nepal_news_scheduler.py))
- `_monitoring_daemon_loop()` runs `scan_popular_nepal_x_posts(force_refresh=True)` every **15 minutes** (`X_SCAN_INTERVAL_SECS = 15 * 60`).
- `_maybe_run_candidate_discovery()` runs `evaluate_and_enqueue_candidates()` every **60 minutes** (`CANDIDATE_EVAL_INTERVAL_SECS = 60 * 60`).

### X Profile + Bing RSS Discovery ([`nepal_x_scanner.py`](../nepal_x_scanner.py))
- `scan_popular_nepal_x_posts()` runs two discovery streams concurrently:
  1. `_discover_profile_tweet_candidates(discovery_accounts, 18.0)` across monitored X profiles + portal X accounts.
  2. `_discover_bing_tweet_candidates(12.0)` across `_BING_SEARCH_QUERIES`.
- **Refresh-skip logic**: `_load_existing_x_refresh_map(candidate_sids)` calls `get_x_post_refresh_map()`, which queries both `<sid>` and `x_<sid>` in `x_posts` and maps `x_<sid>` back to `<sid>`. `_select_tweet_ids_to_enrich()` sorts newest-first by Snowflake ID and enforces:
  - `refresh_window_hours = 48.0`: skips already-stored tweets older than 48 hours.
  - `min_recheck_secs = 300.0`: skips tweets refreshed within the last 5 minutes.
  - `active_topup_hours = 24.0`, `active_topup_cap = 60`, `max_enrich = 350`.

### Time-Slotted Circular Batching ([`nepal_social_scanner.py`](../nepal_social_scanner.py))
- `scan_popular_nepal_x_posts()` advances `scan_social_batch(batch_size=25)` (`ThreadPoolExecutor(max_workers=12)`) on every 15-minute cycle.
- When `_CURRENT_ACCOUNT_CURSOR is None` (e.g., after process restart), `scan_social_batch()` seeds from `(int(time.time() // 900) * batch_size) % len(accounts)` so restarts do not reset polling to index `0`.
- Facebook accounts are fetched via `_fetch_facebook_page_posts(acc, hours_cutoff=48)` and X accounts via `_fetch_x_account_posts(acc, hours_cutoff=48)`.

---

## 3. Mandatory Noise, Attribution & Deduplication Rules

### Facebook Attribution & RSS Guardrails ([`nepal_social_scanner.py`](../nepal_social_scanner.py))
- `_is_matching_facebook_entry(link, title, acc, source_title="")`:
  - **Google News RSS wrapper URLs** (`news.google.com/rss/articles/`): accepted **only** if `source_title` (when present) contains `"facebook"` or `"fb.com"` **and** either `handle` (boundary-matched, `len >= 3`) or `name` (`len >= 3`) appears in `title` or `source_title`. Unrelated pages/portals (e.g. `News24 Nepal`, `OnlineKhabar`) are rejected.
  - **Direct URLs**: must contain `facebook.com` or `fb.com` and either match `handle` on a URL boundary (`(?:^|[/?=&]){handle}(?:$|[/?&#])`) or match `name` (`len >= 3`) in `title`.
- **Bing News fallback**: strictly scoped to `b_query = f'site:facebook.com "{name}"'` (never un-scoped `"{name} Nepal"`).
- **Category unification**: `author_type = acc.get("type") or acc.get("category") or "Politicians"`.
- **Zero synthetic metrics**: all RSS-ingested Facebook and X fallback posts must set `is_real_api = False`, `likes = 0`, `retweets = 0`, `replies = 0`, `impressions = 0`, `engagement_score = 0`.
- **Deterministic IDs**: `_deterministic_social_post_id()` generates `fb_<sha256[:20]>` / `x_<sha256[:20]>` from `normalize_canonical_url(link)` (never Python `abs(hash(...))`).

### X Substance, Relevance & Greeting Filters ([`nepal_x_scanner.py`](../nepal_x_scanner.py))
- **Unmapped `"Public X Voice"` tweets**: `_is_substantive_unmapped_x_post(clean_text)` requires:
  1. `>= 25` chars and `>= 6` words after stripping URLs, `@mentions`, and `#hashtags`.
  2. Explicit Nepal/regional match via `_NEPAL_X_RELEVANCE_RE`.
  3. Substantive news/policy classification via `is_news_post("", clean_text)`.
- **Monitored non-portal accounts** (`is_protected_account and not is_portal_bridge`):
  - Drops bare-link/mention posts (`< 15` non-URL/mention/hashtag chars).
  - Drops short greeting-only posts (`len(clean_text) < 120` matching `_GREETING_PATTERNS` without any non-country keyword from `_NEWS_KEYWORDS_DEV` / `_NEWS_KEYWORDS_EN`, excluding `"नेपाल"` / `"nepal"`).
  - Portal bridge accounts (`is_portal_bridge`) bypass this filter.

### Canonical IDs & `save_x_posts()` Deduplication ([`nepal_news_store.py`](../nepal_news_store.py))
- `canonicalize_social_post_id(post_id, platform="x")` converts bare 15–22 digit X status IDs (`^\d{15,22}$`) to `x_<sid>`. `_enrich_tweet_by_id()` emits `x_<sid>` directly.
- `save_x_posts(posts, batch_size=250)`:
  1. Canonicalizes IDs and sorts `is_real_api=True` and numeric `^(?:x|fb)_\d+$` IDs ahead of RSS-hashed rows.
  2. Deduplicates in-batch and against recent 48-hour `x_posts` rows (`published_dt >= NOW() - INTERVAL '48 hours'`) by:
     - `id` (same-ID updates perform `ON CONFLICT (id) DO UPDATE`),
     - `normalize_canonical_url(link)` (skips different-ID duplicates), and
     - `(LOWER(raw_handle), LEFT(normalized_text, 120))` (`len >= 20`), **exempting** pairs where both IDs are numeric status IDs (`^(?:x|fb)_\d+$`) so legitimate back-to-back updates are preserved.

---

## 4. Automated `pending_verification` Discovery & Promotion Rules

### Schema ([`migrations/005_account_discovery_candidates.sql`](../migrations/005_account_discovery_candidates.sql))
- `x_accounts` columns: `discovery_source`, `discovery_score`, `discovered_at`, `promoted_at` (with partial indexes `idx_x_accounts_pending_discovered` and `idx_x_accounts_promoted_at`).
- `x_account_discovery_signals` table: unique index `idx_x_discovery_signals_unique` on `(platform, LOWER(handle), signal_type, LOWER(source_handle), post_id)` plus rolling-window indexes `idx_x_discovery_signals_created_at` and `idx_x_discovery_signals_handle_window`.

### Signal Extraction & Candidate Evaluation
- **Extraction**: `_enrich_tweet_by_id()` extracts `quoted_tweet.user` and `entities.user_mentions` for monitored accounts (`acc is not None`), excluding existing monitored/portal handles, and `scan_popular_nepal_x_posts()` batch-inserts via `record_discovery_signals()`.
- **Evaluation (`evaluate_and_enqueue_candidates(max_pending=50, ttl_days=30)`)**:
  1. **14-day co-mentions**: `signal_type = 'co_mention'`, `created_at >= NOW() - INTERVAL '14 days'`, `COUNT(DISTINCT LOWER(source_handle)) >= 3`.
  2. **7-day Bing RSS high-signal handles**: `author_type = 'Public X Voice'`, `published_dt >= NOW() - INTERVAL '7 days'`, `COUNT(*) >= 3 AND MAX(COALESCE(engagement_score, 0)) >= 50`.
  3. **48-hour topic spikes**: `author_type = 'Public X Voice'`, `published_dt >= NOW() - INTERVAL '48 hours'`, `COUNT(*) FILTER (WHERE COALESCE(engagement_score, 0) >= 100) >= 2`.
- **Safety Gates**:
  - `is_candidate_handle_allowed()`: rejects handles `< 3` chars, `_CANDIDATE_DENYLIST_HANDLES` (e.g. `grok`, `x`, `support`, `youtube`, `facebook`), and `_CANDIDATE_SPAM_PATTERN` (`bot`, `promo`, `giveaway`, `crypto`, `airdrop`, `casino`, `betting`, `nsfw`, `porn`, `followback`).
  - `_is_candidate_credible()`: requires `nepal_relevant_ratio >= 0.5`; if `followers_count > 0`, requires `followers_count >= 2000` or `(is_blue_verified and account_age >= 180 days)`; if `account_created_at` is known without follower count, requires `account_age >= 180 days` or `is_blue_verified`.
  - **Queue & TTL bounds**: deletes `pending_verification` (`enabled = 0`) rows older than **30 days** (`ttl_days=30`) and `x_account_discovery_signals` older than 30 days; caps total `pending_verification` rows at **50** (`max_pending=50`).
- **Promotion Cap (`promote_pending_x_account(handle, platform=None, max_weekly_promotions=10)`)**:
  - Enforces `<= 10` promotions (`promoted_at >= NOW() - INTERVAL '7 days'`) before updating `verification_status = 'verified'`, `enabled = 1`, `promoted_at = NOW()`.

---

## 5. Feed Query, Keyset Pagination & UI Rules

- **`exclude_media_houses=True`**: enforced consistently on social-only feeds in `_build_workspace_page_sql(workspace="x")`, `_build_filtered_count_sql_parts(workspace="x"|"live")`, `get_stored_live_feed_page(stream_filter="X (Twitter) Only"|"Verified X Voices Only")`, and `app.py:get_active_x_posts()`.
- **Real-API Engagement Sorting & Keyset Cursor**:
  - `get_stored_x_posts()` and `_build_workspace_page_sql()` sort `Most engagement`, `Most liked`, and `Most reposted` using:
    `CASE WHEN COALESCE(is_real_api, FALSE) THEN COALESCE(<metric>, 0) ELSE -1 END DESC, published_dt DESC, id DESC`
  - Keyset seek clause: `(<metric_expr>, published_dt, id) < (<cursor_metric>, '<c_dt_utc>', <cursor_id>)`.
  - `_extract_next_cursor("x", rows, sort_mode)` in [`app.py`](../app.py) emits `-1` for `is_real_api=False` / `None` rows so multi-page pagination stays aligned with SQL ordering.
- **UI Metrics Rendering**: `_render_x_metrics_html(p)` in [`app.py`](../app.py) renders `RSS / Metrics N/A` when `not p.get("is_real_api", True)` and `likes == retweets == replies == 0`.

---

## 6. Verification & Maintenance Appendix

### Pre-Deploy Compile & Unit/Regression Test Command
```bash
.venv/bin/python -m py_compile \
  nepal_social_scanner.py nepal_x_scanner.py nepal_news_store.py nepal_news_scheduler.py app.py \
  tests/test_social_media_unification.py && \
.venv/bin/python -m unittest \
  tests.test_social_media_unification \
  tests.test_refactor_units \
  tests.test_media_logos \
  tests.test_performance_and_regression.AppTestEndToEndRegressionTests.test_annapurna_post_x_bridge_card_and_reader_parity \
  tests.test_performance_and_regression.AppTestEndToEndRegressionTests.test_dual_feed_x_boost_filtering_and_inplace_url_reconciliation \
  tests.test_performance_and_regression.AppTestEndToEndRegressionTests.test_operational_polish_stale_detector_staggering_and_x_bridge_guard -v
```

### 4-Metric `x_posts` SQL Health Check
One-time cleanup script: [`migrations/cleanup_x_posts_duplicates.sql`](../migrations/cleanup_x_posts_duplicates.sql). Run this verification query to confirm all 4 counts are `0`:
```sql
WITH dup_links AS (
    SELECT COUNT(*) AS cnt
    FROM (
        SELECT ROW_NUMBER() OVER (
            PARTITION BY LOWER(REGEXP_REPLACE(REGEXP_REPLACE(COALESCE(link, ''), '\?.*$', ''), '/+$', ''))
            ORDER BY id
        ) AS rn
        FROM x_posts
        WHERE COALESCE(link, '') <> ''
    ) t
    WHERE rn > 1
)
SELECT
    (SELECT COUNT(*) FROM x_posts WHERE id ~ '^\d{15,22}$' AND (platform = 'x' OR platform IS NULL)) AS remaining_bare_x_ids,
    (SELECT COUNT(*) FROM x_posts dup JOIN x_posts canon ON canon.id = 'x_' || dup.id WHERE dup.id ~ '^\d{15,22}$') AS remaining_x_sid_pairs,
    (SELECT cnt FROM dup_links) AS remaining_dup_links,
    (SELECT COUNT(*) FROM x_posts
     WHERE COALESCE(is_real_api, FALSE) = TRUE
       AND (
           platform = 'facebook'
           OR COALESCE(link, '') ILIKE '%facebook.com%'
           OR COALESCE(link, '') ILIKE '%news.google.com%'
           OR COALESCE(link, '') ILIKE '%bing.com%'
           OR (id ~ '^(x|fb)_[0-9a-f]{16,24}$' AND COALESCE(likes, 0) = 0 AND COALESCE(retweets, 0) = 0 AND COALESCE(replies, 0) = 0)
       )
    ) AS remaining_false_real_api;
```

### Live Smoke-Test Snippet
```bash
.venv/bin/python -c "
from collections import Counter
import nepal_news_store as st, app as nepal_app
posts = st.get_stored_x_posts(limit=200, exclude_media_houses=True)
print('total:', len(posts), 'platforms:', Counter(p.get('platform') for p in posts),
      'real_api:', Counter(bool(p.get('is_real_api', True)) for p in posts),
      'rss_na:', sum(1 for p in posts if 'RSS / Metrics N/A' in nepal_app._render_x_metrics_html(p)))
print('discovery_eval:', st.evaluate_and_enqueue_candidates())
"
```
