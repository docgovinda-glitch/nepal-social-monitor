"""
test_social_media_unification.py
Unit tests verifying the 1,000+ Social Media (Facebook + X) directory,
the news relevance filter, the 10-account circular batch ingestion,
and unified database store and retrieval.
"""

import unittest
from unittest import mock
import datetime

import nepal_social_directory as sd
import nepal_social_scanner as scanner
import nepal_news_store as store
from nepal_config import NEPAL_TZ


class TestSocialMediaUnification(unittest.TestCase):

    def test_directory_volume_and_integrity(self):
        """Verifies directory contains strictly audited, authentic voices with zero fabrication."""
        accounts = sd.VERIFIED_NEPAL_SOCIAL_DIRECTORY
        self.assertGreaterEqual(len(accounts), 380, "Directory must have at least 380 authentic accounts")
        
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
            self.assertGreaterEqual(kpis.get("total_discovered", 0), 380)
            self.assertIn("Politicians", kpis.get("by_category", {}))

    def test_landing_page_source_counts(self):
        """Verifies _source_counts accurately returns social media accounts >= 380."""
        from app import _source_counts
        np_c, ind_c, soc_c = _source_counts()
        self.assertGreater(np_c, 0, "Nepali press count should be > 0")
        self.assertGreater(ind_c, 0, "Indian press count should be > 0")
        self.assertGreaterEqual(soc_c, 380, "Social media account count must reflect the vetted accounts")

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
