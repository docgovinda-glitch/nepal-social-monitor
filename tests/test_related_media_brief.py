import datetime
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import nepal_news_store as store
import nepal_summarizer as summarizer


class TestRelatedSameStreamBrief(unittest.TestCase):
    def test_nepali_article_returns_only_nepali_same_stream_and_deduplicates(self):
        now = datetime.datetime(2026, 11, 26, 14, 0, tzinfo=store.NEPAL_TZ)
        target = {
            "canonical_id": "np-1",
            "source": "eKantipur",
            "title": "प्रधानमन्त्री कार्कीद्वारा जलविद्युत आयोजनाको उद्घाटन",
            "summary": "प्रधानमन्त्री कार्कीले तामाकोशी जलविद्युत आयोजनाको उद्घाटन गर्नुभएको छ।",
            "link": "https://ekantipur.com/news/2026/11/26/hydro-project?utm_source=rss",
            "canonical_url": "https://ekantipur.com/news/2026/11/26/hydro-project",
            "language": "Nepali",
            "published_dt": now,
        }
        candidates = [
            # Same-stream Nepali match (Setopati)
            {
                "canonical_id": "np-2",
                "source": "Setopati",
                "title": "प्रधानमन्त्री कार्कीले गरे तामाकोशी जलविद्युत आयोजनाको उद्घाटन",
                "summary": "तामाकोशी जलविद्युत आयोजनाको उद्घाटन कार्यक्रम सम्पन्न भएको छ।",
                "link": "https://www.setopati.com/politics/hydro-project",
                "language": "Nepali",
                "published_dt": now - datetime.timedelta(hours=1),
            },
            # Duplicate outlet (Setopati again, lower score/older)
            {
                "canonical_id": "np-3",
                "source": "Setopati",
                "title": "तामाकोशी जलविद्युत आयोजनाको उद्घाटन",
                "summary": "प्रधानमन्त्री कार्की द्वारा उद्घाटन।",
                "link": "https://setopati.com/politics/hydro-project-2",
                "language": "Nepali",
                "published_dt": now - datetime.timedelta(hours=2),
            },
            # Self-canonical URL duplicate from another source field
            {
                "canonical_id": "np-4",
                "source": "MirrorOutlet",
                "title": "प्रधानमन्त्री कार्कीद्वारा जलविद्युत आयोजनाको उद्घाटन",
                "summary": "तामाकोशी जलविद्युत आयोजनाको उद्घाटन।",
                "link": "https://www.ekantipur.com/news/2026/11/26/hydro-project/",
                "language": "Nepali",
                "published_dt": now - datetime.timedelta(minutes=30),
            },
            # Cross-stream English article (must be excluded!)
            {
                "canonical_id": "en-1",
                "source": "The Kathmandu Post",
                "title": "PM Karki inaugurates Tamakoshi hydropower project",
                "summary": "Prime Minister Karki inaugurated the Tamakoshi hydropower project.",
                "link": "https://kathmandupost.com/national/2026/11/26/hydro-project",
                "language": "English",
                "published_dt": now - datetime.timedelta(minutes=20),
            },
            # Hindi article (must never leak into Nepali stream!)
            {
                "canonical_id": "hi-1",
                "source": "Dainik",
                "title": "प्रधानमंत्री ने जलविद्युत परियोजना का उद्घाटन किया है",
                "summary": "तामाकोशी जलविद्युत परियोजना का उद्घाटन किया गया है।",
                "link": "https://example.in/hydro-project",
                "language": "Hindi",
                "published_dt": now - datetime.timedelta(minutes=15),
            },
            # Second valid Nepali outlet (OnlineKhabar)
            {
                "canonical_id": "np-5",
                "source": "OnlineKhabar (NP)",
                "title": "तामाकोशी जलविद्युत आयोजनाको प्रधानमन्त्री कार्कीद्वारा उद्घाटन",
                "summary": "जलविद्युत आयोजनाको उद्घाटन आज सम्पन्न भयो।",
                "link": "https://www.onlinekhabar.com/2026/11/hydro-project",
                "language": "Nepali",
                "published_dt": now - datetime.timedelta(minutes=10),
            },
        ]

        related = summarizer.find_related_same_stream_articles(target, candidates=candidates, max_results=3)
        sources = [r["source"] for r in related]
        urls = [r["url"] for r in related]
        self.assertEqual(len(related), 2)
        self.assertEqual(set(sources), {"Setopati", "OnlineKhabar (NP)"})
        self.assertNotIn("The Kathmandu Post", sources)
        self.assertNotIn("Dainik", sources)
        self.assertNotIn("MirrorOutlet", sources)
        self.assertTrue(all("ekantipur.com" not in u for u in urls))

    def test_english_article_returns_only_english_same_stream(self):
        now = datetime.datetime(2026, 11, 26, 14, 0, tzinfo=store.NEPAL_TZ)
        target = {
            "canonical_id": "en-10",
            "source": "The Kathmandu Post",
            "title": "Nepal and India sign power trade agreement in Kathmandu",
            "summary": "Officials signed a cross-border power trade agreement in Kathmandu on Thursday.",
            "link": "https://kathmandupost.com/money/2026/11/26/power-trade",
            "language": "English",
            "published_dt": now,
        }
        candidates = [
            {
                "canonical_id": "en-11",
                "source": "MyRepublica",
                "title": "India and Nepal ink cross-border power trade agreement in Kathmandu",
                "summary": "Kathmandu hosted the signing of the bilateral power trade agreement.",
                "link": "https://myrepublica.nagariknetwork.com/news/power-trade",
                "language": "English",
                "published_dt": now - datetime.timedelta(hours=1),
            },
            {
                "canonical_id": "np-11",
                "source": "Setopati",
                "title": "नेपाल र भारतबीच विद्युत व्यापार सम्झौतामा हस्ताक्षर",
                "summary": "काठमाडौंमा विद्युत व्यापार सम्झौता सम्पन्न।",
                "link": "https://www.setopati.com/kinmel/power-trade",
                "language": "Nepali",
                "published_dt": now - datetime.timedelta(minutes=30),
            },
        ]
        related = summarizer.find_related_same_stream_articles(target, candidates=candidates, max_results=3)
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["source"], "MyRepublica")

    def test_social_media_post_skips_related_lookup_completely(self):
        post = {
            "id": "1234567890",
            "raw_handle": "kathmandupost",
            "handle": "@kathmandupost",
            "platform": "x",
            "text": "Nepal and India sign power trade agreement in Kathmandu today.",
            "link": "https://x.com/kathmandupost/status/1234567890",
        }
        self.assertEqual(summarizer.find_related_same_stream_articles(post), [])
        with patch.object(summarizer, "find_related_same_stream_articles", side_effect=AssertionError("Must not be called")):
            res = summarizer.generate_on_demand_x_content(post)
        self.assertTrue(res["ok"])
        self.assertNotIn("Related:", res["formatted_text"])

    def test_syndicated_rss_story_and_zero_match_fallback(self):
        now = datetime.datetime(2026, 11, 26, 14, 0, tzinfo=store.NEPAL_TZ)
        syndicated_target = {
            "canonical_id": "syn-1",
            "source": "Gorkhapatra Online",
            "title": "रासस: कर्णाली राजमार्ग पहिरोका कारण अवरुद्ध",
            "summary": "रासस । अविरल वर्षापछि आएको पहिरोले कर्णाली राजमार्ग पूर्ण रूपमा अवरुद्ध भएको छ।",
            "link": "https://gorkhapatraonline.com/news/karnali-highway",
            "language": "Nepali",
            "published_dt": now,
        }
        candidates = [
            {
                "canonical_id": "syn-2",
                "source": "Ratopati",
                "title": "अविरल वर्षाले कर्णाली राजमार्ग पहिरोका कारण अवरुद्ध",
                "summary": "रासस। पहिरोले कर्णाली राजमार्ग अवरुद्ध हुँदा यात्रु अलपत्र परेका छन्।",
                "link": "https://www.ratopati.com/story/karnali-highway?fbclid=123",
                "language": "Nepali",
                "published_dt": now - datetime.timedelta(minutes=45),
            },
            # Different story that merely shares the wire tag रासस (must NOT match)
            {
                "canonical_id": "syn-3",
                "source": "Nepal Press",
                "title": "रासस: पोखरामा अन्तर्राष्ट्रिय साहित्य महोत्सव सुरु",
                "summary": "रासस। पोखरामा साहित्य महोत्सव आजबाट सुरु भएको छ।",
                "link": "https://www.nepalpress.com/pokhara-litfest",
                "language": "Nepali",
                "published_dt": now - datetime.timedelta(minutes=15),
            },
        ]
        related = summarizer.find_related_same_stream_articles(syndicated_target, candidates=candidates, max_results=3)
        self.assertEqual([r["source"] for r in related], ["Ratopati"])

        formatted_with_related = summarizer.format_english_brief_payload(
            headline="Karnali Highway blocked by landslide",
            brief="Continuous rainfall triggered a landslide blocking the Karnali Highway.",
            source_url="https://gorkhapatraonline.com/news/karnali-highway",
            related_links=related,
        )
        self.assertIn("Related:\n- Ratopati: https://www.ratopati.com/story/karnali-highway", formatted_with_related)

        # Zero-match fallback omits Related: cleanly
        formatted_empty = summarizer.format_english_brief_payload(
            headline="Karnali Highway blocked by landslide",
            brief="Continuous rainfall triggered a landslide blocking the Karnali Highway.",
            source_url="https://gorkhapatraonline.com/news/karnali-highway",
            related_links=[],
        )
        self.assertNotIn("Related:", formatted_empty)

    def test_store_candidates_strict_6h_window_and_error_fallback(self):
        now = datetime.datetime(2026, 11, 26, 14, 0, tzinfo=store.NEPAL_TZ)
        item = {
            "source": "eKantipur",
            "language": "Nepali",
            "published_dt": now,
        }
        captured_sql = []

        def _fake_query(sql, params=None):
            captured_sql.append(sql)
            return []

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RELATED_STREAM_WINDOW_HOURS", None)
            with patch.object(store, "query_supabase", side_effect=_fake_query):
                res = store.get_related_stream_candidates(item, "Nepali")
                self.assertEqual(res, [])
                self.assertEqual(len(captured_sql), 1)
                self.assertIn("FROM articles", captured_sql[0])
                self.assertIn("language = 'Nepali'", captured_sql[0])
                self.assertIn("2026-11-26 08:00:00", captured_sql[0])
                self.assertIn("2026-11-26 20:00:00", captured_sql[0])

        # Indian press routing + DB failure fallback
        indian_item = {
            "source": "The Hindu",
            "language": "English",
            "nepal_relevance_score": 0.85,
            "published_dt": now,
        }
        with patch.object(store, "query_supabase", side_effect=RuntimeError("DB down")):
            self.assertEqual(store.get_related_stream_candidates(indian_item, "English"), [])

    def test_null_published_dt_and_timezone_offset_window_guard(self):
        # Verify _normalize_dt_utc handles naive (NPT), UTC-aware, and NPT-aware offsets identically
        npt_dt = datetime.datetime(2026, 11, 26, 14, 0, tzinfo=store.NEPAL_TZ)
        naive_npt = datetime.datetime(2026, 11, 26, 14, 0)
        utc_equiv = datetime.datetime(2026, 11, 26, 8, 15, tzinfo=datetime.timezone.utc)
        self.assertEqual(store._normalize_dt_utc(npt_dt), utc_equiv)
        self.assertEqual(store._normalize_dt_utc(naive_npt), utc_equiv)
        self.assertEqual(store._normalize_dt_utc(utc_equiv), utc_equiv)
        self.assertIsNone(store._normalize_dt_utc(None))
        self.assertIsNone(store._normalize_dt_utc(""))

        item = {
            "source": "eKantipur",
            "language": "Nepali",
            "published_dt": npt_dt,
        }
        fake_rows = [
            # NULL published_dt -> must be excluded
            {"canonical_id": "r-null", "source": "Setopati", "published_dt": None, "language": "Nepali"},
            # Empty published_dt -> must be excluded
            {"canonical_id": "r-empty", "source": "Ratopati", "published_dt": "", "language": "Nepali"},
            # Unparseable published_dt -> must be excluded
            {"canonical_id": "r-bad", "source": "Himal Press", "published_dt": "not-a-date", "language": "Nepali"},
            # psycopg3 UTC-tagged NPT wallclock 2h earlier (12:00 NPT) -> within ±6h, must be kept
            {
                "canonical_id": "r-in",
                "source": "OnlineKhabar (NP)",
                "published_dt": datetime.datetime(2026, 11, 26, 12, 0, tzinfo=datetime.timezone.utc),
                "language": "Nepali",
            },
            # Naive NPT timestamp 7 hours earlier (07:00 NPT) -> outside ±6h, must be excluded
            {
                "canonical_id": "r-naive-out",
                "source": "NepalKhabar",
                "published_dt": datetime.datetime(2026, 11, 26, 7, 0),
                "language": "Nepali",
            },
            # psycopg3 UTC-tagged NPT wallclock 6h05m later (20:05 NPT) -> outside ±6h, must be excluded
            {
                "canonical_id": "r-out",
                "source": "Nagarik News",
                "published_dt": datetime.datetime(2026, 11, 26, 20, 5, tzinfo=datetime.timezone.utc),
                "language": "Nepali",
            },
        ]
        captured_sql = []

        def _fake_query(sql, params=None):
            captured_sql.append(sql)
            return list(fake_rows)

        with patch.object(store, "query_supabase", side_effect=_fake_query):
            res = store.get_related_stream_candidates(item, "Nepali", window_hours=6)

        self.assertIn("published_dt IS NOT NULL", captured_sql[0])
        self.assertEqual([r["canonical_id"] for r in res], ["r-in"])

    def test_google_news_wrapper_excluded_and_direct_canonical_preferred(self):
        now = datetime.datetime(2026, 11, 26, 14, 0, tzinfo=store.NEPAL_TZ)
        target = {
            "canonical_id": "en-20",
            "source": "The Kathmandu Post",
            "title": "Nepal and India sign power trade agreement in Kathmandu",
            "summary": "Officials signed a cross-border power trade agreement in Kathmandu.",
            "link": "https://kathmandupost.com/money/2026/11/26/power-trade",
            "language": "English",
            "published_dt": now,
        }
        candidates = [
            # Only unresolved news.google.com wrapper -> must be skipped
            {
                "canonical_id": "en-21",
                "source": "The Himalayan Times",
                "title": "Nepal and India sign power trade agreement in Kathmandu",
                "summary": "Cross-border power trade agreement signed in Kathmandu.",
                "link": "https://news.google.com/rss/articles/CBMiWWh0dHBzOi8vdGhlaGltYWxheWFudGltZXMuY29t",
                "canonical_url": "",
                "language": "English",
                "published_dt": now - datetime.timedelta(minutes=20),
            },
            # Has news.google.com link, but direct canonical_url -> must prefer & normalize direct URL
            {
                "canonical_id": "en-22",
                "source": "MyRepublica",
                "title": "India and Nepal ink cross-border power trade agreement in Kathmandu",
                "summary": "Kathmandu hosted the signing of the bilateral power trade agreement.",
                "link": "https://news.google.com/rss/articles/CBMiVWh0dHBzOi8vbXlyZXB1YmxpY2E",
                "canonical_url": "https://myrepublica.nagariknetwork.com/news/power-trade/?utm_source=rss",
                "language": "English",
                "published_dt": now - datetime.timedelta(minutes=10),
            },
        ]
        related = summarizer.find_related_same_stream_articles(target, candidates=candidates, max_results=3)
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["source"], "MyRepublica")
        self.assertEqual(related[0]["url"], "https://myrepublica.nagariknetwork.com/news/power-trade")
        self.assertNotIn("news.google.com", related[0]["url"])
        self.assertEqual(related[0]["canonical_id"], "en-22")
        self.assertEqual(related[0]["table"], "articles")

    def test_record_whatsapp_sent_batch_single_upsert_and_dedup(self):
        executed = []

        def _fake_query(sql, params=None):
            executed.append(sql)
            return []

        entries = [
            {
                "item_key": "k-primary",
                "group_id": "123@g.us",
                "group_name": "Core group",
                "id_message": "MSG1",
                "item_link": "https://ekantipur.com/news/1",
            },
            {
                "item_key": "k-rel-1",
                "group_id": "123@g.us",
                "group_name": "Core group",
                "id_message": "MSG1",
                "item_link": "https://www.setopati.com/politics/1",
            },
            # Duplicate item_key should be deduplicated
            {
                "item_key": "k-rel-1",
                "group_id": "123@g.us",
                "group_name": "Core group",
                "id_message": "MSG1",
                "item_link": "https://www.setopati.com/politics/1",
            },
        ]
        with patch.object(store, "query_supabase", side_effect=_fake_query):
            count = store.record_whatsapp_sent_batch(entries)

        self.assertEqual(count, 2)
        self.assertEqual(len(executed), 1)
        self.assertIn("k-primary", executed[0])
        self.assertIn("k-rel-1", executed[0])
        self.assertEqual(store.record_whatsapp_sent_batch([]), 0)

    def test_collect_sent_targets_and_mark_feed_cards_sent_for_news_and_social(self):
        import app as app_mod

        primary_row = {
            "canonical_id": "np-100",
            "link": "https://ekantipur.com/news/100",
            "title": "Primary story",
        }
        rel_row = {
            "canonical_id": "np-101",
            "link": "https://www.setopati.com/politics/101",
            "title": "Related story",
        }
        p_cid = app_mod._compute_item_uid(primary_row, "global")
        r_cid = app_mod._compute_item_uid(rel_row, "global")

        draft = {
            "saved_content": "Summary body",
            "related_links": [
                {
                    "source": "Setopati",
                    "url": "https://www.setopati.com/politics/101",
                    "title": "Related story",
                    "canonical_id": "np-101",
                },
                {
                    # Not in saved_formatted -> must NOT be marked
                    "source": "Ratopati",
                    "url": "https://www.ratopati.com/story/not-included",
                    "title": "Omitted",
                    "canonical_id": "np-102",
                },
            ],
        }
        saved_fmt = (
            "*Primary*\n\nSummary body\n\n"
            "Source: https://ekantipur.com/news/100\n\n"
            "Related:\n- Setopati: https://www.setopati.com/politics/101"
        )

        # News brief collects primary + included related link
        targets = app_mod._collect_sent_targets_for_share(
            cache_id=p_cid,
            item_link="https://ekantipur.com/news/100",
            is_x=False,
            draft=draft,
            saved_formatted=saved_fmt,
        )
        self.assertEqual([t[0] for t in targets], [p_cid, r_cid])

        # Social post (is_x=True) and empty related_links mark ONLY primary
        self.assertEqual(
            [t[0] for t in app_mod._collect_sent_targets_for_share(p_cid, "https://x.com/a/1", True, draft, saved_fmt)],
            [p_cid],
        )
        self.assertEqual(
            [t[0] for t in app_mod._collect_sent_targets_for_share(p_cid, "https://ekantipur.com/news/100", False, {"related_links": []}, saved_fmt)],
            [p_cid],
        )

        fake_sessions = {
            "Nepal": {
                "items_by_uid": {"u1": primary_row, "u2": rel_row},
                "batches": [
                    {
                        "seq": 0,
                        "rev": 0,
                        "html": (
                            '<div class="feed-card-wrap" data-uid="u1"><!--sent--></div>'
                            '<div class="feed-card-wrap" data-uid="u2"><!--sent--></div>'
                        ),
                    }
                ],
                "_mounted_nav_seq": 3,
            }
        }
        with patch.object(app_mod.st, "session_state", {"feed_sessions": fake_sessions}):
            app_mod._mark_feed_cards_sent(targets, "Core group")

        batch_html = fake_sessions["Nepal"]["batches"][0]["html"]
        self.assertNotIn("<!--sent-->", batch_html)
        self.assertEqual(batch_html.count("hl-chip--ok"), 2)
        self.assertEqual(fake_sessions["Nepal"]["_mounted_nav_seq"], -1)

    def test_already_sent_or_unmatched_related_links_fail_safely(self):
        import app as app_mod

        fake_sessions = {
            "Nepal": {
                "items_by_uid": {
                    "u1": {"canonical_id": "np-200", "link": "https://ekantipur.com/news/200", "title": "Already sent"},
                },
                "batches": [
                    {
                        "seq": 0,
                        "rev": 1,
                        "html": '<div class="feed-card-wrap" data-uid="u1"><span class="hl-chip hl-chip--ok">✓</span></div>',
                    }
                ],
                "_mounted_nav_seq": 2,
            }
        }
        with patch.object(app_mod.st, "session_state", {"feed_sessions": fake_sessions}):
            app_mod._mark_feed_cards_sent(
                [("unknown-id", "https://nonexistent.example/news"), (app_mod._compute_item_uid({"canonical_id": "np-200"}, "global"), "")],
                "Core group",
            )
        # Should not duplicate tick chip or raise
        self.assertEqual(fake_sessions["Nepal"]["batches"][0]["html"].count("hl-chip--ok"), 1)


if __name__ == "__main__":
    unittest.main()
