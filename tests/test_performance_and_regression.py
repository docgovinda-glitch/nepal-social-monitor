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


if __name__ == "__main__":
    unittest.main()
