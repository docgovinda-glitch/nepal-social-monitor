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


if __name__ == "__main__":
    unittest.main()
