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

        # 3) Direct scraping is skipped for annapurnapost.com and Read modal succeeds cleanly (ok=True)
        with mock.patch("urllib.request.urlopen") as m_open:
            self.assertEqual(fetcher.extract_article_full_text("https://annapurnapost.com/story/511589/"), "")
            m_open.assert_not_called()

        with mock.patch("nepal_news_store.hydrate_article_full_content", return_value=None):
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


if __name__ == "__main__":
    unittest.main()
