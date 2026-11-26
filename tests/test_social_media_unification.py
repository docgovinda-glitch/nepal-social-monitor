"""
test_social_media_unification.py
Unit tests verifying the 1,000+ Social Media (Facebook + X) directory,
the news relevance filter, the 10-account circular batch ingestion,
and unified database store and retrieval.
"""

import unittest
from unittest import mock
import datetime

import nepal_config as cfg
import nepal_social_directory as sd
import nepal_social_scanner as scanner
import nepal_news_store as store
import nepal_x_scanner as xs
from nepal_config import NEPAL_TZ


class TestSocialMediaUnification(unittest.TestCase):

    def test_directory_volume_and_integrity(self):
        """Verifies curated directory keeps strictly the live 242 authentic accounts with zero duplicates."""
        accounts = sd.VERIFIED_NEPAL_SOCIAL_DIRECTORY
        self.assertEqual(len(accounts), 242, "Curated directory must match the live 242 accounts")
        self.assertEqual(sum(1 for a in accounts if a.get("platform") == "facebook"), 58)
        self.assertEqual(sum(1 for a in accounts if a.get("platform") == "x"), 184)

        # Verify zero duplicate (platform, handle) entries
        plat_handles = [(a.get("platform", "x").lower(), a.get("handle", "").lstrip("@").lower()) for a in accounts]
        self.assertEqual(len(plat_handles), len(set(plat_handles)), "Duplicate (platform, handle) found in directory")

        # Verify directory-only pruned handles and superseded Facebook duplicates are absent
        self.assertNotIn("x:rato_pati", sd.DIRECTORY_BY_PLATFORM_HANDLE)
        self.assertNotIn("x:techpananp", sd.DIRECTORY_BY_PLATFORM_HANDLE)
        self.assertNotIn("facebook:12khari", sd.DIRECTORY_BY_PLATFORM_HANDLE)
        for dup_fb in (
            "facebook:bijaykumar.official",
            "facebook:prembaniyaofficial",
            "facebook:gyanendrashahiofficial",
            "facebook:ndrrma.nepal",
            "facebook:nepalpolicehq",
        ):
            self.assertNotIn(dup_fb, sd.DIRECTORY_BY_PLATFORM_HANDLE)

        # Verify newly onboarded accounts across all 4 groups
        for key in (
            "x:bishnurijal1",
            "facebook:1434940019",
            "x:arjunnarasingha",
            "x:khusbu_oli",
            "x:jagdishkharel1",
            "x:hark_sampang",
            "x:lama_ram1",
            "x:birat_anupam",
            "x:tikaramyatri",
            "facebook:100064557167145",
            "facebook:routineofnepalipolitics",
            "facebook:24ghantanepal",
            "x:nonext_question",
            "x:tanujapandey_",
            "facebook:100066949059540",
            "x:sidhant",
            "x:siddhantvm",
        ):
            self.assertIn(key, sd.DIRECTORY_BY_PLATFORM_HANDLE, f"Missing expected account {key}")

        # Verify Balen Shah handles are authentic real-world URLs
        balen_fb = sd.DIRECTORY_BY_PLATFORM_HANDLE.get("facebook:balenofficial")
        self.assertIsNotNone(balen_fb, "Balen Shah Facebook must exist in directory")
        self.assertEqual(balen_fb.get("handle"), "balenOfficial")
        self.assertEqual(balen_fb.get("profile_url"), "https://www.facebook.com/balenOfficial")

        balen_x = sd.DIRECTORY_BY_PLATFORM_HANDLE.get("x:shahbalen")
        self.assertIsNotNone(balen_x, "Balen Shah X must exist in directory")
        self.assertEqual(balen_x.get("handle"), "ShahBalen")
        self.assertEqual(balen_x.get("profile_url"), "https://x.com/ShahBalen")

        # Verify no fabricated synthetic district accounts or fake role suffixes exist
        for acc in accounts:
            h = acc.get("handle", "")
            role = acc.get("role", "")
            self.assertFalse("Province)" in role, f"Synthetic district account found: {acc.get('name')} ({h})")
            self.assertFalse(any(h.endswith(suf) for suf in ["_jhap", "_mora", "_nuwa", "_chit", "_kail", "_bank", "_kasp"]),
                             f"Fabricated district handle found: {h}")
            self.assertFalse(any(h.endswith(suf) for suf in [".health", ".tech", ".biz", ".prof", ".critic", ".author", ".rights"]),
                             f"Fabricated role suffix handle found: {h}")
            self.assertIn(acc.get("platform"), ("facebook", "x"), "Platform must be facebook or x")
            self.assertTrue(acc.get("name"), "Account name must not be empty")
            self.assertTrue(acc.get("handle"), "Account handle must not be empty")
            self.assertTrue(acc.get("role"), "Account role must not be empty")
            self.assertTrue(acc.get("profile_url"), "Account profile_url must not be empty")

    def test_news_relevance_filter(self):
        """Verifies is_news_post accepts news and rejects greetings/banter."""
        # Greeting test
        is_news, score, cat = scanner.is_news_post("शुभप्रभात", "शुभ प्रभात सबै साथीहरूलाई आजको दिन शुभ रहोस्")
        self.assertFalse(is_news, "Pure greeting should not be classified as news")
        self.assertLess(score, 0.40)

        # Policy & News test
        news_sample = "संसदीय छानबिन विशेष समितिले सहकारी बचत अपचलन सम्बन्धमा सरकारलाई आफ्नो प्रतिवेदन बुझाएको छ।"
        is_news_2, score_2, cat_2 = scanner.is_news_post("सहकारी प्रतिवेदन", news_sample)
        self.assertTrue(is_news_2, "Policy/governance statement must be classified as news")
        self.assertGreaterEqual(score_2, 0.70)
        self.assertIn(cat_2, scanner.CANONICAL_CATEGORIES)

    def test_ten_account_batch_slicing(self):
        """Verifies scan_social_batch processes 10 accounts and advances cursor in a loop."""
        accounts = scanner.get_monitored_social_accounts()
        total = len(accounts)

        # Batch 1 from offset 0
        _, next_c1 = scanner.scan_social_batch(batch_size=10, offset=0)
        self.assertEqual(next_c1, 10)

        # Batch 2 from offset 10
        _, next_c2 = scanner.scan_social_batch(batch_size=10, offset=10)
        self.assertEqual(next_c2, 20)

        # Wrap-around check
        _, next_c_wrap = scanner.scan_social_batch(batch_size=10, offset=total - 5)
        self.assertEqual(next_c_wrap, 5)

    def test_store_hydrate_and_kpis(self):
        """Verifies _hydrate_x_rows assigns platform and get_x_account_kpis reflects 1,000+ voices."""
        sample_rows = [
            {"id": "1", "text": "Post 1", "link": "https://x.com/balenshah/status/123"},
            {"id": "2", "text": "Post 2", "link": "https://www.facebook.com/balenOfficial/posts/456", "platform": "facebook"},
        ]
        hydrated = store._hydrate_x_rows(sample_rows)
        self.assertEqual(hydrated[0]["platform"], "x")
        self.assertEqual(hydrated[1]["platform"], "facebook")

        # Test KPI fallback
        with mock.patch("nepal_news_store.query_supabase", return_value=[]):
            kpis = store.get_x_account_kpis()
            self.assertEqual(kpis.get("total_discovered", 0), 242)
            self.assertIn("Politicians", kpis.get("by_category", {}))

    def test_landing_page_source_counts(self):
        """Verifies _source_counts accurately returns the live 242 social media accounts."""
        from app import _source_counts
        np_c, ind_c, soc_c = _source_counts()
        self.assertGreater(np_c, 0, "Nepali press count should be > 0")
        self.assertGreater(ind_c, 0, "Indian press count should be > 0")
        self.assertGreaterEqual(soc_c, 242, "Social media account count must reflect the vetted accounts")

    def test_portal_x_bridges_and_boosts_preserved_beyond_curated_directory(self):
        """Verifies portal X bridge/boost handles remain active even when omitted from the 207 curated directory."""
        import nepal_fetcher as fetcher

        expected_portal_handles = {
            (p.get("x_handle") or p.get("x_boost_handle")).lstrip("@").strip().lower()
            for p in cfg.TOP_NEPAL_NEWS_PORTALS
            if p.get("x_handle") or p.get("x_boost_handle")
        }
        self.assertEqual(len(expected_portal_handles), 10)
        self.assertIn("rato_pati", expected_portal_handles)
        self.assertIn("techpananp", expected_portal_handles)

        # Curated directory intentionally omits directory-only portal boost handles
        curated_keys = {a["handle"].lower() for a in sd.VERIFIED_NEPAL_SOCIAL_DIRECTORY}
        self.assertNotIn("rato_pati", curated_keys)
        self.assertNotIn("techpananp", curated_keys)

        # _with_portal_x_accounts preserves all 10 portal X handles for scanner discovery
        merged = xs._with_portal_x_accounts(sd.VERIFIED_NEPAL_SOCIAL_DIRECTORY)
        merged_x_handles = {
            a["handle"].lstrip("@").strip().lower()
            for a in merged
            if str(a.get("platform") or "x").lower() == "x"
        }
        self.assertTrue(expected_portal_handles.issubset(merged_x_handles))
        rato_acc = next(a for a in merged if a["handle"].lower() == "rato_pati")
        tech_acc = next(a for a in merged if a["handle"].lower() == "techpananp")
        self.assertEqual(rato_acc.get("type"), "Media Houses and News Outlets")
        self.assertEqual(tech_acc.get("type"), "Media Houses and News Outlets")

        # scan_popular_nepal_x_posts passes portal boost handles into profile candidate discovery
        seen_discovery_handles = set()

        def _fake_discover(accounts, timeout_secs=18.0):
            seen_discovery_handles.update(
                a["handle"].lstrip("@").strip().lower() for a in accounts if a.get("handle")
            )
            return {}

        with mock.patch("nepal_x_scanner.get_monitored_x_accounts", return_value=list(sd.VERIFIED_NEPAL_SOCIAL_DIRECTORY)), \
             mock.patch("nepal_x_scanner._discover_profile_tweet_candidates", side_effect=_fake_discover), \
             mock.patch("nepal_x_scanner._discover_bing_tweet_candidates", return_value=[]), \
             mock.patch("nepal_social_scanner.scan_social_batch", return_value=([], 0)), \
             mock.patch("nepal_news_store.save_x_posts", return_value=0), \
             mock.patch("nepal_fetcher.bridge_x_portals_to_articles", return_value=0):
            xs.scan_popular_nepal_x_posts(force_refresh=True)

        self.assertTrue(expected_portal_handles.issubset(seen_discovery_handles))

        # boost_x_portals_to_articles still boosts Ratopati & TechPana posts
        now_npt = datetime.datetime(2026, 11, 26, 9, 45, 0, tzinfo=NEPAL_TZ)
        sample_x_posts = [
            {
                "id": "99001",
                "raw_handle": "Rato_pati",
                "text": "संसद् बैठकमा बजेटबारे छलफल सुरु https://t.co/rp1",
                "published_dt": now_npt - datetime.timedelta(minutes=5),
                "expanded_urls": ["https://www.ratopati.com/story/499001/parliament-budget"],
            },
            {
                "id": "99002",
                "raw_handle": "TechPanaNP",
                "text": "नेपालमा नयाँ साइबर सुरक्षा नीति लागू हुँदै https://t.co/tp1",
                "published_dt": now_npt - datetime.timedelta(minutes=4),
                "expanded_urls": ["https://techpana.com/2026/160999/cyber-security-policy"],
            },
        ]
        boosted_calls = []
        with mock.patch("nepal_fetcher.get_existing_article_urls", return_value={}), \
             mock.patch("nepal_fetcher.batch_fetch_full_content"), \
             mock.patch(
                 "nepal_fetcher.batch_upsert_articles",
                 side_effect=lambda arts, sname, **kw: boosted_calls.append((sname, arts, kw)) or {"ingested": len(arts)},
             ):
            cnt = fetcher.boost_x_portals_to_articles(x_posts=sample_x_posts, now_npt=now_npt)

        self.assertEqual(cnt, 2)
        self.assertEqual({sname for sname, _, _ in boosted_calls}, {"Ratopati", "TechPana"})

    def test_upsert_social_account_defaults_and_sync(self):
        """Verifies upsert_single_x_account gracefully defaults omitted fields and syncs to memory."""
        test_acc = {
            "platform": "facebook",
            "handle": "test_nepal_voice_unique",
            "name": "Test Nepal Voice",
            "category": "Civil Society and Public Voices",
            "subcategory": "Civic Oversight",
            "role": "Civic Researcher / Governance Watchdog",
            # Note: source_url, verification_status, followers, and relevance are omitted!
        }
        with mock.patch("nepal_news_store.query_supabase", return_value=[{"handle": "test_nepal_voice_unique"}]):
            saved = store.upsert_single_x_account(test_acc)
            self.assertTrue(saved)

        # Check in-memory sync
        mem_acc = sd.DIRECTORY_BY_PLATFORM_HANDLE.get("facebook:test_nepal_voice_unique")
        self.assertIsNotNone(mem_acc)
        self.assertEqual(mem_acc.get("verification_status"), "verified")
        self.assertEqual(mem_acc.get("followers"), "N/A")
        self.assertEqual(mem_acc.get("profile_url"), "https://www.facebook.com/test_nepal_voice_unique")

        # Toggle state in memory
        sd.set_memory_account_enabled("test_nepal_voice_unique", False, platform="facebook")
        self.assertEqual(mem_acc.get("enabled"), 0)

        # Cleanup test entry
        sd.delete_memory_account("test_nepal_voice_unique", platform="facebook")
        self.assertNotIn("facebook:test_nepal_voice_unique", sd.DIRECTORY_BY_PLATFORM_HANDLE)

    def test_account_monitoring_toggle_and_remove(self):
        """Verifies toggle monitoring on/off and remove trigger DB operations and directory updates."""
        test_h = "temp_audit_del_voice"
        test_plat = "facebook"
        test_acc = {
            "platform": test_plat,
            "handle": test_h,
            "name": "Temp Audit Voice",
            "category": "Politicians",
            "subcategory": "Party Leadership",
            "role": "Civic Leader",
            "enabled": 1,
            "verification_status": "verified"
        }
        with mock.patch("nepal_news_store.query_supabase", return_value=[{"handle": test_h}]):
            store.upsert_single_x_account(test_acc)

        # Verify added to memory
        self.assertIn(f"{test_plat}:{test_h}", sd.DIRECTORY_BY_PLATFORM_HANDLE)

        # 1. Test Monitor toggle off
        executed_sqls = []
        def _mock_query(sql):
            executed_sqls.append(sql)
            if "UPDATE x_accounts" in sql:
                return [{"handle": test_h}]
            if "DELETE FROM x_accounts" in sql:
                return [{"handle": test_h}]
            return []

        with mock.patch("nepal_news_store.query_supabase", side_effect=_mock_query):
            ok_toggle = store.set_x_account_enabled(test_h, False, platform=test_plat)
            self.assertTrue(ok_toggle)
            self.assertTrue(any("UPDATE x_accounts" in s and "enabled = 0" in s for s in executed_sqls))
            # Verify memory enabled updated
            acc_in_mem = sd.DIRECTORY_BY_PLATFORM_HANDLE.get(f"{test_plat}:{test_h}")
            self.assertEqual(acc_in_mem.get("enabled"), 0)

            # 2. Test Monitor toggle on
            ok_toggle_on = store.set_x_account_enabled(test_h, True, platform=test_plat)
            self.assertTrue(ok_toggle_on)
            self.assertTrue(any("UPDATE x_accounts" in s and "enabled = 1" in s for s in executed_sqls))
            self.assertEqual(acc_in_mem.get("enabled"), 1)

            # 3. Test Remove
            ok_remove = store.delete_x_account(test_h, platform=test_plat)
            self.assertTrue(ok_remove)
            self.assertTrue(any("DELETE FROM x_accounts" in s for s in executed_sqls))
            # Verify removed from memory
            self.assertNotIn(f"{test_plat}:{test_h}", sd.DIRECTORY_BY_PLATFORM_HANDLE)

    def test_reliability_and_noise_reduction_fixes(self):
        """Verifies deterministic SHA-256 IDs, zero synthetic engagement, platform='x' filtering, and Public X Voice gate."""
        # 1. Deterministic SHA-256 IDs (tracking params stripped)
        id1 = scanner._deterministic_social_post_id("facebook", "https://www.facebook.com/post/123?utm_source=fb", "Title")
        id2 = scanner._deterministic_social_post_id("facebook", "https://www.facebook.com/post/123/?fbclid=xyz", "Title")
        self.assertEqual(id1, id2)
        self.assertTrue(id1.startswith("fb_"))
        self.assertEqual(len(id1), 23)

        # 2. RSS/Bing Facebook fallback sets zero engagement and is_real_api=False
        fake_feed = mock.MagicMock()
        fake_feed.entries = [
            type("Entry", (), {
                "title": "नेपाल सरकारको नयाँ नीति र बजेट घोषणा",
                "summary": "नेपाल सरकारले आज नयाँ आर्थिक नीति र बजेट सार्वजनिक गरेको छ।",
                "link": "https://www.facebook.com/24GhantaNepal/posts/999?utm_source=test",
                "published": datetime.datetime.now(NEPAL_TZ).isoformat(),
            })()
        ]
        with mock.patch("nepal_social_scanner.feedparser.parse", return_value=fake_feed):
            fb_posts = scanner._fetch_facebook_page_posts({"handle": "24GhantaNepal", "name": "24 Ghanta Nepal", "category": "Civil Society and Public Voices"})
        self.assertEqual(len(fb_posts), 1)
        self.assertEqual(fb_posts[0]["engagement_score"], 0)
        self.assertEqual(fb_posts[0]["likes"], 0)
        self.assertFalse(fb_posts[0]["is_real_api"])

        # 3. get_monitored_x_accounts filters to platform == 'x' and _get_account_by_handle_map includes new social dir accounts
        x_accs = xs.get_monitored_x_accounts(enabled_only=True)
        self.assertTrue(all(str(a.get("platform") or "x").lower() == "x" for a in x_accs))
        self.assertIn("bishnurijal1", xs._get_account_by_handle_map())
        self.assertIn("sidhant", xs._get_account_by_handle_map())

        # 4. _enrich_tweet_by_id filters noisy unmapped Public X Voice while protecting curated & bridge accounts
        def _fake_cdn_resp(payload):
            r = mock.MagicMock()
            r.status_code = 200
            r.json.return_value = payload
            return r

        # 4a. Unmapped greeting/low-substance tweet is rejected
        low_payload = {
            "text": "Good morning everyone! https://t.co/abc123",
            "user": {"screen_name": "random_noise_999", "name": "Random"},
            "favorite_count": 5,
            "retweet_count": 0,
            "reply_count": 0,
            "created_at": datetime.datetime.now(NEPAL_TZ).isoformat(),
        }
        with mock.patch.object(xs._get_x_http_session(), "get", return_value=_fake_cdn_resp(low_payload)):
            self.assertIsNone(xs._enrich_tweet_by_id("2123456789012345678"))

        # 4b. Unmapped off-topic (non-Nepal) news tweet is rejected
        offtopic_payload = {
            "text": "The federal parliament passed a new municipal parking tax reform bill today in Sydney.",
            "user": {"screen_name": "random_noise_999", "name": "Random"},
            "favorite_count": 12,
            "retweet_count": 3,
            "reply_count": 1,
            "created_at": datetime.datetime.now(NEPAL_TZ).isoformat(),
        }
        with mock.patch.object(xs._get_x_http_session(), "get", return_value=_fake_cdn_resp(offtopic_payload)):
            self.assertIsNone(xs._enrich_tweet_by_id("2123456789012345679"))

        # 4c. Unmapped substantive Nepal news tweet is accepted
        nepal_payload = {
            "text": "Nepal parliament committee today reviewed the new hydropower investment policy and cross-border power trade treaty.",
            "user": {"screen_name": "unmapped_analyst", "name": "Analyst"},
            "favorite_count": 20,
            "retweet_count": 4,
            "reply_count": 2,
            "created_at": datetime.datetime.now(NEPAL_TZ).isoformat(),
        }
        with mock.patch.object(xs._get_x_http_session(), "get", return_value=_fake_cdn_resp(nepal_payload)):
            res_unmapped = xs._enrich_tweet_by_id("2123456789012345680")
        self.assertIsNotNone(res_unmapped)
        self.assertEqual(res_unmapped["author_type"], "Public X Voice")

        # 4d. Protected media-house bridge handle (@Rato_pati) passes even with short link-only headline
        bridge_payload = {
            "text": "ब्रेकिङ अपडेट https://t.co/xyz",
            "user": {"screen_name": "Rato_pati", "name": "Ratopati"},
            "favorite_count": 10,
            "retweet_count": 2,
            "reply_count": 0,
            "created_at": datetime.datetime.now(NEPAL_TZ).isoformat(),
        }
        with mock.patch.object(xs._get_x_http_session(), "get", return_value=_fake_cdn_resp(bridge_payload)):
            res_bridge = xs._enrich_tweet_by_id("2123456789012345681")
        self.assertIsNotNone(res_bridge)

    def test_pending_verification_discovery_pipeline(self):
        """Verifies co-mention/quote extraction, candidate evaluation, denylist/credibility/50-cap, 10/week promotion cap, and hourly schedule."""
        import nepal_news_scheduler as sched

        # 1. Co-mention & quote extraction in _enrich_tweet_by_id for monitored account
        monitored_acc = sd.DIRECTORY_BY_PLATFORM_HANDLE["x:shahbalen"]
        tweet_payload = {
            "text": "Important discussion on Kathmandu infrastructure with @new_policy_voice and @grok",
            "user": {"screen_name": "ShahBalen", "name": "Balen Shah"},
            "favorite_count": 500,
            "retweet_count": 80,
            "reply_count": 20,
            "created_at": datetime.datetime.now(NEPAL_TZ).isoformat(),
            "quoted_tweet": {
                "text": "Nepal budget infrastructure update",
                "user": {
                    "screen_name": "new_econ_scholar",
                    "name": "New Econ Scholar",
                    "followers_count": 5500,
                    "is_blue_verified": True,
                },
            },
            "entities": {
                "user_mentions": [
                    {"screen_name": "new_policy_voice", "name": "New Policy Voice"},
                    {"screen_name": "grok", "name": "Grok"},
                    {"screen_name": "ShahBalen", "name": "Balen Shah"},
                ]
            },
        }
        r_mock = mock.MagicMock()
        r_mock.status_code = 200
        r_mock.json.return_value = tweet_payload
        with mock.patch.object(xs._get_x_http_session(), "get", return_value=r_mock):
            enriched = xs._enrich_tweet_by_id("2123456789012345690", known_handle="ShahBalen", known_account=monitored_acc)

        sigs = enriched.get("_discovery_signals", [])
        sig_handles = {s["handle"].lower() for s in sigs}
        self.assertIn("new_econ_scholar", sig_handles)
        self.assertIn("new_policy_voice", sig_handles)
        self.assertNotIn("shahbalen", sig_handles)

        # 2. Denylist & credibility checks
        self.assertFalse(store.is_candidate_handle_allowed("grok"))
        self.assertFalse(store.is_candidate_handle_allowed("nepal_parody_acc"))
        self.assertFalse(store.is_candidate_handle_allowed("user_987654"))
        self.assertTrue(store.is_candidate_handle_allowed("new_econ_scholar", "New Econ Scholar"))
        self.assertFalse(store._is_candidate_credible(followers_count=300, is_blue_verified=False))
        self.assertTrue(store._is_candidate_credible(followers_count=2500, is_blue_verified=False))

        # 3. evaluate_and_enqueue_candidates enforces 50-row pending cap & enqueues valid candidates
        with mock.patch("nepal_news_store.query_supabase", side_effect=[
            [],             # TTL cleanup x_accounts
            [],             # TTL cleanup signals
            [{"n": 50}],    # pending count == 50 (at cap)
        ]):
            cap_res = store.evaluate_and_enqueue_candidates(max_pending=50, ttl_days=30)
        self.assertEqual(cap_res["enqueued"], 0)
        self.assertEqual(cap_res["pending_total"], 50)

        sql_log = []
        def _fake_eval_sql(sql):
            sql_log.append(sql)
            if "DELETE FROM x_accounts" in sql:
                return [{"handle": "stale_candidate"}]
            if "DELETE FROM x_account_discovery_signals" in sql:
                return []
            if "SELECT COUNT(*) AS n FROM x_accounts WHERE verification_status = 'pending_verification'" in sql:
                return [{"n": 2}]
            if "SELECT COALESCE(platform, 'x') AS platform, LOWER(handle) AS h FROM x_accounts" in sql:
                return [{"platform": "x", "h": "shahbalen"}]
            if "FROM x_account_discovery_signals" in sql:
                return [
                    {"platform": "x", "h": "new_econ_scholar", "name": "New Econ Scholar", "distinct_sources": 4, "followers_count": 5500, "is_blue_verified": True, "account_created_at": None, "rel_ratio": 1.0},
                    {"platform": "x", "h": "low_follower_bot12345", "name": "Spam", "distinct_sources": 5, "followers_count": 100, "is_blue_verified": False, "account_created_at": None, "rel_ratio": 1.0},
                ]
            if "INTERVAL '7 days'" in sql and "FROM x_posts" in sql:
                return [{"h": "bing_nepal_expert", "name": "Bing Nepal Expert", "post_cnt": 4, "max_eng": 120, "is_ver": True, "sample_texts": "Nepal budget and parliament policy || Kathmandu trade agreement"}]
            if "INTERVAL '48 hours'" in sql and "FROM x_posts" in sql:
                return [{"h": "spike_voice", "name": "Spike Voice", "spike_cnt": 2, "max_eng": 250, "is_ver": False, "sample_texts": "Nepal election commission update || Balen Kathmandu policy"}]
            if "INSERT INTO x_accounts" in sql:
                return [{"handle": "new_econ_scholar"}, {"handle": "bing_nepal_expert"}, {"handle": "spike_voice"}]
            return []

        with mock.patch("nepal_news_store.query_supabase", side_effect=_fake_eval_sql):
            ev_res = store.evaluate_and_enqueue_candidates(max_pending=50, ttl_days=30)
        self.assertEqual(ev_res["expired"], 1)
        self.assertEqual(ev_res["enqueued"], 3)
        self.assertEqual(ev_res["pending_total"], 5)
        insert_sql = next(s for s in sql_log if "INSERT INTO x_accounts" in s)
        self.assertNotIn("low_follower_bot12345", insert_sql)
        self.assertIn("pending_verification", insert_sql)

        # 4. Rolling 7-day cap of <= 10 promotions
        with mock.patch("nepal_news_store.query_supabase", return_value=[{"n": 10}]):
            ok_cap, msg_cap = store.promote_pending_x_account("new_econ_scholar", platform="x", max_weekly_promotions=10)
        self.assertFalse(ok_cap)
        self.assertIn("cap", msg_cap.lower())

        with mock.patch("nepal_news_store.query_supabase", side_effect=[
            [{"n": 9}],
            [{"platform": "x", "handle": "new_econ_scholar", "name": "New Econ Scholar", "enabled": 1, "verification_status": "verified"}],
        ]):
            ok_prom, _ = store.promote_pending_x_account("new_econ_scholar", platform="x", max_weekly_promotions=10)
        self.assertTrue(ok_prom)
        sd.delete_memory_account("new_econ_scholar", platform="x")

        # 5. Hourly scheduler gating
        sched._LAST_CANDIDATE_EVAL_TIME = 0.0
        with mock.patch("nepal_news_store.evaluate_and_enqueue_candidates", return_value={"enqueued": 1}) as m_eval:
            r1 = sched._maybe_run_candidate_discovery(now_sec=4000.0)
            r2 = sched._maybe_run_candidate_discovery(now_sec=4500.0)
            r3 = sched._maybe_run_candidate_discovery(now_sec=7601.0)
        self.assertIsNotNone(r1)
        self.assertIsNone(r2)
        self.assertIsNotNone(r3)
        self.assertEqual(m_eval.call_count, 2)

    def test_facebook_fetch_rejects_third_party_news_misattribution(self):
        """Verifies _fetch_facebook_page_posts rejects third-party news URLs and unrelated FB pages."""
        from types import SimpleNamespace

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        fake_entries = [
            SimpleNamespace(
                title="Balen Shah inspects Kathmandu road project",
                summary="Kathmandu Metropolitan City mayor inspects road maintenance and budget.",
                link="https://onlinekhabar.com/2026/11/balen-news",
                published=now_str,
            ),
            SimpleNamespace(
                title="Random Page Update - Facebook",
                summary="Unrelated Facebook page discussing Nepal parliament and budget.",
                link="https://www.facebook.com/randompage999/posts/111",
                published=now_str,
            ),
            SimpleNamespace(
                title="Balen Shah - Facebook",
                summary="Kathmandu Metropolitan City announces new infrastructure budget and governance reform.",
                link="https://www.facebook.com/balenofficial/posts/222?fbclid=IwAR123",
                published=now_str,
            ),
        ]
        acc = {
            "platform": "facebook",
            "handle": "balenofficial",
            "name": "Balen Shah",
            "type": "Politicians",
        }
        with mock.patch("feedparser.parse", return_value=SimpleNamespace(entries=fake_entries)):
            posts = scanner._fetch_facebook_page_posts(acc, hours_cutoff=48)
        self.assertEqual(len(posts), 1)
        self.assertIn("balenofficial/posts/222", posts[0]["link"])
        self.assertEqual(posts[0]["author_type"], "Politicians")
        self.assertFalse(posts[0]["is_real_api"])

        # Verify Bing fallback is strictly scoped to site:facebook.com and rejects non-FB links
        captured_urls = []
        mock_resp = SimpleNamespace(status_code=200, text="<rss/>")
        mock_sess = mock.MagicMock()

        def _fake_get(url, **kwargs):
            captured_urls.append(url)
            return mock_resp

        mock_sess.get.side_effect = _fake_get
        with mock.patch("feedparser.parse", side_effect=[
            SimpleNamespace(entries=[]),
            SimpleNamespace(entries=[fake_entries[0]]),
        ]), mock.patch("nepal_social_scanner._get_social_http_session", return_value=mock_sess):
            fb_fallback = scanner._fetch_facebook_page_posts(acc, hours_cutoff=48)
        self.assertEqual(fb_fallback, [])
        self.assertTrue(captured_urls and "site%3Afacebook.com" in captured_urls[0])

    def test_social_batch_time_slotted_cursor_and_coverage(self):
        """Verifies scan_social_batch uses a time-slotted initial cursor and batch_size=25."""
        accounts = scanner.get_monitored_social_accounts()
        total = len(accounts)
        orig_cursor = scanner._CURRENT_ACCOUNT_CURSOR
        try:
            scanner._CURRENT_ACCOUNT_CURSOR = None
            with mock.patch("time.time", return_value=900.0 * 3 + 15.0), \
                 mock.patch("nepal_social_scanner._fetch_facebook_page_posts", return_value=[]), \
                 mock.patch("nepal_social_scanner._fetch_x_account_posts", return_value=[]):
                _, next_c = scanner.scan_social_batch(batch_size=25)
            expected_start = (3 * 25) % total
            self.assertEqual(next_c, (expected_start + 25) % total)
        finally:
            scanner._CURRENT_ACCOUNT_CURSOR = orig_cursor

    def test_monitored_x_greeting_noise_and_cross_batch_dedup(self):
        """Verifies monitored X greeting/bare-link filtering and save_x_posts cross-batch dedup."""
        import nepal_x_scanner as xs

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%a %b %d %H:%M:%S +0000 %Y")
        acc_map = {
            "balenshah": {
                "handle": "balenshah",
                "name": "Balen Shah",
                "type": "Politicians",
                "role": "Mayor",
                "avatar_bg": "#1d9bf0",
                "initials": "BS",
            }
        }

        def _fake_cdn_resp(text_val, handle_val="balenshah"):
            r = mock.MagicMock()
            r.status_code = 200
            r.json.return_value = {
                "text": text_val,
                "created_at": now_str,
                "favorite_count": 10,
                "retweet_count": 2,
                "reply_count": 1,
                "user": {"screen_name": handle_val, "name": handle_val},
            }
            return r

        with mock.patch("nepal_x_scanner._get_account_by_handle_map", return_value=acc_map), \
             mock.patch("nepal_x_scanner._get_portal_x_handle_set", return_value={"annapurna_post"}):
            mock_sess = mock.MagicMock()
            mock_sess.get.return_value = _fake_cdn_resp("Good morning Nepal ☀️", "balenshah")
            with mock.patch("nepal_x_scanner._get_x_http_session", return_value=mock_sess):
                self.assertIsNone(xs._enrich_tweet_by_id("1900000000000000001"))

            mock_sess.get.return_value = _fake_cdn_resp("https://t.co/onlylink", "balenshah")
            with mock.patch("nepal_x_scanner._get_x_http_session", return_value=mock_sess):
                self.assertIsNone(xs._enrich_tweet_by_id("1900000000000000002"))

            mock_sess.get.return_value = _fake_cdn_resp("Good morning! Kathmandu budget approved by parliament.", "balenshah")
            with mock.patch("nepal_x_scanner._get_x_http_session", return_value=mock_sess):
                self.assertIsNotNone(xs._enrich_tweet_by_id("1900000000000000003"))

            mock_sess.get.return_value = _fake_cdn_resp("Breaking update!", "annapurna_post")
            with mock.patch("nepal_x_scanner._get_x_http_session", return_value=mock_sess):
                self.assertIsNotNone(xs._enrich_tweet_by_id("1900000000000000004"))

        # Cross-batch dedup in save_x_posts
        existing_db_rows = [
            {
                "id": "x_1900000000000000010",
                "rh": "balenshah",
                "link": "https://x.com/balenshah/status/1900000000000000010",
                "txt_pref": "kathmandu budget approved by the parliament today after long",
            }
        ]
        incoming = [
            {
                "id": "x_rss_dup_url",
                "raw_handle": "balenshah",
                "handle": "@balenshah",
                "text": "Different prefix but same canonical tweet URL",
                "link": "https://x.com/balenshah/status/1900000000000000010?utm_source=bing",
            },
            {
                "id": "x_rss_dup_text",
                "raw_handle": "balenshah",
                "handle": "@balenshah",
                "text": "Kathmandu budget approved by the parliament today after long debate.",
                "link": "https://x.com/balenshah/status/999999",
            },
            {
                "id": "x_1900000000000000010",
                "raw_handle": "balenshah",
                "handle": "@balenshah",
                "text": "Kathmandu budget approved by the parliament today after long debate.",
                "link": "https://x.com/balenshah/status/1900000000000000010",
                "likes": 55,
            },
        ]
        with mock.patch("nepal_news_store.query_supabase", side_effect=[existing_db_rows, [{"cnt": 1}]]) as m_q:
            pushed = store.save_x_posts(incoming)
        self.assertEqual(pushed, 1)
        insert_sql = m_q.call_args_list[1][0][0]
        self.assertIn("x_1900000000000000010", insert_sql)
        self.assertNotIn("x_rss_dup_url", insert_sql)
        self.assertNotIn("x_rss_dup_text", insert_sql)

    def test_engagement_sort_real_api_priority_and_exclude_media_houses(self):
        """Verifies real-API engagement sort priority, exclude_media_houses forwarding, and RSS UI label."""
        captured_sql = []

        def _fake_q(sql):
            captured_sql.append(sql)
            return []

        with mock.patch("nepal_news_store.query_supabase", side_effect=_fake_q):
            store.get_stored_x_posts(sort_mode="Most engagement", limit=20)
        self.assertTrue(captured_sql)
        self.assertIn("CASE WHEN COALESCE(is_real_api, FALSE) THEN COALESCE(engagement_score, 0) ELSE -1 END DESC", captured_sql[0])

        with mock.patch("nepal_news_store.get_stored_x_posts", return_value=[]) as m_get:
            store.get_stored_live_feed_page(stream_filter="X (Twitter) Only", limit=20)
        self.assertTrue(m_get.called)
        self.assertTrue(m_get.call_args.kwargs.get("exclude_media_houses"))

        import app as nepal_app
        rss_html = nepal_app._render_x_metrics_html({"is_real_api": False, "likes": 0, "retweets": 0, "replies": 0, "sentiment": "Neutral"})
        self.assertIn("RSS / Metrics N/A", rss_html)
        real_html = nepal_app._render_x_metrics_html({"is_real_api": True, "likes": 0, "retweets": 0, "replies": 0, "sentiment": "Neutral"})
        self.assertNotIn("RSS / Metrics N/A", real_html)

    def test_keyset_cursor_parity_and_boundary_dedup_edge_cases(self):
        """Verifies -1 sentinel + (published_dt, id) cursor parity across sort modes and FB/dedup edge cases."""
        import app as nepal_app

        now_npt = datetime.datetime.now(store.NEPAL_TZ)
        rss_row = {"id": "fb_abc123", "published_dt": now_npt, "engagement_score": 50, "likes": 10, "retweets": 5, "is_real_api": False}
        real_row = {"id": "x_999", "published_dt": now_npt, "engagement_score": 12, "likes": 7, "retweets": 2, "is_real_api": True}

        for mode, col_name, real_val in (
            ("Most engagement", "engagement_score", 12),
            ("Most liked", "likes", 7),
            ("Most reposted", "retweets", 2),
        ):
            m_rss, dt_rss, id_rss = nepal_app._extract_next_cursor("x", [rss_row], mode)
            self.assertEqual((m_rss, id_rss), (-1, "fb_abc123"))
            sql_rss = store._build_workspace_page_sql(
                "x", sort_mode=mode, cursor_dt=dt_rss, cursor_id=id_rss, cursor_metric=m_rss, limit=20
            )
            self.assertIn(f"CASE WHEN COALESCE(is_real_api, FALSE) THEN COALESCE({col_name}, 0) ELSE -1 END", sql_rss)
            self.assertIn(f", published_dt, id) < (-1, ", sql_rss)
            self.assertIn("DESC, published_dt DESC, id DESC", sql_rss)

            m_real, dt_real, id_real = nepal_app._extract_next_cursor("x", [real_row], mode)
            self.assertEqual((m_real, id_real), (real_val, "x_999"))
            sql_real = store._build_workspace_page_sql(
                "x", sort_mode=mode, cursor_dt=dt_real, cursor_id=id_real, cursor_metric=m_real, limit=20
            )
            self.assertIn(f", published_dt, id) < ({real_val}, ", sql_real)

        # FB boundary check: handle='setopati' must NOT match facebook.com/setopati2/posts/1
        acc_fb = {"handle": "setopati", "name": "Setopati"}
        self.assertFalse(scanner._is_matching_facebook_entry("https://www.facebook.com/setopati2/posts/1", "Other News", acc_fb))
        self.assertTrue(scanner._is_matching_facebook_entry("https://www.facebook.com/setopati/posts/1", "Other News", acc_fb))

        # Back-to-back numeric status IDs with identical 60+ char prefix must BOTH be preserved
        shared_prefix = "Press Release: Kathmandu Metropolitan City announces immediate action on "
        p1 = {
            "id": "x_1900000000000000101",
            "raw_handle": "balenshah",
            "handle": "@balenshah",
            "text": shared_prefix + "waste management.",
            "link": "https://x.com/balenshah/status/1900000000000000101",
            "is_real_api": True,
        }
        p2 = {
            "id": "x_1900000000000000102",
            "raw_handle": "balenshah",
            "handle": "@balenshah",
            "text": shared_prefix + "traffic enforcement.",
            "link": "https://x.com/balenshah/status/1900000000000000102",
            "is_real_api": True,
        }
        with mock.patch("nepal_news_store.query_supabase", side_effect=[[], [{"cnt": 2}]]) as m_q:
            pushed = store.save_x_posts([p1, p2])
        self.assertEqual(pushed, 2)
        sql_ins = m_q.call_args_list[1][0][0]
        self.assertIn("x_1900000000000000101", sql_ins)
        self.assertIn("x_1900000000000000102", sql_ins)

    def test_google_news_wrapper_and_x_id_canonicalization(self):
        """Verifies Google News RSS wrapper FB matching/rejection and x_<sid> canonicalization."""
        import nepal_x_scanner as xs
        from types import SimpleNamespace

        acc = {"platform": "facebook", "handle": "ChiriBabuMaharjanOfficial", "name": "Chiri Babu Maharjan"}
        # Google News wrapper with matching target name & Facebook source -> accepted
        self.assertTrue(scanner._is_matching_facebook_entry(
            "https://news.google.com/rss/articles/CBMi3wFBVV95cUxOYkVw",
            "Chiri Babu Maharjan inspects Lalitpur heritage site - Facebook",
            acc,
            source_title="Facebook",
        ))
        # Google News wrapper with unrelated page/portal -> rejected
        self.assertFalse(scanner._is_matching_facebook_entry(
            "https://news.google.com/rss/articles/CBMikAFBVV95cUxOV1hE",
            "News24 Nepal. . TOP 20 NEWS - NEWS24 TV",
            acc,
            source_title="Facebook",
        ))
        # Google News wrapper with non-Facebook portal source -> rejected even if name appears
        self.assertFalse(scanner._is_matching_facebook_entry(
            "https://news.google.com/rss/articles/CBMikAFBVV95cUxOV1hE",
            "Chiri Babu Maharjan speaks at event",
            acc,
            source_title="OnlineKhabar",
        ))

        # Verify _enrich_tweet_by_id emits canonical x_<sid>
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%a %b %d %H:%M:%S +0000 %Y")
        mock_sess = mock.MagicMock()
        mock_resp = mock.MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "text": "Kathmandu Metropolitan City approves infrastructure budget in parliament.",
            "created_at": now_str,
            "favorite_count": 15,
            "retweet_count": 3,
            "reply_count": 1,
            "user": {"screen_name": "balenshah", "name": "Balen Shah"},
        }
        mock_sess.get.return_value = mock_resp
        with mock.patch("nepal_x_scanner._get_x_http_session", return_value=mock_sess):
            enriched = xs._enrich_tweet_by_id("1900000000000000201")
        self.assertIsNotNone(enriched)
        self.assertEqual(enriched["id"], "x_1900000000000000201")

        # Verify save_x_posts canonicalizes bare <sid> and deduplicates against x_<sid>
        p_bare = {
            "id": "1900000000000000202",
            "raw_handle": "balenshah",
            "handle": "@balenshah",
            "text": "Nepal parliament passes budget bill.",
            "link": "https://x.com/balenshah/status/1900000000000000202",
            "is_real_api": True,
        }
        p_prefixed = {
            "id": "x_1900000000000000202",
            "raw_handle": "balenshah",
            "handle": "@balenshah",
            "text": "Nepal parliament passes budget bill.",
            "link": "https://x.com/balenshah/status/1900000000000000202",
            "is_real_api": False,
        }
        with mock.patch("nepal_news_store.query_supabase", side_effect=[[], [{"cnt": 1}]]) as m_q:
            pushed = store.save_x_posts([p_bare, p_prefixed])
        self.assertEqual(pushed, 1)
        sql_ins = m_q.call_args_list[1][0][0]
        self.assertIn("x_1900000000000000202", sql_ins)
        self.assertEqual(sql_ins.count("1900000000000000202"), 2)  # once in id, once in link

        # Verify _fetch_facebook_page_posts queries Nepal-edition Google News with handle path
        seen_g_urls = []
        def _fake_parse(url):
            seen_g_urls.append(url)
            return SimpleNamespace(entries=[])

        mock_sess_empty = mock.MagicMock()
        mock_sess_empty.get.return_value = mock.MagicMock(status_code=200, text="<rss/>")
        with mock.patch("feedparser.parse", side_effect=_fake_parse), \
             mock.patch("nepal_social_scanner._get_social_http_session", return_value=mock_sess_empty):
            scanner._fetch_facebook_page_posts({"platform": "facebook", "handle": "balenofficial", "name": "Balen Shah"})
        self.assertTrue(seen_g_urls)
        self.assertIn("gl=NP&ceid=NP:en", seen_g_urls[0])
        self.assertIn("facebook.com/balenofficial", seen_g_urls[0])
        # Verify Nepali (Devanagari) alias is included in query and accepted in _is_matching_facebook_entry
        import urllib.parse
        self.assertIn(urllib.parse.quote("बालेन शाह"), seen_g_urls[0])
        self.assertTrue(scanner._is_matching_facebook_entry(
            "https://news.google.com/rss/articles/CBMi3wFBVV95cUxOYkVw",
            "बालेन शाह - Facebook",
            {"platform": "facebook", "handle": "balenOfficial", "name": "Balen Shah"},
            source_title="Facebook",
        ))


if __name__ == "__main__":
    unittest.main()
