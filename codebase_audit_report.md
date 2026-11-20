# Comprehensive Codebase Audit Report: Nepal Media & Intelligence Monitor
**Date:** November 20, 2026  
**Repository:** `nepal-social-monitor`  
**Scope:** Static, Architectural, Concurrency, and Dependency Audit  
**Target Modules:** `app.py`, `nepal_config.py`, `nepal_fetcher.py`, `nepal_news_scheduler.py`, `nepal_news_store.py`, `nepal_summarizer.py`, `nepal_x_scanner.py`, `executive_docx_exporter.py`, `apple_theme.py`, `whatsapp_greenapi.py`, `tests/`

---

## 1. Executive Summary

A comprehensive, read-only static and architectural audit was performed across all 11,000+ lines of Python code supporting the Nepal Media & Intelligence Monitor. The system demonstrates impressive functional depth: a multi-portal concurrent scraper across 33 Nepali media outlets and 34 Indian press feeds, resilient zero-cost Google Translate failover to local CTranslate2 NLLB-200 INT8 inference, pure-Python LexRank summarization, Supabase PostgreSQL keyset pagination via psycopg3 connection pooling, and an Apple HIG-styled Streamlit interface. All 24 unit, regression, and E2E AppTest suites pass cleanly (`Ran 24 tests in 18.65s, OK`).

However, rapid feature iterations and parallel deployment optimizations (split Streamlit Cloud frontend vs. GitHub Actions backend) have created architectural debt, code duplication, concurrency hazards, and a critical authentication vulnerability.

### System Health Ratings

| Dimension | Rating | Summary |
| :--- | :---: | :--- |
| **Functional Capabilities** | **A** | Reliable multi-stream ingestion, fallback translation, high-fidelity UI |
| **Test Coverage & Regressions** | **A-** | Comprehensive 24-test suite validating critical paths, timeouts, and state |
| **Architecture & Modularity** | **C+** | Heavy cross-module coupling, monolithic modules (`nepal_fetcher.py` >3400 lines) |
| **Code Duplication** | **C** | Multiple implementations of Devanagari checks, timezone constants, and classifications |
| **Concurrency & Thread Safety** | **C-** | Unsynchronized, unbounded in-memory caches mutated across worker threads |
| **Security & Auth Posture** | **D+** | Plaintext URL query bypass in `app.py` and hardcoded default password |

### Top 3 Highest-Impact Risks

> [!CAUTION]
> ### 1. URL Query Parameter Authentication Bypass (`SEC-01`)
> In `app.py:112-114`, the logic checks:
> ```python
> query_auth = st.query_params.get("auth", "")
> if query_auth == "true" or query_key == APP_PASSWORD:
>     st.session_state["authenticated"] = True
> ```
> Any unauthenticated user who visits `/?auth=true` in their web browser completely bypasses authentication without entering a password. They receive full administrative privileges: browsing raw intelligence feeds, executing manual syncs, editing summaries, reading WhatsApp dispatch queues, and viewing system health metrics. Coupled with the hardcoded default password `"PIC@55"` (`app.py:104`), the web application is essentially unprotected in default configurations.

> [!WARNING]
> ### 2. Unsynchronized Global Caches & Unbounded Memory Leaks (`CONC-01`, `CONC-02`)
> In `nepal_fetcher.py:71-77`, `FULL_ARTICLE_TEXT_CACHE`, `ARTICLE_DATE_CACHE`, `TCO_REDIRECT_CACHE`, and `GNEWS_URL_CACHE` are plain Python dictionaries (`{}`) initialized at the module level.
> 1. **Thread Safety Violation:** Multiple threads in `concurrent.futures.ThreadPoolExecutor` (inside `nepal_news_scheduler.py` and `nepal_fetcher.py`) concurrently read and write to these dictionaries without any lock protection (`threading.Lock`), creating race conditions.
> 2. **Memory Leak:** These dictionaries have neither a `maxsize` ceiling nor a TTL eviction policy. Over hours of continuous daemon operation or active Streamlit user sessions, thousands of multi-kilobyte article bodies accumulate in RAM. On Streamlit Community Cloud (strict 690 MB–2.7 GB container ceiling), this unbounded cache accumulation will eventually trigger an Out-Of-Memory (OOM) restart.

> [!IMPORTANT]
> ### 3. Silent Pipeline Failures Masked by 50+ Bare `except Exception: pass` Blocks (`ERR-01`)
> Over 50 try/except blocks across `nepal_fetcher.py`, `nepal_news_store.py`, and `app.py` catch generic `Exception` and execute `pass` or return empty lists without writing to `logger.error` or `logger.warning`. For instance, in `nepal_fetcher.py:262, 1042` and `nepal_news_store.py:270, 2426`, database query failures and portal fetch aborts fail silently. An administrator viewing the UI or CI log will see zero error traces while articles are quietly dropped or feeds stop updating.

---

## 2. Prioritized Findings Table

| ID | Severity | Category | Location | Issue Description | Recommended Fix |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **SEC-01** | **CRITICAL** | Security | `app.py:112-114` | `query_auth == "true"` allows instant authentication bypass via URL parameter `/?auth=true`. | Remove `query_auth == "true"` check. Authenticate only via valid `query_key == APP_PASSWORD` (or better, temporary HMAC tokens) and standard password input. |
| **SEC-02** | **HIGH** | Security | `app.py:104` | Hardcoded fallback password `"PIC@55"` in `os.getenv("APP_PASSWORD", "PIC@55")` committed to Git. | Fail closed: require `APP_PASSWORD` to be explicitly set in the environment/secrets. If unset, log a critical configuration error and disable administrative actions. |
| **SEC-03** | **MEDIUM** | Security | `.github/workflows/news_monitor.yml:50-53` | Revoked Twitter secrets (`TWITTER_BEARER_TOKEN`, `TWITTER_CONSUMER_KEY`, etc.) passed to runner environment. | Remove dead Twitter environment variable bindings from the workflow; the scanner uses public syndication and Bing RSS feeds. |
| **SEC-04** | **MEDIUM** | Security | `nepal_fetcher.py:57`, `nepal_summarizer.py:349`, `nepal_x_scanner.py:42` | Global `ssl._create_unverified_context()` disables SSL certificate validation for all outbound HTTP requests. | Use Python's `certifi` bundle for certificate verification. Fall back to unverified context only on explicit, isolated `SSLCertVerificationError` for broken local media servers. |
| **CONC-01** | **HIGH** | Concurrency | `nepal_fetcher.py:71-73` | `FULL_ARTICLE_TEXT_CACHE` and `ARTICLE_DATE_CACHE` are plain dicts mutated concurrently by worker threads without a lock. | Protect cache mutations with a `threading.Lock` or wrap them in a thread-safe `diskcache.Cache` / `collections.OrderedDict` with synchronization. |
| **CONC-02** | **HIGH** | Memory | `nepal_fetcher.py:71-77` | In-memory scraping caches have no size limits or TTL expiration, causing unbounded RAM growth in long-running processes. | Enforce a bounded cache size (e.g., `lru_cache` or bounded dict with max 500 items) or delegate to `diskcache` with automatic eviction. |
| **CONC-03** | **MEDIUM** | Resource | `nepal_summarizer.py:126-136` | `TranslationLRUCache` triggers SQLite `ResourceWarning: unclosed database in <sqlite3.Connection>` during testing and process restarts. | Implement proper `close()` / `__del__()` or context manager handling for SQLite database connections in the diskcache wrapper. |
| **DUP-01** | **HIGH** | Duplication | `nepal_config.py:122` vs `nepal_summarizer.py:565` | Divergent `_has_devanagari()` implementations (regex vs. ord loop); imported inconsistently across 6 modules. | Keep single high-performance implementation in `nepal_config.py`. In `nepal_summarizer.py`, re-export `from nepal_config import _has_devanagari` to prevent breakage. |
| **DUP-02** | **HIGH** | Duplication | `nepal_fetcher.py:329-800` vs `executive_docx_exporter.py:123-200` | Duplicated and divergent editorial category classification engines (9 categories in fetcher vs. 7 in docx exporter). | Centralize classification keyword sets and logic into a shared helper (`nepal_classifier.py` or `classify_article_editorial`), mapping 9 categories to docx sections. |
| **DUP-03** | **MEDIUM** | Duplication | `nepal_config.py:30`, `nepal_news_scheduler.py:42`, `nepal_news_store.py:34`, `nepal_x_scanner.py:35`, `executive_docx_exporter.py:30` | `NEPAL_TZ = zoneinfo.ZoneInfo("Asia/Kathmandu")` instantiated redundantly in 5 separate modules. | Define `NEPAL_TZ` solely in `nepal_config.py` and import it into all downstream modules. |
| **DUP-04** | **MEDIUM** | Duplication | `nepal_fetcher.py:58-63`, `nepal_summarizer.py:590-592`, `nepal_x_scanner.py:39-41`, `nepal_news_store.py:435-452` | Duplicated HTTP User-Agent dictionaries, requests headers, and thread-local session creation blocks. | Centralize default headers and a resilient thread-local `requests.Session` factory in `nepal_config.py`. |
| **DUP-05** | **MEDIUM** | Duplication | `nepal_x_scanner.py:211-226` vs `nepal_config.py:126-167` vs `app.py:962-968` | Relative time calculation and timestamp string formatting re-implemented in multiple locations. | Consolidate timestamp formatting functions into `nepal_config.py:format_nepal_relative_time()`. |
| **DUP-06** | **MEDIUM** | Duplication | `executive_docx_exporter.py:54-79` vs `nepal_config.py:46-118` | `SOURCE_NAME_MAP` in docx exporter duplicates portal name canonicalization defined in `PORTAL_REGISTRY`. | Derive source display names directly from `PORTAL_REGISTRY` metadata. |
| **ERR-01** | **HIGH** | Reliability | `nepal_fetcher.py:88, 111, 262`, `nepal_news_store.py:270, 556`, `app.py:79, 410` | 50+ instances of bare `except Exception:` with `pass` or silent empty returns hiding genuine system errors. | Replace bare `except Exception:` with specific exception types (`requests.RequestException`, `psycopg.Error`), and log with `logger.debug` or `logger.warning`. |
| **ERR-02** | **MEDIUM** | Reliability | `nepal_news_store.py:2426` | In `get_articles_by_date_range()`, database connection errors are caught generically and return `[]`, masquerading DB outages as empty feeds. | Distinguish empty query results from connection/pool exceptions; re-raise or set an explicit error state in `st.session_state` so users know the DB is unreachable. |
| **DEP-01** | **HIGH** | Dependencies | `requirements-backend.txt:18` | `lingua-language-detector>=2.0.2` is installed on CI runner but never imported or used by `nepal_summarizer.py`. | Remove `lingua-language-detector` from `requirements-backend.txt`. `detect_text_language()` uses native regex heuristics with zero overhead. |
| **DEP-02** | **MEDIUM** | Dependencies | `requirements-backend.txt:3` | `transformers>=4.28.0` is specified as a fallback but adds ~1.5 GB PyTorch overhead on CI runners. | Remove `transformers` from `requirements-backend.txt`; `ctranslate2` handles NLLB translation natively in C++ INT8 without PyTorch. |
| **DEP-03** | **MEDIUM** | Deprecation | `nepal_summarizer.py:616` | `wait_exponential_jitter(initial=0.5, max=3.0)` raises `DeprecationWarning: The 'initial' parameter is deprecated, use 'multiplier' instead`. | Update `wait_exponential_jitter` call to use `multiplier=0.5` instead of `initial=0.5`. |
| **DEP-04** | **MEDIUM** | Deprecation | `app.py` (multiple calls) | Calls to `st.components.v1.html` emit deprecation warnings for removal after June 2026. | Plan migration from `st.components.v1.html` to `st.iframe` or Streamlit custom components where appropriate. |
| **DEP-05** | **LOW** | Consistency | `requirements.txt` vs `requirements-backend.txt` | `requirements.txt` uses rigid pinned versions (`==`) while `requirements-backend.txt` uses `>=`. | Standardize backend dependencies to compatible `>=` ranges or lockfile versions to ensure predictable CI builds. |
| **SCH-01** | **MEDIUM** | Schema | `app.py:720-750`, `nepal_x_scanner.py:780` | Inconsistent field names between news articles (`headline_english`, `raw_title`) and X posts (`tweet_text_en`, `clean_text`). | Create a unified `FeedItem` adapter or standard dictionary view so card renderers do not need 5 nested `.get()` fallbacks. |
| **SCH-02** | **LOW** | Config | `whatsapp_greenapi.py:53-61` | WhatsApp group IDs (`12036302...-group@g.us`) are hardcoded directly in Python source. | Move WhatsApp recipient group IDs to environment variables (`WHATSAPP_PRIMARY_GROUP_ID`, etc.). |

---

## 3. Duplication Map & Consolidation Targets

```
┌────────────────────────────────────────────────────────────────────────┐
│                          DUPLICATION CLUSTERS                          │
└────────────────────────────────────────────────────────────────────────┘

1. Devanagari Unicode Detection
   ├── nepal_config.py:122 (regex [\u0900-\u097F])
   └── nepal_summarizer.py:565 (ord loop 0x0900..0x097F)
   ──► TARGET: nepal_config.py:_has_devanagari (Re-export in nepal_summarizer)

2. Timezone Instantiation (NEPAL_TZ)
   ├── nepal_config.py:30
   ├── nepal_news_scheduler.py:42
   ├── nepal_news_store.py:34
   ├── nepal_x_scanner.py:35
   └── executive_docx_exporter.py:30
   ──► TARGET: nepal_config.py:NEPAL_TZ (Import into all 5 modules)

3. Editorial Category Classification
   ├── nepal_fetcher.py:329-800+ (9 categories, extensive keyword lists)
   ├── executive_docx_exporter.py:123-200 (7 digest sections)
   └── nepal_x_scanner.py:121-208 (X post overrides + fetcher delegation)
   ──► TARGET: nepal_classifier.py (Shared keyword taxonomy & mapper)

4. HTTP Request Headers & Sessions
   ├── nepal_fetcher.py:58-63 (DEFAULT_HEADERS)
   ├── nepal_summarizer.py:590-592 (User-Agent header dict)
   ├── nepal_x_scanner.py:39-41 (DEFAULT_HEADERS)
   └── nepal_news_store.py:435-452 (Thread-local Session creation)
   ──► TARGET: nepal_config.py:get_requests_session(), DEFAULT_HEADERS

5. Relative & Display Time Formatting
   ├── nepal_config.py:126-167 (parse_to_nepal_time)
   ├── nepal_x_scanner.py:211-226 (format_relative_time)
   └── app.py:962-968 (_format_card_timestamp)
   ──► TARGET: nepal_config.py:format_nepal_relative_time()

6. Source Name Normalization
   ├── nepal_config.py:46-118 (PORTAL_REGISTRY)
   └── executive_docx_exporter.py:54-79 (SOURCE_NAME_MAP)
   ──► TARGET: nepal_config.py:get_source_display_name()
```

---

## 4. Phased Cleanup Plan (Preserving 24/24 Regression Tests)

The following 4-phase refactoring roadmap resolves high-impact security and stability risks while ensuring that all 24 automated regression tests in `tests/test_performance_and_regression.py` pass after each phase.

```mermaid
flowchart LR
    P1["Phase 1:<br/>Security & Quick Fixes"] --> P2["Phase 2:<br/>Constants & Deduplication"]
    P2 --> P3["Phase 3:<br/>Cache & Thread Safety"]
    P3 --> P4["Phase 4:<br/>Error Logging & Deps"]
    
    style P1 fill:#ffdddd,stroke:#cc0000,stroke-width:2px
    style P2 fill:#fff2cc,stroke:#d6b656,stroke-width:2px
    style P3 fill:#e1d5e7,stroke:#9673a6,stroke-width:2px
    style P4 fill:#d5e8d4,stroke:#82b366,stroke-width:2px
```

### Phase 1: Security Hardening & Zero-Risk Quick Wins
**Goal:** Close immediate security holes and fix active deprecation warnings without touching business logic.
1. **Fix `SEC-01` (`app.py`):** Remove `query_auth == "true"` check. Retain password validation and optional HMAC URL authentication.
2. **Fix `DEP-03` (`nepal_summarizer.py`):** Change `wait_exponential_jitter(initial=0.5, max=3.0)` to `wait_exponential_jitter(multiplier=0.5, max=3.0)`.
3. **Fix `SEC-03` (`news_monitor.yml`):** Delete revoked Twitter secrets (`TWITTER_BEARER_TOKEN`, `TWITTER_CONSUMER_KEY`, etc.) from GitHub Actions env map.
4. **Validation Gate:** Run `python tests/test_performance_and_regression.py -v`. Confirm 24/24 tests pass.

### Phase 2: Deduplication & Constants Consolidation
**Goal:** Establish single sources of truth for timezone, Devanagari detection, and HTTP headers without breaking external callers.
1. **Consolidate `NEPAL_TZ` (`DUP-03`):** Remove redundant definitions in `nepal_news_scheduler.py`, `nepal_news_store.py`, `nepal_x_scanner.py`, and `executive_docx_exporter.py`. Replace with `from nepal_config import NEPAL_TZ`.
2. **Consolidate `_has_devanagari` (`DUP-01`):** Verify `nepal_config.py:_has_devanagari` is optimal. In `nepal_summarizer.py`, import and re-export `_has_devanagari` from `nepal_config` so both internal and external modules remain 100% compatible.
3. **Consolidate HTTP Headers & Time Formatting (`DUP-04`, `DUP-05`):** Export `DEFAULT_HEADERS` and `format_nepal_relative_time` from `nepal_config.py`. Update `nepal_x_scanner.py` and `nepal_fetcher.py`.
4. **Validation Gate:** Run full test suite; verify `test_bs_calendar_intraday_timestamp_priority_and_scheduler_utc_normalization` and `test_timestamp_helpers_preserve_wallclock_and_microseconds`.

### Phase 3: Thread-Safe Caching & Memory Bounding
**Goal:** Eliminate race conditions and protect Streamlit Community Cloud from OOM crashes.
1. **Thread-Safe Scraping Caches (`CONC-01`, `CONC-02`):** In `nepal_fetcher.py`, replace plain dicts `FULL_ARTICLE_TEXT_CACHE` and `ARTICLE_DATE_CACHE` with a bounded LRU cache (e.g., `collections.OrderedDict` limited to 1,000 items with a `threading.Lock`, or `diskcache.Cache` with TTL).
2. **SQLite Connection Hygiene (`CONC-03`):** Add explicit cache closing on daemon teardown in `nepal_summarizer.py`.
3. **Validation Gate:** Run `test_concurrent_pipeline_isolation_and_no_overlap_lock` and `test_bounded_translation_lru_cache`.

### Phase 4: Error Handling Hygiene & Dead Dependency Pruning
**Goal:** Provide visibility into silent failures and trim CI runner dependencies.
1. **Trim Backend Dependencies (`DEP-01`, `DEP-02`):** Remove `lingua-language-detector` and `transformers` from `requirements-backend.txt`. Verify CI builds and runs cleanly.
2. **Selective Exception Logging (`ERR-01`, `ERR-02`):** Audit the top 20 most critical `except Exception: pass` sites in `nepal_fetcher.py` and `nepal_news_store.py`. Add `logger.warning` with contextual portal/URL metadata so degraded sources are surfaced.
3. **Validation Gate:** Run complete end-to-end regression suite (`24 tests`). Confirm 0 regressions and 0 deprecation warnings.
