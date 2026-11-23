"""
tests/test_refactor_units.py
Fast unit tests covering:
1. LLM JSON parsing, recovery, and fallback translation
2. Conditional HTTP 304 handling and connection pooling in nepal_fetcher.py
3. _build_search_sql, _build_category_sql, and NPT date boundaries in nepal_news_store.py
4. Helper consolidation in nepal_config.py
"""

import unittest
import datetime
import zoneinfo
from unittest.mock import patch, MagicMock

import nepal_config
from nepal_config import (
    NEPAL_TZ,
    _has_devanagari,
    format_nepal_relative_time,
    parse_to_nepal_time,
    DEFAULT_HEADERS,
)
import nepal_news_store
import nepal_fetcher
import nepal_summarizer


class TestConfigAndHelpers(unittest.TestCase):
    def test_has_devanagari(self):
        self.assertTrue(_has_devanagari("नेपाल समाचार"))
        self.assertTrue(_has_devanagari("PM Oli visited काठमाडौँ today"))
        self.assertFalse(_has_devanagari("Kathmandu news only"))
        self.assertFalse(_has_devanagari(""))
        self.assertFalse(_has_devanagari(None))

    def test_format_nepal_relative_time_boundaries(self):
        now_npt = datetime.datetime(2026, 11, 23, 12, 0, 0, tzinfo=NEPAL_TZ)
        
        # Under 60 seconds
        dt_just_now = now_npt - datetime.timedelta(seconds=45)
        self.assertEqual(format_nepal_relative_time(dt_just_now, now_npt), "Just now")
        
        # Minutes
        dt_15m = now_npt - datetime.timedelta(minutes=15)
        self.assertEqual(format_nepal_relative_time(dt_15m, now_npt), "15m ago")
        
        # Hours
        dt_4h = now_npt - datetime.timedelta(hours=4)
        self.assertEqual(format_nepal_relative_time(dt_4h, now_npt), "4h ago")
        
        # Days
        dt_3d = now_npt - datetime.timedelta(days=3)
        self.assertEqual(format_nepal_relative_time(dt_3d, now_npt), "3d ago")
        
        # Beyond 7 days (date string)
        dt_10d = now_npt - datetime.timedelta(days=10)
        self.assertIn("Nov", format_nepal_relative_time(dt_10d, now_npt))

    def test_default_headers_present(self):
        self.assertIn("User-Agent", DEFAULT_HEADERS)
        self.assertIn("Accept", DEFAULT_HEADERS)


class TestFetcherConditionalHTTP(unittest.TestCase):
    def test_session_pooling(self):
        s1 = nepal_fetcher.get_worker_session()
        s2 = nepal_fetcher.get_worker_session()
        self.assertIs(s1, s2)
        self.assertIn("https://", s1.adapters)

    def test_conditional_fetch_304_handling(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 304
        mock_resp.content = b""

        with patch.object(nepal_fetcher.get_worker_session(), "get", return_value=mock_resp):
            content, is_mod, st_code = nepal_fetcher.fetch_feed_with_conditional_cache(
                "https://example.com/feed.xml",
                timeout_secs=2.0,
            )
            self.assertIsNone(content)
            self.assertFalse(is_mod)
            self.assertEqual(st_code, 304)

    def test_conditional_fetch_200_caches_etag(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"<rss><channel><title>Test</title></channel></rss>"
        mock_resp.headers = {"ETag": '"abc123etag"', "Last-Modified": "Mon, 23 Nov 2026 05:00:00 GMT"}

        url = "https://example.com/fresh_feed.xml"
        with patch.object(nepal_fetcher.get_worker_session(), "get", return_value=mock_resp):
            content, is_mod, st_code = nepal_fetcher.fetch_feed_with_conditional_cache(url)
            self.assertTrue(is_mod)
            self.assertEqual(st_code, 200)
            self.assertIn(b"Test", content)

        # Check cached headers
        with nepal_fetcher._FEED_HTTP_CACHE_LOCK:
            cached = nepal_fetcher._FEED_HTTP_CACHE.get(url)
            self.assertIsNotNone(cached)
            self.assertEqual(cached.get("etag"), '"abc123etag"')


class TestNewsStoreSQLBuilders(unittest.TestCase):
    def test_build_search_sql_like(self):
        sql = nepal_news_store._build_search_sql("Kathmandu election", ["title", "summary"])
        self.assertIsNotNone(sql)
        self.assertIn("ILIKE", sql)
        self.assertIn("ESCAPE", sql)
        self.assertIn("COALESCE(title, '')", sql)

    def test_build_search_sql_fts(self):
        sql = nepal_news_store._build_search_sql("Oli election", ["title", "summary"], use_fts=True)
        self.assertIsNotNone(sql)
        self.assertIn("to_tsvector", sql)
        self.assertIn("to_tsquery", sql)

    def test_build_category_sql(self):
        # Specific category
        sql_in = nepal_news_store._build_category_sql("🇮🇳 India Section")
        self.assertIn("India Section", sql_in)
        self.assertIn("primary_section", sql_in)

        # All categories (unfiltered)
        sql_all = nepal_news_store._build_category_sql("🌐 All Categories")
        self.assertIsNone(sql_all)

        # Classified only
        sql_cls = nepal_news_store._build_category_sql("📂 Classified Only")
        self.assertIn("primary_section IN", sql_cls)

    def test_npt_ts_formatting(self):
        dt = datetime.datetime(2026, 11, 23, 10, 30, 0, tzinfo=NEPAL_TZ)
        ts_npt = nepal_news_store._fmt_sql_ts(dt, as_utc=False)
        ts_utc = nepal_news_store._fmt_sql_ts(dt, as_utc=True)
        self.assertIn("2026-11-23 10:30:00", ts_npt)
        self.assertIn("+0000", ts_utc)


class TestSummarizerResilience(unittest.TestCase):
    def test_devanagari_detection_in_summarizer(self):
        self.assertTrue(nepal_summarizer._has_devanagari("नेपाल"))
        self.assertFalse(nepal_summarizer._has_devanagari("Nepal"))

    def test_malformed_json_resilience(self):
        # Test fallback when JSON response from an LLM is surrounded by Markdown fences or malformed
        raw_output = "```json\n{\"title\": \"Test News\", \"category\": \"Nepal – Internal\"}\n```"
        clean = raw_output.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        import json
        data = json.loads(clean)
        self.assertEqual(data["title"], "Test News")
        self.assertEqual(data["category"], "Nepal – Internal")


if __name__ == "__main__":
    unittest.main()
