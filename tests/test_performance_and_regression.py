"""
Regression and performance correctness test suite for Nepal Media Monitor.
Covers timestamp conversions, SQL index/trigram alignment, keyset pagination &
timeframe boundaries, concurrent pipeline lock & isolation, and end-to-end
Streamlit AppTest flows (login deferral, single-pass load_more delta payloads,
workspace switching, filters, search, Analytics & Export, System Health).
"""

import datetime
import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class StoreAndPaginationUnitTests(unittest.TestCase):
    def test_timestamp_helpers_preserve_wallclock_and_microseconds(self):
        import nepal_news_store as store

        dt_np = store._parse_npt_wallclock_ts("2026-11-18 14:32:10.654321+00:00")
        self.assertIsNotNone(dt_np)
        self.assertEqual(dt_np.tzinfo, store.NEPAL_TZ)
        self.assertEqual((dt_np.hour, dt_np.minute, dt_np.second, dt_np.microsecond), (14, 32, 10, 654321))

        dt_x = store._parse_utc_to_npt_ts("2026-11-18T08:47:10.123456+00:00")
        self.assertIsNotNone(dt_x)
        self.assertEqual(dt_x.tzinfo, store.NEPAL_TZ)
        self.assertEqual((dt_x.hour, dt_x.minute, dt_x.second, dt_x.microsecond), (14, 32, 10, 123456))

    def test_where_builders_respect_npt_vs_utc_and_trgm_expression(self):
        import nepal_news_store as store

        s_npt = datetime.datetime(2026, 11, 18, 12, 0, 0, tzinfo=store.NEPAL_TZ)
        e_npt = datetime.datetime(2026, 11, 18, 15, 0, 0, tzinfo=store.NEPAL_TZ)
        snap = datetime.datetime(2026, 11, 18, 15, 0, 0, tzinfo=store.NEPAL_TZ)

        art_w = " AND ".join(store._build_articles_where(start_dt=s_npt, end_dt=e_npt, snapshot_ingested_at=snap, search_query="oli"))
        self.assertIn("2026-11-18 12:00:00.000000", art_w)
        self.assertIn("2026-11-18 09:15:00.000000+0000", art_w)
        self.assertNotIn("CONCAT_WS", art_w)
        self.assertIn("COALESCE(title, '') || ' '", art_w)

        ind_w = " AND ".join(store._build_indian_where(start_dt=s_npt, end_dt=e_npt, snapshot_ingested_at=snap))
        self.assertIn("2026-11-18 12:00:00.000000", ind_w)
        self.assertIn("2026-11-18 09:15:00.000000+0000", ind_w)

        x_w = " AND ".join(store._build_x_where(start_dt=s_npt, end_dt=e_npt, snapshot_ingested_at=snap, search_query="budget"))
        self.assertIn("2026-11-18 06:15:00.000000+0000", x_w)
        self.assertNotIn("CONCAT_WS", x_w)

    def test_theme_payloads_have_no_blocking_fonts_and_compact_sizes(self):
        import apple_theme

        self.assertNotIn("fonts.googleapis.com", apple_theme.AUTH_CSS)
        self.assertNotIn("fonts.googleapis.com", apple_theme.FEED_CARD_CSS)
        self.assertNotIn("fonts.googleapis.com", apple_theme.APPLE_DESIGN_SYSTEM_CSS)
        self.assertLess(len(apple_theme.AUTH_CSS.encode("utf-8")), 4500)
        self.assertLess(len(apple_theme.FEED_CARD_CSS.encode("utf-8")), 12000)

    def test_psycopg_datetime_and_supavisor_dsn_resolution(self):
        import nepal_news_store as store

        # Ensure psycopg3 UTC-tagged wallclock datetimes keep NPT wallclock hour/minute/microsecond
        utc_wallclock_dt = datetime.datetime(2026, 11, 18, 14, 45, 12, 987654, tzinfo=datetime.timezone.utc)
        parsed_np = store._parse_npt_wallclock_ts(utc_wallclock_dt)
        self.assertEqual(parsed_np.tzinfo, store.NEPAL_TZ)
        self.assertEqual((parsed_np.hour, parsed_np.minute, parsed_np.second, parsed_np.microsecond), (14, 45, 12, 987654))

        with mock.patch.dict("os.environ", {"SUPABASE_DB_PASSWORD": "p@ss/w#rd!", "SUPABASE_DB_HOST": "aws-1-ap-south-1.pooler.supabase.com"}, clear=False):
            dsn = store._resolve_supavisor_dsn()
            self.assertIsNotNone(dsn)
            self.assertIn("aws-1-ap-south-1.pooler.supabase.com:6543/postgres", dsn)
            self.assertIn("p%40ss%2Fw%23rd%21", dsn)
            self.assertIn("sslmode=", dsn)

        # Placeholder passwords must be rejected safely so fallback continues without auth errors
        with mock.patch.dict("os.environ", {"DATABASE_URL": "postgresql://postgres:[YOUR-DATABASE-PASSWORD]@db.iiztmvbfrydfowehtiqa.supabase.co:5432/postgres"}, clear=False):
            self.assertIsNone(store._resolve_supavisor_dsn())

        # Direct db.<ref>.supabase.co:5432 URI with no AF_INET record rewrites automatically to IPv4 Supavisor pooler
        with mock.patch("socket.getaddrinfo", side_effect=OSError("no ipv4")), \
             mock.patch.dict("os.environ", {"DATABASE_URL": "postgresql://postgres:secretPass@db.iiztmvbfrydfowehtiqa.supabase.co:5432/postgres"}, clear=False):
            rewritten = store._resolve_supavisor_dsn()
            self.assertIn("postgres.iiztmvbfrydfowehtiqa:secretPass@aws-1-ap-south-1.pooler.supabase.com:6543/postgres", rewritten)

    def test_concurrent_pipeline_isolation_and_no_overlap_lock(self):
        import nepal_news_scheduler as sched

        def fake_np(**kwargs):
            time.sleep(0.18)
            return [{"id": 1}, {"id": 2}]

        def fake_in(**kwargs):
            time.sleep(0.05)
            raise RuntimeError("Indian source timeout")

        def fake_x(**kwargs):
            time.sleep(0.05)
            return [{"id": 99}]

        with mock.patch("nepal_fetcher.fetch_top_nepal_media", side_effect=fake_np), \
             mock.patch("nepal_fetcher.fetch_nepal_in_indian_media", side_effect=fake_in), \
             mock.patch("nepal_x_scanner.scan_popular_nepal_x_posts", side_effect=fake_x):
            t0 = time.perf_counter()
            res, errs = sched._run_concurrent_ingest_pipelines(pipeline_timeout_secs=5.0)
            elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 0.35, "Pipelines did not execute concurrently")
        self.assertEqual(res.get("nepali"), 2)
        self.assertEqual(res.get("x"), 1)
        self.assertIn("indian", errs)

        # Verify overlap guard AND targeted failed-source retry + selective stream_seqs update
        gate = sched.threading.Event()
        with mock.patch("nepal_fetcher.fetch_top_nepal_media", side_effect=lambda **k: (gate.wait(1.0), [{"id": 1}])[1]), \
             mock.patch("nepal_fetcher.fetch_nepal_in_indian_media", side_effect=RuntimeError("transient error")), \
             mock.patch("nepal_x_scanner.scan_popular_nepal_x_posts", return_value=[{"id": 7}]):
            started1, _ = sched.trigger_manual_sync_async()
            started2, snap2 = sched.trigger_manual_sync_async()
            gate.set()
            deadline = time.time() + 3.0
            while sched.get_manual_sync_status().get("running") and time.time() < deadline:
                time.sleep(0.02)

        self.assertTrue(started1)
        self.assertFalse(started2)
        self.assertTrue(snap2.get("running"))
        after_first = sched.get_manual_sync_status()
        self.assertIn("indian", after_first["errors"])
        self.assertEqual(after_first["pipelines"]["x"]["status"], "done")
        x_seq_before = after_first["stream_seqs"]["x"]

        # Retry ONLY failed 'indian' stream independently without re-running nepali/x
        with mock.patch("nepal_fetcher.fetch_nepal_in_indian_media", return_value=[{"id": 42}]) as mock_in_retry, \
             mock.patch("nepal_x_scanner.scan_popular_nepal_x_posts") as mock_x_retry:
            started_retry, _ = sched.trigger_manual_sync_async(targets=["indian"])
            self.assertTrue(started_retry)
            deadline = time.time() + 3.0
            while sched.get_manual_sync_status().get("running") and time.time() < deadline:
                time.sleep(0.02)
            mock_in_retry.assert_called_once()
            mock_x_retry.assert_not_called()
        after_retry = sched.get_manual_sync_status()
        self.assertEqual(after_retry["stream_seqs"]["x"], x_seq_before)
        self.assertNotIn("indian", after_retry["errors"])
        self.assertEqual(after_retry["pipelines"]["indian"]["status"], "done")

    def test_empty_exception_formatting_and_portal_fallback_and_timeouts(self):
        import io
        import nepal_config as cfg
        import nepal_fetcher as fetcher
        import nepal_news_scheduler as sched

        self.assertEqual(cfg.format_exc(TimeoutError()), "TimeoutError")
        self.assertEqual(cfg.format_exc(RuntimeError("boom")), "RuntimeError: boom")

        portal = {"name": "TestPortal", "type": "html", "url": "https://example.com/", "alt_urls": ["https://example.com/rss"], "lang": "English", "category": "Digital Daily"}
        # 1) Empty TimeoutError from fetch_single_portal must record ERROR with non-blank error text
        with mock.patch("nepal_fetcher.fetch_single_portal", side_effect=TimeoutError()) as m_fetch, \
             mock.patch("nepal_news_scheduler.record_source_error") as m_rec_err, \
             mock.patch("nepal_news_scheduler.batch_upsert_articles") as m_upsert:
            out = sched.run_single_source_discovery(portal)
            self.assertEqual(out["status"], "ERROR")
            self.assertEqual(out["error"], "TimeoutError")
            m_rec_err.assert_called_once()
            self.assertEqual(m_rec_err.call_args[0][1], "TimeoutError")
            m_upsert.assert_not_called()
            self.assertIs(m_fetch.call_args.kwargs.get("persist"), False)
            self.assertIs(m_fetch.call_args.kwargs.get("raise_on_error"), True)

        # 2) HTML portal yielding empty/blocked homepage falls back cleanly to RSS alt_urls
        rss_bytes = (
            b'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            b'<item><title>Kathmandu diplomatic meeting held</title>'
            b'<link>https://example.com/news/1</link><pubDate>Wed, 18 Nov 2026 09:00:00 +0000</pubDate></item>'
            b'</channel></rss>'
        )

        class _FakeResp:
            def __init__(self, data: bytes):
                self._data = data
            def read(self):
                return self._data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        def _fake_urlopen(req, context=None, timeout=None):
            u = req.full_url if hasattr(req, "full_url") else str(req)
            if u.endswith("/rss"):
                return _FakeResp(rss_bytes)
            return _FakeResp(b"<html><body><div>blocked</div></body></html>")

        with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen), \
             mock.patch("nepal_fetcher.batch_fetch_full_content"), \
             mock.patch("nepal_fetcher.batch_upsert_articles") as m_up:
            parsed = fetcher.fetch_single_portal(
                portal, datetime.datetime.now(cfg.NEPAL_TZ), persist=False, raise_on_error=True
            )
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0]["title"], "Kathmandu diplomatic meeting held")
            m_up.assert_not_called()

        # 3) Bounded cycle_timeout_secs exits quickly without waiting for hung portal futures
        gate = sched.threading.Event()
        slow_portals = [{"name": "SlowPortal", "type": "rss", "url": "https://example.com/slow", "lang": "Nepali"}]
        health_rows = [{"name": "SlowPortal", "enabled": 1, "check_interval_mins": 10}]
        with mock.patch("nepal_fetcher.TOP_NEPAL_NEWS_PORTALS", slow_portals), \
             mock.patch("nepal_news_scheduler.get_all_source_health", return_value=health_rows), \
             mock.patch("nepal_news_scheduler.run_single_source_discovery", side_effect=lambda p: (gate.wait(2.0), {"ingested": 0})[1]):
            t0 = time.perf_counter()
            res = sched.run_all_sources_discovery(parallel_workers=1, force_all=True, cycle_timeout_secs=0.1)
            elapsed = time.perf_counter() - t0
            gate.set()
        self.assertLess(elapsed, 0.8)
        self.assertEqual(res["results"]["SlowPortal"]["status"], "TIMEOUT")

    def test_indian_media_scoring_monotonicity_bing_fresh_and_dedupe(self):
        import nepal_config as cfg
        import nepal_fetcher as fetcher
        import nepal_news_store as store

        # 1) Regression check on real headlines previously lost at 0.64 + promo filtering
        trapped_cases = [
            ("Centre Notifies Immigration Rule Changes, Revises Passport Norms For Nepal & Bhutan Travel", "https://outlookindia.com/national/nepal-bhutan"),
            ("In first bilateral trip, Nepal PM Balendra Shah to visit India from Nov 22", "https://indianexpress.com/article/india/nepal-pm-balendra-shah-india-visit"),
            ("Ayodhya-Janakpur Train Completes Trial Run Linking India", "https://www.ndtv.com/india-news/ayodhya-janakpur-train"),
            ("Flash floods in Nepal again: Warning bells for Himalaya, lessons for India", "https://indianexpress.com/article/explained/flash-floods-in-nepal"),
            ("बिहार: पुराने मोबाइल खरीद नेपाल- बांग्लादेश भेज रहे शातिर", "https://www.livehindustan.com/bihar/cyber-criminals-nepal"),
        ]
        for headline, url in trapped_cases:
            ev = fetcher.evaluate_indian_article_nepal_relevance(
                title=headline, summary=headline, full_content=headline, link=url, source="Test"
            )
            self.assertEqual(ev["relevance_status"], "substantive", f"Expected substantive for {headline}: {ev}")
            self.assertGreaterEqual(ev["nepal_relevance_score"], 0.66, f"Expected >=0.66 for {headline}: {ev}")

        promo = fetcher.evaluate_indian_article_nepal_relevance(
            title="प्रभात खबर को Google पर पसंदीदा सोर्स बनाएं →",
            summary="नेपाल में बड़ी खबर",
            link="https://profile.google.com/@prabhatkhabartv",
        )
        self.assertEqual(promo["relevance_status"], "excluded")
        self.assertEqual(promo["nepal_relevance_score"], 0.0)

        # 2) Redirect unwrap + smart quote canonical_id dedupe
        wrapped = "http://www.bing.com/news/apiclick.aspx?ref=FexRss&url=https%3a%2f%2fwww.moneycontrol.com%2fworld%2fnepal-visit.html%3futm_source%3dbing"
        self.assertEqual(store.normalize_canonical_url(wrapped), "https://www.moneycontrol.com/world/nepal-visit.html")
        cid1 = store.generate_canonical_id("The Indian Express", wrapped, "Nepal PM Balendra Shah's agenda")
        cid2 = store.generate_canonical_id("The Indian Express", "https://www.moneycontrol.com/world/nepal-visit.html", "Nepal PM Balendra Shah’s agenda")
        self.assertEqual(cid1, cid2)

        # 3) Stale >72h HTML items still trigger date-sorted Bing fallback & strip .np sites + hydrate body scores
        now_npt = datetime.datetime.now(cfg.NEPAL_TZ)
        old_html = (
            "<html><body>"
            "<article><a href='/news/old-1'><h2>Nepal flood situation reviewed by border officials in Patna</h2></a><time>2026-09-01</time></article>"
            "<article><a href='/news/old-2'><h2>India Nepal power corridor meeting concludes in New Delhi</h2></a><time>2026-09-02</time></article>"
            "<article><a href='/news/old-3'><h2>Kathmandu trade delegation arrives in Kolkata for talks</h2></a><time>2026-09-03</time></article>"
            "<article><a href='/news/nepal-borderline-1'><h2>Regional energy grid talks advance across eastern corridor</h2></a><time>2026-11-18</time></article>"
            "</body></html>"
        ).encode("utf-8")
        bing_rss = (
            b'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
            b'<item><title>Why Nepal PM Balendra Shah cut short first India visit - Moneycontrol</title>'
            b'<link>http://www.bing.com/news/apiclick.aspx?url=https%3a%2f%2fwww.moneycontrol.com%2fworld%2fbalen-25h.html</link>'
            b'<pubDate>Wed, 18 Nov 2026 02:50:00 GMT</pubDate><description>Nepal PM Balendra Shah bilateral talks in Delhi</description></item>'
            b'<item><title>Kathmandu airport flight update - Onlinekhabar</title>'
            b'<link>http://www.bing.com/news/apiclick.aspx?url=https%3a%2f%2fenglish.onlinekhabar.com%2fflight.html</link>'
            b'<pubDate>Wed, 18 Nov 2026 03:00:00 GMT</pubDate><description>Nepal domestic aviation update</description></item>'
            b'</channel></rss>'
        )

        class _Resp:
            def __init__(self, b: bytes):
                self._b = b
            def read(self):
                return self._b
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        seen_urls = []
        def _mock_urlopen(req, context=None, timeout=None):
            u = req.full_url if hasattr(req, "full_url") else str(req)
            seen_urls.append(u)
            if "bing.com/news/search" in u:
                return _Resp(bing_rss)
            return _Resp(old_html)

        def _fake_hydrate(cands, max_workers=10, summarize_english=False):
            for c in cands:
                if "Regional energy grid talks" in c["title"]:
                    c["full_content"] = "Nepal electricity grid connectivity with India expanded as Nepal Power Authority signed 350 MW winter bilateral trade agreement in Kathmandu."

        src_cfg = {"name": "Moneycontrol", "type": "topic_html", "domain": "moneycontrol.com", "url": "https://www.moneycontrol.com/news/tags/nepal.html", "lang": "English"}
        with mock.patch("urllib.request.urlopen", side_effect=_mock_urlopen), \
             mock.patch("nepal_fetcher.extract_date_from_card_or_url", return_value=now_npt - datetime.timedelta(days=20)), \
             mock.patch("nepal_fetcher.batch_fetch_full_content", side_effect=_fake_hydrate):
            out = fetcher.fetch_single_indian_media(src_cfg, now_npt, relevance_threshold=0.65)

        self.assertTrue(any("qft=sortbydate" in u for u in seen_urls), f"Date-sorted Bing fallback did not trigger: {seen_urls}")
        by_link = {x["link"]: x for x in out}
        self.assertIn("https://www.moneycontrol.com/world/balen-25h.html", by_link)
        self.assertIn("https://www.moneycontrol.com/news/nepal-borderline-1", by_link)
        self.assertEqual(by_link["https://www.moneycontrol.com/news/nepal-borderline-1"]["relevance_status"], "substantive")
        self.assertFalse(any("onlinekhabar.com" in lk for lk in by_link), "Nepali portal must be excluded from Indian Press")

    def test_x_scanner_snowflake_selection_concurrent_discovery_and_batched_upsert(self):
        import nepal_news_store as store
        import nepal_x_scanner as xs

        now_npt = datetime.datetime(2026, 11, 19, 9, 45, 0, tzinfo=xs.NEPAL_TZ)

        def _make_snowflake(hours_ago: float, seq: int = 1) -> str:
            dt = now_npt - datetime.timedelta(hours=hours_ago)
            ms = int(dt.astimezone(datetime.timezone.utc).timestamp() * 1000) - 1288834974657
            return str((ms << 22) | seq)

        sid_new_1 = _make_snowflake(1.0, 1)
        sid_new_2 = _make_snowflake(3.0, 2)
        sid_stale_recent = _make_snowflake(6.0, 3)
        sid_fresh_recent = _make_snowflake(10.0, 4)
        sid_old_stored = _make_snowflake(96.0, 5)

        existing_map = {
            sid_stale_recent: (now_npt - datetime.timedelta(minutes=20)).astimezone(datetime.timezone.utc),
            sid_fresh_recent: (now_npt - datetime.timedelta(seconds=30)).astimezone(datetime.timezone.utc),
            sid_old_stored: (now_npt - datetime.timedelta(days=2)).astimezone(datetime.timezone.utc),
        }

        # When 40+ new/stale items exist, freshly synced and >48h stored tweets are skipped
        bulk_new = [_make_snowflake(0.5, 100 + i) for i in range(45)]
        selected_bulk = xs._select_tweet_ids_to_enrich(
            [sid_old_stored, sid_fresh_recent, sid_stale_recent, sid_new_2, sid_new_1] + bulk_new,
            existing_map=existing_map,
            now_npt=now_npt,
        )
        self.assertIn(sid_new_1, selected_bulk)
        self.assertIn(sid_new_2, selected_bulk)
        self.assertIn(sid_stale_recent, selected_bulk)
        self.assertNotIn(sid_fresh_recent, selected_bulk)
        self.assertNotIn(sid_old_stored, selected_bulk)
        # Newest-first Snowflake ordering within brand_new
        self.assertLess(selected_bulk.index(sid_new_1), selected_bulk.index(sid_new_2))

        # When every recent tweet was just updated, active <=24h top-up prevents empty sync return
        selected_topup = xs._select_tweet_ids_to_enrich(
            [sid_old_stored, sid_fresh_recent],
            existing_map=existing_map,
            now_npt=now_npt,
        )
        self.assertEqual(selected_topup, [sid_fresh_recent])

        # save_x_posts deduplicates duplicate IDs before SQL upsert and parses cnt scalar
        seen_sql = []

        def _fake_query(sql, params=None):
            seen_sql.append(sql)
            return [{"cnt": 2}]

        sample_posts = [
            {"id": sid_new_1, "handle": "@a", "text": "Post one", "published_dt": now_npt},
            {"id": sid_new_1, "handle": "@a", "text": "Post one dup", "published_dt": now_npt},
            {"id": sid_new_2, "handle": "@b", "text": "Post two", "published_dt": now_npt - datetime.timedelta(hours=1)},
        ]
        with mock.patch("nepal_news_store.query_supabase", side_effect=_fake_query):
            up_cnt = store.save_x_posts(sample_posts)
        self.assertEqual(up_cnt, 2)
        self.assertEqual(len(seen_sql), 1)
        self.assertIn("Post one", seen_sql[0])
        self.assertNotIn("Post one dup", seen_sql[0])
        self.assertIn("Post two", seen_sql[0])

        # scan_popular_nepal_x_posts merges profile + Bing concurrently and saves once with batch_size=250
        prof_acc = {"handle": "NepalVoice", "name": "Nepal Voice", "role": "Media", "avatar_bg": "#111", "initials": "NV"}
        with mock.patch("nepal_x_scanner.get_monitored_x_accounts", return_value=[prof_acc]), \
             mock.patch("nepal_x_scanner._discover_profile_tweet_candidates", return_value={sid_new_1: prof_acc}), \
             mock.patch("nepal_x_scanner._discover_bing_tweet_candidates", return_value=[(sid_new_1, "NepalVoice", "Dup", "https://x.com/NepalVoice/status/" + sid_new_1), (sid_new_2, "OtherUser", "Bing hit", "https://x.com/OtherUser/status/" + sid_new_2)]), \
             mock.patch("nepal_x_scanner._load_existing_x_refresh_map", return_value={}), \
             mock.patch("nepal_x_scanner._enrich_tweet_by_id", side_effect=lambda sid, **kw: {"id": sid, "text": f"Unique tweet {sid}", "published_dt": now_npt}) as m_enrich, \
             mock.patch("nepal_news_store.save_x_posts", return_value=2) as m_save, \
             mock.patch("nepal_fetcher.bridge_x_portals_to_articles", return_value=0) as m_bridge:
            out_posts = xs.scan_popular_nepal_x_posts(force_refresh=True)

        self.assertEqual(len(out_posts), 2)
        self.assertEqual(m_enrich.call_count, 2)
        m_save.assert_called_once()
        self.assertEqual(m_save.call_args.kwargs.get("batch_size"), 250)
        m_bridge.assert_called_once()

    def test_bs_calendar_intraday_timestamp_priority_and_scheduler_utc_normalization(self):
        import nepal_config as cfg
        import nepal_fetcher as fetcher
        import nepal_news_store as store
        import nepal_news_scheduler as sched
        from bs4 import BeautifulSoup

        now_npt = datetime.datetime(2026, 11, 19, 15, 0, 0, tzinfo=cfg.NEPAL_TZ)

        # 1) Accurate BS-to-AD calendar conversion for Mangsir & Kartik 2083
        self.assertEqual(fetcher._bs_to_ad_date(2083, 8, 3), datetime.date(2026, 11, 19))
        self.assertEqual(fetcher._bs_to_ad_date(2083, 8, 1), datetime.date(2026, 11, 17))
        self.assertEqual(fetcher._bs_to_ad_date(2083, 7, 25), datetime.date(2026, 11, 11))

        dt_bs_today, is_do_today = fetcher.parse_snippet_to_datetime_with_meta("३ मंसिर २०८३", now_npt)
        self.assertTrue(is_do_today)
        self.assertEqual(dt_bs_today.date(), datetime.date(2026, 11, 19))
        # Today's date_only item preserves discovery time instead of 00:00:00 or 12:00:00
        self.assertEqual((dt_bs_today.hour, dt_bs_today.minute), (15, 0))

        dt_bs_past, is_do_past = fetcher.parse_snippet_to_datetime_with_meta("२५ कार्तिक २०८३", now_npt)
        self.assertTrue(is_do_past)
        self.assertEqual(dt_bs_past.date(), datetime.date(2026, 11, 11))

        # 2) eKantipur date-only <span>2026-11-19</span> & URL /2026/11/19/ do not short-circuit JSON-LD datePublished
        ek_card_html = (
            '<div class="template-taja"><div class="news-section">'
            '<a href="https://ekantipur.com/business/2026/11/19/power-trade-test.html">'
            'भारतको ऊर्जा एक्सचेन्जमा ५९४ मेगावाट विद्युत् बेच्न नेपाललाई अनुमति <span>2026-11-19</span>'
            '</a></div></div>'
        )
        ek_article_html = (
            '<html><head><script type="application/ld+json">'
            '{"@type":"NewsArticle","datePublished":"2026-11-19 14:41:11"}'
            '</script></head><body><p>Body</p></body></html>'
        ).encode("utf-8")

        # 3) Kathmandu Post article HTML prefers Updated at : HH:MM over Published at : date-only and ignores blocktop-date
        kp_article_html = (
            '<html><body>'
            '<div class="blocktop blocktop-date">Thursday, November 19, 2026</div>'
            '<div class="updated-time">Published at : November 19, 2026</div>'
            '<div class="updated-time">Updated at : November 19, 2026 12:13</div>'
            '</body></html>'
        ).encode("utf-8")

        class _FakeR:
            def __init__(self, b: bytes):
                self._b = b
            def read(self, n=-1):
                return self._b
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def _fake_uopen(req, context=None, timeout=None):
            u = req.full_url if hasattr(req, "full_url") else str(req)
            if "ekantipur.com" in u:
                return _FakeR(ek_article_html)
            return _FakeR(kp_article_html)

        soup_ek = BeautifulSoup(ek_card_html, "html.parser")
        a_ek = soup_ek.find("a")
        fetcher.ARTICLE_DATE_CACHE.pop("https://ekantipur.com/business/2026/11/19/power-trade-test.html", None)
        fetcher.ARTICLE_DATE_CACHE.pop("https://kathmandupost.com/sports/2026/11/19/anfa-test", None)

        with mock.patch("urllib.request.urlopen", side_effect=_fake_uopen):
            dt_ek = fetcher.extract_date_from_card_or_url(
                a_ek, "https://ekantipur.com/business/2026/11/19/power-trade-test.html", now_npt
            )
            dt_kp = fetcher.extract_date_from_card_or_url(
                None, "https://kathmandupost.com/sports/2026/11/19/anfa-test", now_npt
            )

        self.assertEqual((dt_ek.year, dt_ek.month, dt_ek.day, dt_ek.hour, dt_ek.minute, dt_ek.second), (2026, 11, 19, 14, 41, 11))
        self.assertEqual((dt_kp.year, dt_kp.month, dt_kp.day, dt_kp.hour, dt_kp.minute), (2026, 11, 19, 12, 13))

        # 4) parse_to_nepal_time keeps slightly future timestamps (clock skew <= 1d) and only clamps >1d future
        skew_dt = now_npt + datetime.timedelta(minutes=5)
        parsed_skew, rel_skew, _ = cfg.parse_to_nepal_time(skew_dt, now_npt)
        self.assertEqual(parsed_skew, skew_dt)
        self.assertEqual(rel_skew, "Just now")

        far_future = now_npt + datetime.timedelta(days=3)
        parsed_far, _, _ = cfg.parse_to_nepal_time(far_future, now_npt)
        self.assertEqual(parsed_far, now_npt)

        # 5) Scheduler UTC normalization handles both aware datetimes and future-skewed naive strings
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        aware_recent = now_utc - datetime.timedelta(minutes=2)
        future_skewed_str = (now_utc + datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S+00:00")
        self.assertEqual(sched._normalize_to_utc_dt(aware_recent), aware_recent)
        skew_norm = sched._normalize_to_utc_dt(future_skewed_str)
        self.assertIsNotNone(skew_norm)
        self.assertLess((now_utc - skew_norm).total_seconds() / 60.0, -1.0)


class SupabaseLiveIntegrationTests(unittest.TestCase):
    def test_live_feed_keyset_pagination_and_single_cte_bootstraps(self):
        import concurrent.futures
        import nepal_news_store as store

        now_npt = datetime.datetime.now(store.NEPAL_TZ)
        start_12h = now_npt - datetime.timedelta(hours=12)

        login_boot = store.get_login_bootstrap_bundle(
            header_start_dt=start_12h, header_end_dt=now_npt,
            live_start_dt=start_12h, live_end_dt=now_npt, limit=10,
        )
        counts = login_boot["header"]["counts"]
        sum_counts = counts["nepali_count"] + counts["indian_count"] + counts["x_count"]
        self.assertEqual(login_boot["live_page"]["total_count"], sum_counts)
        self.assertLessEqual(len(login_boot["live_page"]["rows"]), 10)

        ind_boot = store.get_indian_workspace_bootstrap(
            start_dt=start_12h, end_dt=now_npt, snapshot_ingested_at=now_npt, limit=10
        )
        self.assertEqual(ind_boot["total_count"], counts["indian_count"])
        for br in ind_boot["borderline_items"]:
            self.assertGreaterEqual(float(br.get("nepal_relevance_score", 0.0)), 0.40)

        x_boot = store.get_x_workspace_bootstrap(
            start_dt=start_12h, end_dt=now_npt, snapshot_ingested_at=now_npt, limit=10
        )
        self.assertEqual(x_boot["total_count"], counts["x_count"])
        self.assertGreater(x_boot["kpis"]["total_discovered"], 0)

        # Simultaneous 3-user concurrent fetch respects _SUPABASE_SEM without errors
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futs = [
                pool.submit(store.get_feed_page_with_count, ws, start_12h, now_npt, now_npt, limit=5)
                for ws in ("live", "nepali", "x")
            ]
            results = [f.result() for f in futs]
        self.assertEqual(len(results), 3)

        for ws in ("live", "nepali", "x"):
            p1 = store.get_feed_page_with_count(
                workspace=ws,
                start_dt=start_12h,
                end_dt=now_npt,
                snapshot_ingested_at=now_npt,
                limit=5,
                include_count=True,
            )
            rows1 = p1["rows"]
            if len(rows1) == 5:
                last = rows1[-1]
                p2 = store.get_feed_page_with_count(
                    workspace=ws,
                    start_dt=start_12h,
                    end_dt=now_npt,
                    snapshot_ingested_at=now_npt,
                    cursor_dt=last["published_dt"],
                    cursor_rank=last.get("_stream_rank"),
                    cursor_id=last.get("_cursor_id") or last.get("canonical_id") or str(last.get("id", "")),
                    limit=5,
                    include_count=False,
                )
                rows2 = p2["rows"]
                ids1 = {(r.get("_feed_type", ws), str(r.get("canonical_id") or r.get("id"))) for r in rows1}
                ids2 = {(r.get("_feed_type", ws), str(r.get("canonical_id") or r.get("id"))) for r in rows2}
                self.assertEqual(ids1 & ids2, set(), f"Duplicate rows across keyset pages in {ws}")
                for r in rows1 + rows2:
                    self.assertTrue(start_12h <= r["published_dt"] <= now_npt, f"Out-of-window row leaked in {ws}")


class AppTestEndToEndRegressionTests(unittest.TestCase):
    def test_login_scroll_delta_workspace_switch_filters_and_exports(self):
        import components.infinite_feed as inf_comp
        from streamlit.testing.v1 import AppTest

        recorded = []
        orig_render = inf_comp.render_infinite_feed_component

        def spy_render(**kwargs):
            recorded.append({
                "key": kwargs.get("key"),
                "batch_count": len(kwargs.get("batches", [])),
                "seqs": [b.get("seq") for b in kwargs.get("batches", [])],
                "css_bytes": len(str(kwargs.get("theme_css", "")).encode("utf-8")),
            })
            return orig_render(**kwargs)

        with mock.patch.object(inf_comp, "render_infinite_feed_component", side_effect=spy_render):
            at = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=45)
            at.run()
            self.assertEqual(len(at.exception), 0)
            # Unauthenticated gate: shows password input, renders no feed, defers heavy stores
            self.assertEqual(len(at.text_input), 1)
            self.assertFalse(at.session_state["authenticated"] if "authenticated" in at.session_state else False)
            self.assertEqual(recorded, [])

            # Authenticate cleanly -> initial mount sends batch [0] and FEED_CARD_CSS (~7.8 KB, not 64 KB)
            recorded.clear()
            at.text_input[0].set_value("PIC@55")
            at.button[0].click().run()
            self.assertEqual(len(at.exception), 0)
            self.assertTrue(at.session_state["authenticated"])
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0]["seqs"], [0])
            self.assertGreater(recorded[0]["css_bytes"], 1000)
            self.assertLess(recorded[0]["css_bytes"], 12000)

            live_sess = at.session_state["feed_sessions"]["live"]
            initial_loaded = len(live_sess["items_by_uid"])
            self.assertGreater(initial_loaded, 0)
            snap_start = live_sess["snapshot_start_dt"]
            snap_end = live_sess["snapshot_end_dt"]

            # Warm no-op rerun sends ZERO batches and ZERO CSS bytes
            recorded.clear()
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0]["batch_count"], 0)
            self.assertEqual(recorded[0]["css_bytes"], 0)

            # Verify single-pass load_more: 1 component call, ONLY delta batch [1], ZERO CSS, inside window
            if live_sess["has_more"]:
                recorded.clear()
                at.session_state["inf_feed_live"] = {
                    "event": "load_more",
                    "next_seq": len(live_sess["batches"]),
                    "ts": int(time.time() * 1000) + 100,
                }
                at.run()
                self.assertEqual(len(at.exception), 0)
                self.assertEqual(len(recorded), 1, "load_more must execute in a single pass")
                self.assertEqual(recorded[0]["seqs"], [1], "load_more must send ONLY delta batch")
                self.assertEqual(recorded[0]["css_bytes"], 0, "load_more must NOT resend CSS")
                live_sess_after = at.session_state["feed_sessions"]["live"]
                self.assertGreater(len(live_sess_after["items_by_uid"]), initial_loaded)
                for item in live_sess_after["items_by_uid"].values():
                    self.assertTrue(snap_start <= item["published_dt"] <= snap_end)

            # Switch workspaces across all 6 views and back to Live Feed
            for target_ws in ("Nepali Media", "Indian Press", "X", "Analytics & Export", "System Health", "Live Feed"):
                recorded.clear()
                at.session_state["app_nav_section"] = target_ws
                at.run()
                self.assertEqual(len(at.exception), 0, f"Exception in workspace {target_ws}: {at.exception}")
                if target_ws == "Live Feed":
                    # Switching back reuses cached batches (0, 1) and mounts fresh iframe with FEED_CARD_CSS
                    self.assertEqual(recorded[-1]["seqs"], [0, 1])
                    self.assertGreater(recorded[-1]["css_bytes"], 1000)

            # Verify topic filter on Live Feed + search filter + timeframe switch (Today) work cleanly
            at.selectbox[0].set_value("🇮🇳 India Section").run()
            self.assertEqual(len(at.exception), 0)
            self.assertIn("India Section", at.session_state["feed_sessions"]["live"]["filter_sig"])
            at.session_state["committed_search_query"] = "oli"
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertIn("|oli", at.session_state["feed_sessions"]["live"]["filter_sig"])
            at.session_state["cp_timeframe_segment"] = "Today"
            at.session_state["tf_epoch"] = int(at.session_state["tf_epoch"]) + 1
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertIn("live|Today|", at.session_state["feed_sessions"]["live"]["filter_sig"])

    def test_share_and_read_modal_edit_persistence_and_whatsapp_sending(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=45)
        at.run()
        at.text_input[0].set_value("PIC@55")
        at.button[0].click().run()

        live_sess = at.session_state["feed_sessions"]["live"]
        first_uid = list(live_sess["items_by_uid"].keys())[0]
        item = live_sess["items_by_uid"][first_uid]

        # 1. Share modal: opening -> editing -> typing -> saving keeps modal on screen and commits draft v2
        at.session_state["inf_feed_live"] = {"event": "action", "action": "share", "item_uid": first_uid, "ts": int(time.time() * 1000) + 100}
        at.run()
        self.assertEqual(at.session_state["active_modal"]["mode"], "share")

        edit_btn = [b for b in at.button if b.key == f"dlg_edit_{first_uid}"][0]
        edit_btn.click().run()

        ti = [t for t in at.text_input if t.key == f"dlg_hl_edit_{first_uid}"][0]
        ta = [t for t in at.text_area if t.key == f"dlg_ta_edit_{first_uid}"][0]
        ti.set_value("Edited Regression Share Title")
        ta.set_value("Edited Regression Share Brief")

        save_btn = [b for b in at.button if b.key == f"dlg_save_edit_{first_uid}"][0]
        save_btn.click().run()

        cid = at.session_state["active_modal"]["cache_id"]
        sh_draft = at.session_state["share_drafts"][cid]
        self.assertEqual(sh_draft["version"], 2)
        self.assertEqual(sh_draft["saved_headline"], "Edited Regression Share Title")
        self.assertEqual(sh_draft["saved_content"], "Edited Regression Share Brief")
        self.assertFalse(sh_draft["is_editing"])

        # Close Share modal cleanly
        cls_btn = [b for b in at.button if b.key == f"dlg_sh_cls_{first_uid}"][0]
        cls_btn.click().run()
        self.assertIsNone(at.session_state.get("active_modal"))

        # 2. Read modal: opening -> translation editing -> typing -> saving -> WhatsApp single-click send
        at.session_state["inf_feed_live"] = {"event": "action", "action": "read", "item_uid": first_uid, "ts": int(time.time() * 1000) + 200}
        at.run()
        self.assertEqual(at.session_state["active_modal"]["mode"], "read")

        read_cid = at.session_state["active_modal"]["cache_id"]
        at.session_state["ondemand_fulltext"][read_cid] = {
            "ok": True,
            "lang": "en",
            "original_title": item.get("title"),
            "original_text": "Sample original text paragraph 1.\n\nSample paragraph 2.",
            "translated_title": "Translated English Title",
            "translated_text": "Translated English Body paragraph 1.\n\nTranslated English Body paragraph 2.",
            "source_url": item.get("link"),
            "is_complete": True,
        }
        at.session_state["ondemand_fulltext_view"][read_cid] = "en"
        at.run()

        rd_edit_btn = [b for b in at.button if b.key == f"dlg_rd_edit_{first_uid}"][0]
        rd_edit_btn.click().run()

        rd_ti = [t for t in at.text_input if t.key == f"dlg_rd_hl_{first_uid}"][0]
        rd_ta = [t for t in at.text_area if t.key == f"dlg_rd_ta_{first_uid}"][0]
        rd_ti.set_value("Custom Edited Translation Title")
        rd_ta.set_value("Custom Edited Translation Body Line 1.\n\nCustom Edited Translation Body Line 2.")

        rd_save_btn = [b for b in at.button if b.key == f"dlg_rd_save_{first_uid}"][0]
        rd_save_btn.click().run()

        rd_draft = at.session_state["read_translation_drafts"][read_cid]
        self.assertEqual(rd_draft["version"], 2)
        self.assertEqual(rd_draft["saved_headline"], "Custom Edited Translation Title")
        self.assertIn("Custom Edited Translation Body Line 1", rd_draft["saved_body"])
        self.assertFalse(rd_draft["is_editing"])

        # WhatsApp send
        send_btn = [b for b in at.button if b.key == f"dlg_rd_conf_{first_uid}"][0]
        with mock.patch("whatsapp_greenapi.send_group_message", return_value={"ok": True, "accepted": True, "id_message": "WA_TEST_REG_456"}), \
             mock.patch("nepal_news_store.record_whatsapp_sent") as mock_record:
            send_btn.click().run()
            self.assertTrue(mock_record.called)

        # 3. Verify X post destination group routing directly to Social Media Monitoring
        from whatsapp_greenapi import get_share_targets
        x_targets = get_share_targets(is_x_post=True)
        self.assertEqual(len(x_targets), 1)
        self.assertEqual(x_targets[0]["name"], "Social Media Monitoring")
        self.assertEqual(x_targets[0]["id"], "120363412139269937@g.us")

        news_targets = get_share_targets(is_x_post=False)
        self.assertEqual(len(news_targets), 2)
        self.assertEqual({t["name"] for t in news_targets}, {"India Related News in Nepali Media", "Core group of PIC Wing"})

    def test_annapurna_post_x_bridge_card_and_reader_parity(self):
        import nepal_config as cfg
        import nepal_fetcher as fetcher
        import nepal_summarizer as summ

        ap_cfg = next(p for p in cfg.TOP_NEPAL_NEWS_PORTALS if p["name"] == "Annapurna Post")
        self.assertEqual(ap_cfg["type"], "x_bridge")
        self.assertEqual(ap_cfg["x_handle"], "Annapurna_Post")

        now_npt = datetime.datetime(2026, 11, 19, 16, 15, 0, tzinfo=cfg.NEPAL_TZ)

        # 1) resolve_tco_url uses HEAD with allow_redirects=False and never probes annapurnapost.com
        fake_head_resp = mock.MagicMock()
        fake_head_resp.headers = {"Location": "https://annapurnapost.com/story/511589/"}
        fetcher.TCO_REDIRECT_CACHE.pop("https://t.co/VtyP9aRDD8", None)
        with mock.patch("nepal_fetcher.requests.head", return_value=fake_head_resp) as m_head:
            resolved = fetcher.resolve_tco_url("https://t.co/VtyP9aRDD8")
        self.assertEqual(resolved, "https://annapurnapost.com/story/511589/")
        self.assertFalse(m_head.call_args.kwargs.get("allow_redirects"))

        # 2) Bridged article resolves real annapurnapost.com URL, strips links/#/@, classifies & populates summary/full_content
        art = fetcher.build_x_bridged_article(
            portal=ap_cfg,
            tweet_id="2123350203076133335",
            raw_text="सेयर बजारमा सामान्य सुधार, कारोबार रकम ३ अर्बमा झर्यो #NEPSE @Annapurna_Post https://t.co/VtyP9aRDD8",
            published_dt_raw="2026-11-19T09:38:33.000Z",
            now_npt=now_npt,
            expanded_urls=["https://annapurnapost.com/story/511589/"],
            card_title="सेयर बजारमा सामान्य सुधार, कारोबार रकम ३ अर्बमा झर्यो",
            card_description="काठमाडौं : बिहीबार सेयर बजार परिसूचक नेप्सेमा सामान्य सुधार देखिएको छ। ने",
        )
        self.assertIsNotNone(art)
        self.assertEqual(art["source"], "Annapurna Post")
        self.assertEqual(art["link"], "https://annapurnapost.com/story/511589/")
        self.assertEqual(art["primary_section"], "Nepal – Economy")
        self.assertIn("Economy & Finance", art["secondary_tags"])
        self.assertNotIn("t.co", art["title"])
        self.assertNotIn("#", art["title"])
        self.assertNotIn("@", art["title"])
        self.assertEqual(art["summary"], "काठमाडौं : बिहीबार सेयर बजार परिसूचक नेप्सेमा सामान्य सुधार देखिएको छ।")
        self.assertEqual((art["published_dt"].hour, art["published_dt"].minute), (15, 23))

        # 3) Direct scraping works for annapurnapost.com via .news__details and Read modal succeeds cleanly (ok=True)
        mock_ap_html = (
            b'<html><body><div class="news__details">'
            b'<p>\xe0\xa4\x95\xe0\xa4\xbe\xe0\xa4\xa0\xe0\xa4\xae\xe0\xa4\xbe\xe0\xa4\xa1\xe0\xa4\xb0\xe0\xa5\x8c\xe0\xa4\x82 : '
            b'\xe0\xa4\xac\xe0\xa4\xbf\xe0\xa4\xb9\xe0\xa5\x80\xe0\xa4\xac\xe0\xa4\xbe\xe0\xa4\xb0 \xe0\xa4\xb8\xe0\xa5\x87\xe0\xa4\xaf\xe0\xa4\xb0 '
            b'\xe0\xa4\xac\xe0\xa4\x9c\xe0\xa4\xbe\xe0\xa4\xb0 \xe0\xa4\xaa\xe0\xa4\xb0\xe0\xa4\xbf\xe0\xa4\xb8\xe0\xa5\x82\xe0\xa4\x9a\xe0\xa4\x95 '
            b'\xe0\xa4\xa8\xe0\xa5\x87\xe0\xa4\xaa\xe0\xa5\x8d\xe0\xa4\xb8\xe0\xa5\x87\xe0\xa4\xae\xe0\xa4\xbe \xe0\xa4\xb8\xe0\xa4\xbe\xe0\xa4\xae\xe0\xa4\xbe\xe0\xa4\xa8\xe0\xa5\x8d\xe0\xa4\xaf '
            b'\xe0\xa4\xb8\xe0\xa5\x81\xe0\xa4\xa7\xe0\xa4\xbe\xe0\xa4\xb0 \xe0\xa4\xa6\xe0\xa5\x87\xe0\xa4\x96\xe0\xa4\xbf\xe0\xa4\x8f\xe0\xa4\x95\xe0\xa5\x8b \xe0\xa4\x9b\xe0\xa5\xa4</p>'
            b'</div></body></html>'
        )
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = mock_ap_html
        mock_resp.__enter__.return_value = mock_resp
        fetcher.FULL_ARTICLE_TEXT_CACHE.pop("https://annapurnapost.com/story/511589/", None)
        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            extracted = fetcher.extract_article_full_text("https://annapurnapost.com/story/511589/")
            self.assertIn("नेप्सेमा सामान्य सुधार", extracted)

        with mock.patch("nepal_news_store.hydrate_article_full_content", return_value=None), \
             mock.patch("nepal_fetcher.extract_article_full_text", return_value="काठमाडौं : बिहीबार सेयर बजार परिसूचक नेप्सेमा सामान्य सुधार देखिएको छ।"):
            rd = summ.extract_on_demand_full_article(art, translate_to_english=False)
        self.assertTrue(rd["ok"])
        self.assertEqual(rd["source_url"], "https://annapurnapost.com/story/511589/")
        self.assertIn("नेप्सेमा सामान्य सुधार", rd["original_text"])

        # 4) Tweet without external article link falls back cleanly to X permalink and still opens in Read modal
        art_no_link = fetcher.build_x_bridged_article(
            portal=ap_cfg,
            tweet_id="2123350000000000001",
            raw_text="संसद बैठक भोलि दिउँसो १ बजेसम्मका लागि स्थगित #NepalParliament",
            published_dt_raw="2026-11-19T10:00:00.000Z",
            now_npt=now_npt,
        )
        self.assertIsNotNone(art_no_link)
        self.assertEqual(art_no_link["link"], "https://x.com/Annapurna_Post/status/2123350000000000001")
        with mock.patch("nepal_news_store.hydrate_article_full_content", return_value=None), \
             mock.patch("nepal_fetcher.extract_article_full_text", return_value=""):
            rd2 = summ.extract_on_demand_full_article(art_no_link, translate_to_english=False)
        self.assertTrue(rd2["ok"])

        # 5) Naya Patrika x_bridge (@NAYA_PATRIKA): resolves nayapatrikadaily.com, strips '| Naya Patrika News',
        #    keeps direct full-text scraping enabled via .content__para, and yields clean Read/Brief parity
        np_cfg = next(p for p in cfg.TOP_NEPAL_NEWS_PORTALS if p["name"] == "Naya Patrika")
        self.assertEqual(np_cfg["type"], "x_bridge")
        self.assertEqual(np_cfg["x_handle"], "NAYA_PATRIKA")
        self.assertEqual(np_cfg["target_domain"], "nayapatrikadaily.com")
        self.assertFalse(fetcher._is_direct_scrape_skipped("https://nayapatrikadaily.com/news/208805/permission-to-sell-594-mw-electricity-to/"))

        np_art = fetcher.build_x_bridged_article(
            portal=np_cfg,
            tweet_id="2123361663248457903",
            raw_text="कीर्तिपुरबाट ११ लाखको काजु बरामद | Naya Patrika News https://t.co/BlCAjoG9DP",
            published_dt_raw="2026-11-19T10:24:05.000Z",
            now_npt=now_npt,
            expanded_urls=["https://nayapatrikadaily.com/news/208803/cashew-smuggling/"],
            card_title="कीर्तिपुरबाट ११ लाखको काजु बरामद | Naya Patrika News",
            card_description="काठमाडौं/ बिना बिलबिजक ओसारपसार भइरहेको ११ लाख ५९ हजार २०० रुपैयाँ बराबरको काजु बरामद।",
        )
        self.assertIsNotNone(np_art)
        self.assertEqual(np_art["source"], "Naya Patrika")
        self.assertEqual(np_art["title"], "कीर्तिपुरबाट ११ लाखको काजु बरामद")
        self.assertEqual(np_art["link"], "https://nayapatrikadaily.com/news/208803/cashew-smuggling/")
        self.assertEqual((np_art["published_dt"].hour, np_art["published_dt"].minute), (16, 9))

        # Verify .content__para is prioritized ahead of unrelated sidebar <article> cards
        fake_np_html = (
            "<html><body>"
            "<article><p>Unrelated sidebar trending snippet that must not win over main body container.</p></article>"
            "<div class='detail__page-content'><div class='content__para'>"
            "<p>काठमाडौं । विनाबिलबिजक ओसारपसार भइरहेको ११ लाख ५९ हजार दुई सय रुपैयाँबराबरको काजु कीर्तिपुरबाट बरामद भएको छ।</p>"
            "<p>सशस्त्र प्रहरीले बिहीबार बिहान चोभारस्थित सुक्खा बन्दरगाहको बाटो हुँदै ल्याउँदै गरेको अवस्थामा बरामद गरेको हो।</p>"
            "</div></div></body></html>"
        ).encode("utf-8")

        class _NPResp:
            def read(self):
                return fake_np_html
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        fetcher.FULL_ARTICLE_TEXT_CACHE.pop(np_art["link"], None)
        with mock.patch("urllib.request.urlopen", return_value=_NPResp()):
            extracted_np = fetcher.extract_article_full_text(np_art["link"], timeout=5)
        self.assertIn("विनाबिलबिजक ओसारपसार", extracted_np)
        self.assertNotIn("Unrelated sidebar", extracted_np)

        # 6) TechPana (@TechPanaNP) RSS + X-Boost config & The Himalayan Times (@TheHimalayan) x_bridge config + headline/hashtag parsing
        tp_cfg = next(p for p in cfg.TOP_NEPAL_NEWS_PORTALS if p["name"] == "TechPana")
        tht_cfg = next(p for p in cfg.TOP_NEPAL_NEWS_PORTALS if p["name"] == "The Himalayan Times")
        self.assertEqual((tp_cfg["type"], tp_cfg["x_boost_handle"]), ("rss", "TechPanaNP"))
        self.assertEqual((tht_cfg["type"], tht_cfg["x_handle"]), ("x_bridge", "TheHimalayan"))

        tp_art = fetcher.build_x_bridged_article(
            portal=tp_cfg,
            tweet_id="2123358930244133185",
            raw_text="उत्तर कोरियाले आफ्नै एआई च्याटबट सार्वजनिक गरेको छ । ‘एआई सर्भिस सिस्टम १.०’ नाम दिइएको यो च्याटबटले प्रश्नको उत्तर दिन्छ । https://t.co/abc",
            published_dt_raw="2026-11-19T10:13:13.000Z",
            now_npt=now_npt,
            expanded_urls=["https://techpana.com/2026/160072/north-korea-ai-chatbot"],
        )
        self.assertIsNotNone(tp_art)
        self.assertEqual(tp_art["link"], "https://techpana.com/2026/160072/north-korea-ai-chatbot")
        self.assertTrue(tp_art["title"].endswith("सार्वजनिक गरेको छ।"))
        self.assertIn("एआई सर्भिस सिस्टम", tp_art["summary"])

        tht_art = fetcher.build_x_bridged_article(
            portal=tht_cfg,
            tweet_id="2123369951738429879",
            raw_text="#Sports\nNSC lifts ANFA suspension and all administrative restrictions\nhttps://t.co/n5hGElHwQC",
            published_dt_raw="2026-11-19T10:57:01.000Z",
            now_npt=now_npt,
            expanded_urls=["https://thehimalayantimes.com/sports/anfa-suspension-lifted"],
            card_title="NSC lifts ANFA suspension and all administrative restrictions",
            card_description="The National Sports Council has lifted the suspension and restrictions.",
        )
        self.assertIsNotNone(tht_art)
        self.assertEqual(tht_art["title"], "NSC lifts ANFA suspension and all administrative restrictions")
        self.assertNotIn("#Sports", tht_art["summary"])
        self.assertEqual(tht_art["link"], "https://thehimalayantimes.com/sports/anfa-suspension-lifted")

        # 7) NepalKhabar 6-part URL timestamp slug (UTC in RSS feed -> NPT, NPT in social URL -> NPT)
        nk_now = datetime.datetime(2026, 11, 19, 16, 50, 0, tzinfo=cfg.NEPAL_TZ)
        nk_rss_u = "https://nepalkhabar.com/sports/291968-2026-11-19-11-2-58"
        nk_npt_u = "https://nepalkhabar.com/sports/291968-2026-11-19-16-47-58"
        fetcher.ARTICLE_DATE_CACHE.pop(nk_rss_u, None)
        fetcher.ARTICLE_DATE_CACHE.pop(nk_npt_u, None)
        with mock.patch("urllib.request.urlopen") as m_open:
            dt_from_utc_slug = fetcher.extract_date_from_card_or_url(None, nk_rss_u, nk_now)
            dt_from_npt_slug = fetcher.extract_date_from_card_or_url(None, nk_npt_u, nk_now)
            m_open.assert_not_called()
        self.assertEqual((dt_from_utc_slug.hour, dt_from_utc_slug.minute, dt_from_utc_slug.second), (16, 47, 58))
        self.assertEqual((dt_from_npt_slug.hour, dt_from_npt_slug.minute, dt_from_npt_slug.second), (16, 47, 58))

    def test_english_brief_whatsapp_format_and_reader_headline_translation_copy(self):
        import nepal_summarizer as summ

        # 1) Nepali article -> English Brief contains bold English headline + brief + direct link
        ne_item = {
            "source": "eKantipur",
            "language": "Nepali",
            "title": "विपद् पुनर्वासको असफल शृंखला : भोटेकोशीमा पनि दोहोरिएला कि सुधारिएला ?",
            "summary": "विपद्पछि पुनर्वास योजना लगातार असफल हुँदा सर्वसाधारण जोखिमपूर्ण स्थानमा बस्न बाध्य छन्।",
            "full_content": (
                "विपद्पछि पुनर्वास योजना लगातार असफल हुँदा सर्वसाधारण जोखिमपूर्ण स्थानमा बस्न बाध्य छन्।\n\n"
                "सरकारले २०५० सालको बाढी र २०७२ को भूकम्पपछि पनि प्रभावकारी व्यवस्थापन गर्न सकेन।"
            ),
            "link": "https://ekantipur.com/news/2026/11/19/bhotekoshi-rehab.html",
        }

        def _fake_translate(txt, **kw):
            if "भोटेकोशी" in txt and "शृंखला" in txt:
                return "Failed Series of Disaster Rehabilitation: Will It Repeat in Bhotekoshi?"
            if "२०५०" in txt:
                return "The government failed to manage rehabilitation effectively after the 2050 flood and 2072 earthquake."
            return "Post-disaster rehabilitation plans keep failing, forcing citizens to live in risky areas."

        with mock.patch("nepal_news_store.hydrate_article_full_content", return_value=None), \
             mock.patch("nepal_fetcher.extract_article_full_text", return_value=""), \
             mock.patch("nepal_summarizer._translate_ne_to_en", side_effect=_fake_translate):
            brief_ne = summ.generate_on_demand_news_brief(ne_item)

        self.assertTrue(brief_ne["ok"])
        self.assertEqual(brief_ne["headline_english"], "Failed Series of Disaster Rehabilitation: Will It Repeat in Bhotekoshi?")
        self.assertIn("*Failed Series of Disaster Rehabilitation: Will It Repeat in Bhotekoshi?*\n\n", brief_ne["formatted_text"])
        self.assertIn("\n\nRead Original Source: https://ekantipur.com/news/2026/11/19/bhotekoshi-rehab.html", brief_ne["formatted_text"])
        self.assertEqual(len(brief_ne["formatted_text"].split("\n\n")), 3)

        # 2) English article (Indian Press / English Nepali Media) -> same 3-part WhatsApp format
        en_item = {
            "source": "The Hindu",
            "language": "English",
            "title": "India and Nepal review cross-border power transmission lines",
            "summary": "Officials from New Delhi and Kathmandu reviewed bilateral hydropower corridors and grid interconnectivity.",
            "full_content": (
                "Officials from New Delhi and Kathmandu reviewed bilateral hydropower corridors and grid interconnectivity "
                "during the annual energy secretary meeting. Both sides agreed to accelerate the 400 kV transmission link."
            ),
            "link": "https://www.thehindu.com/news/international/india-nepal-power.ece",
        }
        with mock.patch("nepal_news_store.hydrate_article_full_content", return_value=None), \
             mock.patch("nepal_fetcher.extract_article_full_text", return_value=""):
            brief_en = summ.generate_on_demand_news_brief(en_item)

        self.assertTrue(brief_en["ok"])
        self.assertEqual(brief_en["headline_english"], "India and Nepal review cross-border power transmission lines")
        parts_en = brief_en["formatted_text"].split("\n\n")
        self.assertEqual(len(parts_en), 3)
        self.assertEqual(parts_en[0], "*India and Nepal review cross-border power transmission lines*")
        self.assertTrue(len(parts_en[1]) > 20)
        self.assertEqual(parts_en[2], "Read Original Source: https://www.thehindu.com/news/international/india-nepal-power.ece")

        # 3) In-App Reader translates headline AND full body, and single-click Copy formats Headline + Body + Link
        with mock.patch("nepal_news_store.hydrate_article_full_content", return_value=None), \
             mock.patch("nepal_fetcher.extract_article_full_text", return_value=""), \
             mock.patch("nepal_summarizer._translate_ne_to_en", side_effect=_fake_translate):
            rd_tr = summ.extract_on_demand_full_article(ne_item, translate_to_english=True)

        self.assertTrue(rd_tr["ok"])
        self.assertEqual(rd_tr["original_title"], ne_item["title"])
        self.assertEqual(rd_tr["translated_title"], "Failed Series of Disaster Rehabilitation: Will It Repeat in Bhotekoshi?")
        self.assertIn("Post-disaster rehabilitation plans keep failing", rd_tr["translated_text"])
        self.assertIn("2050 flood and 2072 earthquake", rd_tr["translated_text"])

        copy_payload = summ.format_reader_copy_payload(
            headline=rd_tr["translated_title"],
            full_body=rd_tr["translated_text"],
            source_url=rd_tr["source_url"],
        )
        self.assertTrue(copy_payload.startswith("Failed Series of Disaster Rehabilitation: Will It Repeat in Bhotekoshi?\n\n"))
        self.assertIn("2050 flood and 2072 earthquake", copy_payload)
        self.assertTrue(copy_payload.endswith("\n\nRead Original Source: https://ekantipur.com/news/2026/11/19/bhotekoshi-rehab.html"))

        # 4) Hindi Indian Press article -> 3-part English Brief + Read modal English headline translation & Copy
        hi_item = {
            "source": "Amar Ujala",
            "language": "Hindi",
            "title": "नेपाल सीमा पर सुरक्षा व्यवस्था और कड़ी की गई",
            "summary": "सोनौली और रक्सौल सीमा पर अतिरिक्त सुरक्षा बल तैनात किए गए हैं।",
            "full_content": (
                "सोनौली और रक्सौल सीमा पर अतिरिक्त सुरक्षा बल तैनात किए गए हैं।\n\n"
                "अधिकारियों ने दोनों देशों के बीच समन्वय बैठक की।"
            ),
            "link": "https://www.amarujala.com/uttar-pradesh/nepal-border-security",
        }

        def _fake_hi_translate(txt, **kw):
            if "सुरक्षा व्यवस्था" in txt:
                return "Security arrangements tightened further along Nepal border"
            if "समन्वय बैठक" in txt:
                return "Officials held a coordination meeting between the two countries."
            return "Additional security forces have been deployed at Sunauli and Raxaul borders."

        with mock.patch("nepal_news_store.hydrate_article_full_content", return_value=None), \
             mock.patch("nepal_fetcher.extract_article_full_text", return_value=""), \
             mock.patch("nepal_summarizer._translate_ne_to_en", side_effect=_fake_hi_translate):
            brief_hi = summ.generate_on_demand_news_brief(hi_item)
            rd_hi = summ.extract_on_demand_full_article(hi_item, translate_to_english=True)

        self.assertTrue(brief_hi["ok"])
        parts_hi = brief_hi["formatted_text"].split("\n\n")
        self.assertEqual(len(parts_hi), 3)
        self.assertEqual(parts_hi[0], "*Security arrangements tightened further along Nepal border*")
        self.assertEqual(parts_hi[2], "Read Original Source: https://www.amarujala.com/uttar-pradesh/nepal-border-security")

        self.assertTrue(rd_hi["ok"])
        self.assertEqual(rd_hi["translated_title"], "Security arrangements tightened further along Nepal border")
        hi_copy = summ.format_reader_copy_payload(
            headline=rd_hi["translated_title"],
            full_body=rd_hi["translated_text"],
            source_url=rd_hi["source_url"],
            whatsapp_bold=False,
        )
        self.assertTrue(hi_copy.startswith("Security arrangements tightened further along Nepal border\n\n"))
        self.assertIn("coordination meeting", hi_copy)
        self.assertTrue(hi_copy.endswith("\n\nRead Original Source: https://www.amarujala.com/uttar-pradesh/nepal-border-security"))

        # Verify 3-part WhatsApp payload from reader with bold headline
        hi_wa = summ.format_reader_copy_payload(
            headline=rd_hi["translated_title"],
            full_body=rd_hi["translated_text"],
            source_url=rd_hi["source_url"],
            whatsapp_bold=True,
        )
        self.assertTrue(hi_wa.startswith("*Security arrangements tightened further along Nepal border*\n\n"))
        self.assertIn("coordination meeting", hi_wa)
        self.assertTrue(hi_wa.endswith("\n\nRead Original Source: https://www.amarujala.com/uttar-pradesh/nepal-border-security"))

    def test_indian_media_classifier_boundaries_entities_and_placeholder_ts_repair(self):
        import nepal_config as cfg
        import nepal_fetcher as fetcher
        import nepal_news_store as store

        # 1) url_has_nepal strict slug boundaries: police / politics / foolish must NOT match 'oli'
        ev_police = fetcher.evaluate_indian_article_nepal_relevance(
            title="UP Police bust cyber fraud network across Lucknow",
            summary="Uttar Pradesh police arrested one suspect in a cyber fraud case.",
            link="https://timesofindia.indiatimes.com/city/lucknow/sonbhadra-police-bust-cyber-fraud",
            source="The Times of India",
        )
        self.assertEqual(ev_police["relevance_status"], "excluded")
        self.assertEqual(ev_police["nepal_relevance_score"], 0.0)

        ev_foolish = fetcher.evaluate_indian_article_nepal_relevance(
            title="Musk says he feels pretty foolish for failed U.S. election spending",
            summary="Billionaire reflects on campaign spending in U.S. politics.",
            link="https://www.thehindu.com/news/international/musk-feels-pretty-foolish-politics/article123.ece",
            source="The Hindu",
        )
        self.assertEqual(ev_foolish["relevance_status"], "excluded")
        self.assertEqual(ev_foolish["nepal_relevance_score"], 0.0)

        ev_oli_slug = fetcher.evaluate_indian_article_nepal_relevance(
            title="Bilateral talks review cross-border energy trade and transit",
            summary="Senior officials met on regional connectivity and power trade.",
            link="https://www.thehindu.com/news/international/kp-oli-india-energy-talks/article999.ece",
            source="The Hindu",
        )
        self.assertGreater(ev_oli_slug["nepal_relevance_score"], 0.0)
        self.assertIn("Nepal in article URL slug", ev_oli_slug["relevance_reason"])

        # 2) Expanded _NEPAL_CORE_SUBJECT_RE (Gorkha, Pokhara, Hindi cricket with Nepal in headline)
        ev_gorkha = fetcher.evaluate_indian_article_nepal_relevance(
            title="Agnipath Debate: 6-Year Tenure, Gorkha Recruitment & India's Military Preparedness",
            summary="Defence experts discuss Gorkha rifles recruitment and bilateral defence ties.",
            link="https://www.indiatoday.in/india/story/agnipath-gorkha-recruitment",
            source="India Today",
        )
        self.assertEqual(ev_gorkha["relevance_status"], "substantive")
        self.assertGreaterEqual(ev_gorkha["nepal_relevance_score"], 0.65)

        ev_pokhara = fetcher.evaluate_indian_article_nepal_relevance(
            title="Pokhara international airport talks advance with regional aviation ministry",
            summary="Bilateral aviation connectivity and air route expansion discussed.",
            link="https://www.theprint.in/diplomacy/pokhara-airport-talks/",
            source="The Print",
        )
        self.assertEqual(ev_pokhara["relevance_status"], "substantive")

        ev_hi_cricket = fetcher.evaluate_indian_article_nepal_relevance(
            title="Rising Stars Asia Cup: नेपाल के खिलाफ ऐसी हो सकती है भारत की क्रिकेट टीम",
            summary="एशिया कप में नेपाल के खिलाफ भारत के मुकाबले को लेकर तैयारी तेज।",
            link="https://navbharattimes.indiatimes.com/sports/cricket/india-vs-nepal-asia-cup",
            source="Navbharat Times",
        )
        self.assertEqual(ev_hi_cricket["relevance_status"], "substantive")
        self.assertNotIn("Penalized: domestic Indian", ev_hi_cricket["relevance_reason"])

        # 3) Tag landing pages are cleanly rejected
        ev_tag = fetcher.evaluate_indian_article_nepal_relevance(
            title="Nepal Foreign Students News and Updates",
            summary="Latest news on Nepal foreign students.",
            link="https://education.economictimes.indiatimes.com/tag/nepal+foreign+students",
            source="The Economic Times",
        )
        self.assertEqual(ev_tag["relevance_status"], "excluded")
        self.assertIn("Index/tag landing", ev_tag["relevance_reason"])

        # 4) New high-yield Indian wires are registered in TOP_INDIAN_MEDIA_SOURCES
        ind_names = {s["name"] for s in cfg.TOP_INDIAN_MEDIA_SOURCES}
        for req_name in ("ANI News", "PTI", "The Print", "The Wire", "WION", "Firstpost", "Deccan Herald", "News18", "Aaj Tak", "Dainik Bhaskar"):
            self.assertIn(req_name, ind_names)

        # 5) batch_upsert_indian_articles upgrades 00:00:00 / 12:00:00 placeholder published_dt on conflict
        captured_sql = []
        with mock.patch("nepal_news_store.query_supabase", side_effect=lambda sql, params=None: captured_sql.append(sql) or []):
            store.batch_upsert_indian_articles([{
                "source": "India Today",
                "title": "India and Nepal review border connectivity projects",
                "link": "https://www.indiatoday.in/world/story/india-nepal-border-1",
                "summary": "Officials reviewed cross-border projects.",
                "full_content": "Officials reviewed cross-border projects between India and Nepal.",
                "published_dt": datetime.datetime(2026, 11, 19, 14, 35, 0, tzinfo=cfg.NEPAL_TZ),
                "relative_time": "10 mins ago",
                "exact_time": "Nov 19, 02:35 PM NPT",
                "nepal_relevance_score": 0.85,
                "relevance_status": "substantive",
            }])
        self.assertTrue(captured_sql)
        self.assertIn("EXTRACT(HOUR FROM indian_media_articles.published_dt) IN (0, 12)", captured_sql[0])
        self.assertIn("EXTRACT(MINUTE FROM indian_media_articles.published_dt) = 0", captured_sql[0])

        # 6) record_indian_source_health persists UTC-aware timestamps & status
        health_sql = []
        store._INDIAN_HEALTH_TABLE_READY = True
        with mock.patch("nepal_news_store.query_supabase", side_effect=lambda sql, params=None: health_sql.append(sql) or []):
            cnt = store.record_indian_source_health([
                {"source_name": "ANI News", "source_type": "search_rss", "domain": "aninews.in", "language": "English", "discovered": 8, "substantive": 7, "borderline": 1, "excluded": 0, "latency_secs": 1.2, "error": ""},
                {"source_name": "Broken Outlet", "source_type": "topic_html", "domain": "broken.in", "language": "English", "discovered": 0, "substantive": 0, "borderline": 0, "excluded": 0, "latency_secs": 2.0, "error": "HTTPError: 403"},
            ])
        self.assertEqual(cnt, 2)
        self.assertIn("INSERT INTO indian_source_health", health_sql[0])
        self.assertIn("'operational'", health_sql[0])
        self.assertIn("'failing'", health_sql[0])
        self.assertIn("+00:00", health_sql[0])

    def test_dual_feed_x_boost_filtering_and_inplace_url_reconciliation(self):
        import nepal_config as cfg
        import nepal_fetcher as fetcher
        import nepal_news_store as store
        from nepal_verified_x_directory import DIRECTORY_BY_HANDLE

        # 1) All 6 top portals keep RSS/HTML primary config + verified x_boost_handle
        expected_boosts = {
            "eKantipur": ("html", "ekantipur_com"),
            "OnlineKhabar (NP)": ("rss", "Online_khabar"),
            "Setopati": ("rss", "Setopati"),
            "Ratopati": ("rss", "Rato_pati"),
            "Nagarik News": ("rss", "nagarik_news"),
            "The Kathmandu Post": ("rss", "kathmandupost"),
        }
        portals_by_name = {p["name"]: p for p in cfg.TOP_NEPAL_NEWS_PORTALS}
        for pname, (ptype, handle) in expected_boosts.items():
            pcfg = portals_by_name[pname]
            self.assertEqual(pcfg["type"], ptype)
            self.assertEqual(pcfg.get("x_boost_handle"), handle)
            self.assertTrue(pcfg.get("url"))
            self.assertIn(handle.lower(), DIRECTORY_BY_HANDLE)

        now_npt = datetime.datetime(2026, 11, 20, 12, 0, 0, tzinfo=cfg.NEPAL_TZ)

        # 2) boost_x_portals_to_articles filters non-article, >24h path-date, and already-ingested URLs
        tco_map = {
            "https://t.co/fresh1": "https://ekantipur.com/business/2026/11/20/hydropower-deal-594mw.html",
            "https://t.co/old1": "https://ekantipur.com/news/2026/11/17/archive-story.html",
            "https://t.co/sec1": "https://ekantipur.com/politics",
            "https://t.co/already1": "https://www.onlinekhabar.com/2026/11/2061671/already-ingested",
        }
        fetcher.TCO_REDIRECT_CACHE.clear()

        def _fake_resolve(u, timeout=4.0, allow_redirects=False):
            self.assertFalse(allow_redirects)
            return tco_map.get(u, u)

        x_posts = [
            {
                "id": "9001",
                "raw_handle": "ekantipur_com",
                "text": "सेयर बजार नेप्से परिसूचकमा ५९ अंकको उछाल, कारोबार रकम ६ अर्ब नाघ्यो #NEPSE https://t.co/fresh1",
                "published_dt": now_npt - datetime.timedelta(minutes=3),
            },
            {
                "id": "9002",
                "raw_handle": "ekantipur_com",
                "text": "पुरानो संग्रह समाचार फेरि सेयर https://t.co/old1",
                "published_dt": now_npt - datetime.timedelta(minutes=5),
            },
            {
                "id": "9003",
                "raw_handle": "ekantipur_com",
                "text": "राजनीति खण्ड हेर्नुहोस् https://t.co/sec1",
                "published_dt": now_npt - datetime.timedelta(minutes=4),
            },
            {
                "id": "9004",
                "raw_handle": "Online_khabar",
                "text": "पहिले नै आइसकेको समाचार https://t.co/already1",
                "published_dt": now_npt - datetime.timedelta(minutes=2),
            },
            {
                "id": "9005",
                "raw_handle": "Setopati",
                "text": "लिंक नभएको ट्विट मात्र",
                "published_dt": now_npt - datetime.timedelta(minutes=1),
            },
        ]

        captured_upserts = []
        existing_db = {
            "https://www.onlinekhabar.com/2026/11/2061671/already-ingested": "existing_ok_cid"
        }
        with mock.patch("nepal_fetcher.resolve_tco_url", side_effect=_fake_resolve), \
             mock.patch("nepal_fetcher.get_existing_article_urls", return_value=existing_db) as m_exist, \
             mock.patch("nepal_fetcher.batch_fetch_full_content"), \
             mock.patch("nepal_fetcher.batch_upsert_articles", side_effect=lambda arts, sname, **kw: captured_upserts.append((sname, arts, kw)) or {"ingested": len(arts)}) as m_up:
            boosted_cnt = fetcher.boost_x_portals_to_articles(x_posts=x_posts, now_npt=now_npt)

        self.assertEqual(boosted_cnt, 1)
        m_exist.assert_called_once()
        self.assertEqual(len(captured_upserts), 1)
        sname, b_arts, b_kw = captured_upserts[0]
        self.assertEqual(sname, "eKantipur")
        self.assertTrue(b_kw.get("is_x_boost"))
        self.assertEqual(len(b_arts), 1)
        self.assertEqual(b_arts[0]["link"], "https://ekantipur.com/business/2026/11/20/hydropower-deal-594mw.html")
        self.assertEqual(b_arts[0]["primary_section"], "Nepal – Economy")
        self.assertIn("Economy & Finance", b_arts[0]["secondary_tags"])

        # 3) batch_upsert_articles skips existing URLs on is_x_boost=True AND reconciles/upgrades in place on RSS/HTML
        article_url = "https://ekantipur.com/business/2026/11/20/hydropower-deal-594mw.html"
        norm_url = store.normalize_canonical_url(article_url)
        x_cid = store.generate_canonical_id("eKantipur", norm_url, "ट्विट क्याप्सन")

        # 3a) X-boost skips when URL already exists in Supabase
        with mock.patch("nepal_news_store.get_existing_article_urls", return_value={norm_url: x_cid}), \
             mock.patch("nepal_news_store.query_supabase") as m_q:
            skip_res = store.batch_upsert_articles([b_arts[0]], "eKantipur", is_x_boost=True)
        self.assertEqual(skip_res["ingested"], 0)
        self.assertEqual(skip_res["duplicates"], 1)
        m_q.assert_not_called()

        # 3b) RSS/HTML arrival with different official title + tracking query reconciles to existing canonical_id in place
        rss_art = {
            "source": "eKantipur",
            "title": "भारतको ऊर्जा एक्सचेन्जमा ५९४ मेगावाट विद्युत् निर्यात स्वीकृत",
            "link": article_url + "?utm_source=rss",
            "summary": "नेपाल र भारतबीच ५९४ मेगावाट विद्युत् व्यापार सम्झौता कार्यान्वयनमा आएको छ।",
            "full_content": "विस्तृत आधिकारिक समाचार: नेपाल र भारतबीच ५९४ मेगावाट विद्युत् व्यापार सम्झौता आजदेखि कार्यान्वयनमा आएको ऊर्जा मन्त्रालयले जनाएको छ।",
            "published_dt": datetime.datetime(2026, 11, 20, 11, 56, 12, tzinfo=cfg.NEPAL_TZ),
            "relative_time": "3 mins ago",
            "exact_time": "Nov 20, 11:56 AM NPT",
            "language": "Nepali",
            "portal_category": "National Daily",
            "primary_section": "Nepal – Economy",
            "sections": ["Nepal – Economy"],
            "secondary_tags": ["Economy & Finance", "India"],
            "classification_confidence": 0.92,
        }
        sql_calls = []
        with mock.patch("nepal_news_store.get_existing_article_urls", return_value={norm_url: x_cid}), \
             mock.patch("nepal_news_store.query_supabase", side_effect=lambda sql, params=None: sql_calls.append(sql) or []):
            up_res = store.batch_upsert_articles([rss_art], "eKantipur", latency_secs=0.45, is_x_boost=False)

        self.assertEqual(up_res["updated"], 1)
        self.assertEqual(up_res["ingested"], 0)
        self.assertTrue(sql_calls)
        self.assertIn(f"'{x_cid}'", sql_calls[0], "RSS upgrade must reuse existing canonical_id instead of inserting duplicate row")
        self.assertIn("ON CONFLICT (canonical_id) DO UPDATE SET", sql_calls[0])
        self.assertIn("articles.title IS DISTINCT FROM EXCLUDED.title", sql_calls[0])

    def test_operational_polish_stale_detector_staggering_and_x_bridge_guard(self):
        import nepal_config as cfg
        import nepal_fetcher as fetcher
        import nepal_news_scheduler as sched
        import nepal_news_store as store

        now_npt = datetime.datetime(2026, 11, 20, 12, 0, 0, tzinfo=cfg.NEPAL_TZ)

        # 1) Stale 200 OK detector flags enabled high/standard portals >24h old, ignores low/disabled/fresh
        self.assertTrue(store.is_portal_stale({
            "name": "NepalKhabar (EN)",
            "enabled": 1,
            "priority": "standard",
            "status": "operational",
            "latest_article_pub_dt": now_npt - datetime.timedelta(hours=30),
        }, now_npt=now_npt))
        self.assertFalse(store.is_portal_stale({
            "name": "Setopati",
            "enabled": 1,
            "priority": "high",
            "status": "operational",
            "latest_article_pub_dt": now_npt - datetime.timedelta(hours=2),
        }, now_npt=now_npt))
        self.assertFalse(store.is_portal_stale({
            "name": "The Annapurna Express",
            "enabled": 1,
            "priority": "low",
            "status": "operational",
            "latest_article_pub_dt": now_npt - datetime.timedelta(hours=48),
        }, now_npt=now_npt))
        self.assertFalse(store.is_portal_stale({
            "name": "Disabled Portal",
            "enabled": 0,
            "priority": "high",
            "status": "operational",
            "latest_article_pub_dt": now_npt - datetime.timedelta(hours=48),
        }, now_npt=now_npt))

        # 2) Scheduler staggering: cold start runs neither Indian nor X immediately, offset by 6 minutes;
        #    and if both become overdue simultaneously, only one fires per tick.
        t0 = 1_000_000.0
        r_ind, r_x, next_ind, next_x = sched._compute_staggered_due_streams(t0, 0.0, 0.0)
        self.assertFalse(r_ind)
        self.assertFalse(r_x)
        self.assertAlmostEqual((next_x - next_ind), sched.STREAM_STAGGER_SECS, delta=1.0)

        # Simulate long pause where both 15m streams are overdue -> only one runs on this tick
        r_ind2, r_x2, adj_ind2, adj_x2 = sched._compute_staggered_due_streams(
            t0 + 5000.0, t0 + 1000.0, t0 + 1500.0
        )
        self.assertTrue(r_ind2)
        self.assertFalse(r_x2)
        self.assertGreater(adj_x2, t0 + 5000.0 - sched.X_SCAN_INTERVAL_SECS)

        # 3) x_bridge freshness guard skips live profile scraping when x_posts was synced <5 mins ago
        ap_cfg = next(p for p in cfg.TOP_NEPAL_NEWS_PORTALS if p["name"] == "Annapurna Post")
        recent_utc = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=2)
        db_row = {
            "id": "2123350203076133335",
            "raw_handle": "Annapurna_Post",
            "text": "ताजा समाचार अपडेट https://annapurnapost.com/story/511589/",
            "title": "ताजा समाचार अपडेट",
            "link": "https://x.com/Annapurna_Post/status/2123350203076133335",
            "published_dt": recent_utc,
            "updated_at": recent_utc,
        }
        with mock.patch("nepal_news_store.query_supabase", return_value=[db_row]), \
             mock.patch("nepal_x_scanner._discover_profile_tweet_candidates") as m_prof_disc, \
             mock.patch("nepal_x_scanner._get_x_http_session") as m_sess:
            m_sess.return_value.get.return_value.status_code = 404
            res_arts = fetcher.fetch_x_bridged_portal_articles(ap_cfg, now_npt, max_entries=10)
        m_prof_disc.assert_not_called()
        self.assertEqual(len(res_arts), 1)
        self.assertEqual(res_arts[0]["source"], "Annapurna Post")

    def test_portal_extraction_cleaning_and_boilerplate_stripping(self):
        import nepal_fetcher as fetcher

        # 1. Annapurna Post: extracted via .news__details without being blocked
        ap_html = b"""<html><body>
            <div class="news__details">
                <p>Annapurna Post main paragraph 1.</p>
                <p>Annapurna Post main paragraph 2.</p>
            </div>
        </body></html>"""
        m_resp = mock.MagicMock()
        m_resp.read.return_value = ap_html
        m_resp.__enter__.return_value = m_resp
        fetcher.FULL_ARTICLE_TEXT_CACHE.clear()
        with mock.patch("urllib.request.urlopen", return_value=m_resp):
            txt = fetcher.extract_article_full_text("https://annapurnapost.com/story/12345")
            self.assertIn("Annapurna Post main paragraph 1.", txt)
            self.assertIn("Annapurna Post main paragraph 2.", txt)

        # 2. Baahrakhari: decomposes .opinion-box, .trending-news, prioritizes .editor-box over .detail-box
        bh_html = b"""<html><body>
            <div class="detail-box">
                <div class="editor-box">
                    <p>Baahrakhari core story text.</p>
                </div>
                <div class="opinion-box"><p>Unrelated opinion text</p></div>
                <div class="trending-news"><p>Unrelated trending news</p></div>
            </div>
        </body></html>"""
        m_resp.read.return_value = bh_html
        fetcher.FULL_ARTICLE_TEXT_CACHE.clear()
        with mock.patch("urllib.request.urlopen", return_value=m_resp):
            txt = fetcher.extract_article_full_text("https://baahrakhari.com/news/12345")
            self.assertIn("Baahrakhari core story text.", txt)
            self.assertNotIn("Unrelated opinion text", txt)
            self.assertNotIn("Unrelated trending news", txt)

        # 3. Republica: selects .rep-body--regular, decomposes .rep-paywall
        rep_html = b"""<html><body>
            <div class="rep-article-container">
                <div class="rep-body--regular">
                    <p>Republica primary news story.</p>
                </div>
                <div class="rep-paywall"><p>Gain access to up to 10 free articles</p></div>
            </div>
        </body></html>"""
        m_resp.read.return_value = rep_html
        fetcher.FULL_ARTICLE_TEXT_CACHE.clear()
        with mock.patch("urllib.request.urlopen", return_value=m_resp):
            txt = fetcher.extract_article_full_text("https://myrepublica.nagariknetwork.com/news/12345")
            self.assertIn("Republica primary news story.", txt)
            self.assertNotIn("free articles", txt)

        # 4. Nepal Live: stops before email/feedback disclaimer and decomposes .related-stories
        nl_html = b"""<html><body>
            <div class="editor-box">
                <p>Nepal Live legitimate article body.</p>
                <div class="related-stories"><p>Unrelated sidebar carousel</p></div>
                <p>\xe0\xa4\xa8\xe0\xa5\x87\xe0\xa4\xaa\xe0\xa4\xbe\xe0\xa4\xb2\xe0\xa4\xb2\xe0\xa4\xbe\xe0\xa4\x87\xe0\xa4\xad\xe0\xa4\xae\xe0\xa4\xbe \xe0\xa4\xaa\xe0\xa5\x8d\xe0\xa4\xb0\xe0\xa4\x95\xe0\xa4\xbe\xe0\xa4\xb6\xe0\xa4\xbf\xe0\xa4\xa4 \xe0\xa4\xb8\xe0\xa4\xbe\xe0\xa4\xae\xe0\xa4\x97\xe0\xa5\x8d\xe0\xa4\xb0\xe0\xa5\x80\xe0\xa4\xac\xe0\xa4\xbe\xe0\xa4\xb0\xe0\xa5\x87 \xe0\xa4\x95\xe0\xa5\x81\xe0\xa4\xa8\xe0\xa5\x88 \xe0\xa4\x97\xe0\xa5\x81\xe0\xa4\xa8\xe0\xa4\xbe\xe0\xa4\xb8\xe0\xa5\x8b nepallivenews@gmail.com</p>
            </div>
        </body></html>"""
        m_resp.read.return_value = nl_html
        fetcher.FULL_ARTICLE_TEXT_CACHE.clear()
        with mock.patch("urllib.request.urlopen", return_value=m_resp):
            txt = fetcher.extract_article_full_text("https://nepallive.com/story/12345")
            self.assertIn("Nepal Live legitimate article body.", txt)
            self.assertNotIn("nepallivenews@gmail.com", txt)
            self.assertNotIn("Unrelated sidebar carousel", txt)

        # 5. Nepal News: selects #textToRead, stops before registration notice
        nn_html = b"""<html><body>
            <div id="textToRead">
                <p>Nepal News clean report.</p>
                <p>\xe0\xa4\xb8\xe0\xa5\x82\xe0\xa4\x9a\xe0\xa4\xa8\xe0\xa4\xbe \xe0\xa4\xad\xe0\xa4\xbf\xe0\xa4\xad\xe0\xa4\xbe\xe0\xa4\x97 \xe0\xa4\xa6\xe0\xa4\xb0\xe0\xa5\x8d\xe0\xa4\xa4\xe0\xa4\xbe \xe0\xa4\xa8\xe0\xa4\x82 : \xe0\xa5\xa8\xe0\xa5\xa7\xe0\xa5\xaa/\xe0\xa5\xa6\xe0\xa5\xad\xe0\xa5\xad-\xe0\xa5\xad\xe0\xa5\xae</p>
            </div>
        </body></html>"""
        m_resp.read.return_value = nn_html
        fetcher.FULL_ARTICLE_TEXT_CACHE.clear()
        with mock.patch("urllib.request.urlopen", return_value=m_resp):
            txt = fetcher.extract_article_full_text("https://nepalnews.com/s/12345")
            self.assertIn("Nepal News clean report.", txt)
            self.assertNotIn("\xe0\xa4\xa6\xe0\xa4\xb0\xe0\xa5\x8d\xe0\xa4\xa4\xe0\xa4\xbe", txt)

        # 6. TechPana: extracts full story from .content__desc and .news_detail-para
        tp_html = b"""<html><body>
            <div class="news__details">
                <div class="content__desc">
                    <p class="news_detail-para">TechPana in-depth technical story paragraph 1.</p>
                    <p class="news_detail-para">TechPana in-depth technical story paragraph 2.</p>
                </div>
            </div>
        </body></html>"""
        m_resp.read.return_value = tp_html
        fetcher.FULL_ARTICLE_TEXT_CACHE.clear()
        with mock.patch("urllib.request.urlopen", return_value=m_resp):
            txt = fetcher.extract_article_full_text("https://techpana.com/2026/160082/hamro-patro")
            self.assertIn("TechPana in-depth technical story paragraph 1.", txt)
            self.assertIn("TechPana in-depth technical story paragraph 2.", txt)

        # 7. Verify _needs_body_scrape triggers for RSS teaser blurbs (e.g. 556 chars) where full_content == summary
        import nepal_summarizer as summ
        teaser_art = {
            "title": "TechPana News Title",
            "summary": "Short 556-char RSS teaser description blurb without real article paragraphs.",
            "full_content": "Short 556-char RSS teaser description blurb without real article paragraphs.",
            "link": "https://techpana.com/2026/160082/sample",
        }
        self.assertTrue(summ._needs_body_scrape(teaser_art))

        # Real hydrated full article with 1,500 chars does not need body scrape
        full_art = {
            "title": "TechPana News Title",
            "summary": "Short summary",
            "full_content": "Long hydrated news article paragraph 1.\n\nParagraph 2.\n\nParagraph 3." * 25,
            "link": "https://techpana.com/2026/160082/sample",
        }
        self.assertFalse(summ._needs_body_scrape(full_art))


if __name__ == "__main__":
    unittest.main()
