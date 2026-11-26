import os
import sys
import shutil
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nepal_summarizer as summ


class TestEntityAndPostpositionHandling(unittest.TestCase):
    def test_multichar_postposition_masking_and_restoration(self):
        text = "अख्तियारलाई सर्वोच्च अदालतमा प्रचण्डसँग प्रधानमन्त्रीले नेप्सेको नेपाल प्रहरीविरुद्ध उजुरी"
        masked, mmap = summ.mask_entities_for_translation(text)

        # Every multi-char postposition must be detached with a single space after __ENTxxx__
        self.assertIn(" लाई", masked)
        self.assertIn(" मा", masked)
        self.assertIn(" सँग", masked)
        self.assertIn(" ले", masked)
        self.assertIn(" को", masked)
        self.assertIn(" विरुद्ध", masked)
        self.assertEqual(len(mmap), 6)

        # Simulate machine translation output with varied placeholder spacing/casing
        simulated_tr = (
            "Complaint against _ent006_ of __ENT005__ by __ent 004__ with __ENT003__ "
            "at __ENT002__ to __ENT001__"
        )
        restored = summ.restore_entities_after_translation(simulated_tr, mmap)
        self.assertIn("CIAA", restored)
        self.assertIn("Supreme Court", restored)
        self.assertIn("Pushpa Kamal Dahal (Prachanda)", restored)
        self.assertIn("Prime Minister", restored)
        self.assertIn("NEPSE", restored)
        self.assertIn("Nepal Police", restored)


class TestTranslationCacheAndBilingualTolerance(unittest.TestCase):
    def test_lru_cache_l1_bound_and_l2_disk_retention(self):
        cache_dir = os.path.join(tempfile.gettempdir(), "test_ts_l1_l2_cache")
        shutil.rmtree(cache_dir, ignore_errors=True)
        cache = None
        try:
            cache = summ.TranslationLRUCache(maxsize=2, cache_dir=cache_dir)
            cache["ne::k1"] = "v1"
            cache["ne::k2"] = "v2"
            cache["ne::k3"] = "v3"

            # L1 is bounded to maxsize=2, while L2 diskcache retains evicted ne::k1
            self.assertEqual(len(cache), 2)
            self.assertIn("ne::k1", cache)
            self.assertEqual(cache.get("ne::k1"), "v1")
            self.assertEqual(len(cache), 2)

            # __getitem__ promotion from L2 also respects maxsize=2
            self.assertEqual(cache["ne::k2"], "v2")
            self.assertEqual(len(cache), 2)
        finally:
            if cache is not None:
                cache.close()
            shutil.rmtree(cache_dir, ignore_errors=True)

    def test_bilingual_script_tolerance(self):
        src = "नेपाल राष्ट्र बैंकले आज नयाँ मौद्रिक नीति सार्वजनिक गरेको छ। XYZ।"
        mostly_en = "Nepal Rastra Bank today released the new monetary policy. XYZ।"
        unchanged = src

        self.assertTrue(summ._translation_succeeded(src, mostly_en))
        self.assertFalse(summ._translation_succeeded(src, unchanged))
        self.assertFalse(summ._translation_succeeded(src, ""))


class TestBatchedTranslationAndSocialAttribution(unittest.TestCase):
    def test_batched_x_content_preserves_blank_lines_and_calls_batch_once(self):
        post = {
            "id": "1234567890",
            "platform": "x",
            "raw_handle": "balen",
            "author_name": "Balen Shah",
            "text": "पहिलो वाक्य यहाँ छ।\n\nदोस्रो वाक्य यहाँ छ।\nतेस्रो वाक्य यहाँ छ।",
        }
        with mock.patch(
            "nepal_summarizer._translate_batch_to_en",
            return_value=[
                "First sentence is here.",
                "Second sentence is here.",
                "Third sentence is here.",
            ],
        ) as mock_batch:
            res = summ.generate_on_demand_x_content(post)

        mock_batch.assert_called_once()
        self.assertTrue(res["ok"])
        self.assertEqual(
            res["content"],
            "First sentence is here.\n\nSecond sentence is here.\nThird sentence is here.",
        )
        self.assertEqual(res["source_url"], "https://x.com/balen/status/1234567890")

    def test_facebook_post_no_x_url_synthesis_and_clean_profile(self):
        fb_post = {
            "id": "fb_999",
            "platform": "facebook",
            "raw_handle": "https://www.facebook.com/balenofficial/",
            "author_name": "Balendra Shah",
            "role": "Mayor of Kathmandu",
            "text": "Kathmandu Metropolitan City announced a new sanitation drive today.",
            "link": "",
        }
        res = summ.generate_on_demand_x_content(fb_post)
        self.assertTrue(res["ok"])
        self.assertEqual(res["source_url"], "")
        self.assertNotIn("x.com/", res["formatted_text"])
        self.assertEqual(res["profile_line"], "Profile: Balendra Shah — Mayor of Kathmandu")

    def test_extract_on_demand_full_article_uses_batch_translation(self):
        art = {
            "title": "नेपालमा नयाँ जलविद्युत सम्झौता",
            "full_content": "पहिलो अनुच्छेद यहाँ छ।\n\nदोस्रो अनुच्छेद यहाँ छ।\n\nतेस्रो अनुच्छेद यहाँ छ।",
            "link": "",
            "language": "Nepali",
        }
        with mock.patch("nepal_summarizer._translate_ne_to_en", return_value="New Hydropower Deal in Nepal"), \
             mock.patch(
                 "nepal_summarizer._translate_batch_to_en",
                 return_value=["First paragraph is here.", "Second paragraph is here.", "Third paragraph is here."],
             ) as mock_batch:
            res = summ.extract_on_demand_full_article(art, translate_to_english=True)

        mock_batch.assert_called_once()
        self.assertTrue(res["ok"])
        self.assertEqual(res["translated_title"], "New Hydropower Deal in Nepal")
        self.assertEqual(
            res["translated_text"],
            "First paragraph is here.\n\nSecond paragraph is here.\n\nThird paragraph is here.",
        )


class TestSummarizationWindowAndLexRank(unittest.TestCase):
    def test_extract_native_salient_sentences_widened_window(self):
        body = (
            "नेपाल सरकारको मन्त्रिपरिषद् बैठक आज सिंहदरबारमा सम्पन्न भएको छ। "
            "बैठकले आगामी आर्थिक वर्षको लागि ५० अर्ब रुपैयाँको ऊर्जा विकास योजना स्वीकृत गरेको छ। "
            "उक्त योजनाअन्तर्गत तीनवटा नयाँ जलविद्युत आयोजना निर्माण गरिने जानकारी दिइएको छ। "
            "ऊर्जा मन्त्रालयका अनुसार निर्माण कार्य आगामी महिनाबाट सुरु हुनेछ। "
            "यसैबीच स्थानीय सरोकारवालाहरूले आयोजनामा पारदर्शिताको माग गरेका छन्।"
        )
        extracted = summ._extract_native_salient_sentences("ऊर्जा विकास योजना स्वीकृत", body)
        sents = [s for s in extracted.split("।") if s.strip()]
        self.assertGreaterEqual(len(sents), 3)
        self.assertLessEqual(len(extracted), 900)

    def test_generate_on_demand_news_brief_feeds_multisentence_lexrank(self):
        item = {
            "title": "नेपाल र भारतबीच ऊर्जा सम्झौता",
            "full_content": (
                "नेपाल र भारतबीच आज नयाँ ऊर्जा व्यापार सम्झौतामा हस्ताक्षर भएको छ। "
                "सम्झौताअनुसार आगामी १० वर्षमा १० हजार मेगावाट बिजुली निर्यात गरिनेछ। "
                "यो सम्झौताले नेपालको व्यापार घाटा कम गर्न मद्दत पुग्ने अपेक्षा गरिएको छ। "
                "दुवै देशका ऊर्जा सचिवहरूले काठमाडौँमा आयोजित कार्यक्रममा सहमति जनाएका हुन्।"
            ),
            "link": "",
            "language": "Nepali",
        }

        def _fake_tr(txt, **kw):
            if "ऊर्जा सम्झौता" in txt and len(txt) < 60:
                return "Nepal and India sign power agreement"
            return (
                "Nepal and India signed a new power trade agreement today. "
                "Under the pact, 10,000 MW of electricity will be exported over the next 10 years. "
                "The agreement is expected to help reduce Nepal's trade deficit. "
                "Energy secretaries of both countries endorsed the deal in Kathmandu."
            )

        with mock.patch("nepal_summarizer._translate_ne_to_en", side_effect=_fake_tr), \
             mock.patch(
                 "nepal_summarizer.generate_lexrank_english_summary",
                 wraps=summ.generate_lexrank_english_summary,
             ) as mock_lex:
            res = summ.generate_on_demand_news_brief(item)

        self.assertTrue(res["ok"])
        mock_lex.assert_called_once()
        lex_input_text = mock_lex.call_args.kwargs.get("full_text") or ""
        self.assertGreaterEqual(len([s for s in lex_input_text.split(".") if s.strip()]), 4)
        self.assertIn("Nepal and India signed a new power trade agreement today.", res["content"])
        self.assertEqual(res["headline_english"], "Nepal and India sign power agreement")

    def test_long_compound_sentence_rescued_via_clause_splitting(self):
        long_en = (
            "The Supreme Court issued an interim order today halting the controversial highway expansion "
            "project across the protected wetland corridor in Lalitpur district after local residents and "
            "conservationists filed a joint writ petition citing severe environmental damage; Nepal Electricity "
            "Authority separately announced that high-voltage transmission line upgrades along the eastern "
            "industrial corridor will proceed on schedule this quarter without any interruption."
        )
        self.assertGreater(len(long_en.split()), 55)
        en_sents = summ._split_sentences(long_en)
        self.assertEqual(len(en_sents), 2)
        self.assertTrue(en_sents[0].startswith("The Supreme Court issued"))
        self.assertTrue(en_sents[1].startswith("Nepal Electricity Authority separately announced"))

        long_ne = (
            "नेपाल राष्ट्र बैंकले आज सार्वजनिक गरेको नयाँ मौद्रिक नीतिले वाणिज्य बैंकहरूको तरलता व्यवस्थापन "
            "र कर्जा प्रवाहमा दीर्घकालीन सन्तुलन कायम गर्ने लक्ष्य राखेको छ तर निजी क्षेत्रका उद्योगीहरूले "
            "बैंकको ब्याजदर अझै अपेक्षित रूपमा घट्न नसकेको भन्दै उत्पादनमूलक तथा निर्यातमुखी क्षेत्रमा "
            "सहुलियतपूर्ण कर्जाको माग दोहोर्‍याएका छन् भने अर्थ मन्त्रालयले आगामी त्रैमासिकमा पुँजीगत खर्च "
            "र विकास निर्माण कार्य तीव्र बनाउने प्रतिबद्धता व्यक्त गरेको छ।"
        )
        self.assertGreater(len(long_ne.split()), 55)
        ne_sents = summ._split_sentences(long_ne)
        self.assertEqual(len(ne_sents), 3)
        self.assertIn("नेपाल राष्ट्र बैंकले", ne_sents[0])
        self.assertIn("निजी क्षेत्रका उद्योगीहरूले", ne_sents[1])
        self.assertIn("अर्थ मन्त्रालयले", ne_sents[2])

    def test_devanagari_late_index_factual_sentence_survives_and_appears_in_brief(self):
        # Sentences 1..3 are low-fact filler; sentence at index 5 has high-value numbers & institutional terms
        body = (
            "सरकारले आज राजधानीमा विशेष कार्यक्रम आयोजना गरी नयाँ आर्थिक कार्ययोजना सार्वजनिक गरेको छ। "
            "कार्यक्रममा विभिन्न क्षेत्रका प्रतिनिधिहरूको उल्लेखनीय उपस्थिति रहेको आयोजकले जनाएको छ। "
            "सहभागीहरूले समसामयिक विषयमा आ-आफ्ना धारणा राखेका थिए। "
            "छलफलका क्रममा विविध पक्षमा सामान्य विचार विमर्श भएको बताइएको छ। "
            "अधिकांश वक्ताहरूले कार्यक्रमको महत्त्वबारे सामान्य चर्चा गरेका थिए। "
            "कार्ययोजनाअनुसार अर्थ मन्त्रालयले ७५ अर्ब रुपैयाँको विशेष कोषमार्फत १२ प्रतिशत ब्याज अनुदान र ५०० मेगावाट सौर्य ऊर्जा उत्पादन लक्ष्य स्वीकृत गरेको छ। "
            "अन्त्यमा आयोजकले सबै सहभागीलाई धन्यवाद ज्ञापन गरेको थियो।"
        )
        extracted = summ._extract_native_salient_sentences("नयाँ आर्थिक कार्ययोजना सार्वजनिक", body)
        self.assertIn("७५ अर्ब", extracted)
        self.assertIn("५०० मेगावाट", extracted)

        item = {
            "title": "नयाँ आर्थिक कार्ययोजना सार्वजनिक",
            "full_content": body,
            "link": "",
            "language": "Nepali",
        }

        def _fake_tr(txt, **kw):
            if len(txt) < 60:
                return "Government unveils new economic action plan"
            return (
                "The government unveiled a new economic action plan at a special event in the capital today. "
                "Representatives from various sectors attended the event according to the organizers. "
                "Participants shared their general views on contemporary issues during the session. "
                "Under the action plan, the Finance Ministry approved a Rs 75 billion special fund with 12 percent interest subsidy and a 500 MW solar power target."
            )

        with mock.patch("nepal_summarizer._translate_ne_to_en", side_effect=_fake_tr):
            res = summ.generate_on_demand_news_brief(item)

        self.assertTrue(res["ok"])
        self.assertIn("Rs 75 billion", res["content"])
        self.assertIn("500 MW", res["content"])

    def test_short_article_adaptive_weights_no_disconnected_graph_degradation(self):
        # 5 sentences (< 8) where later sentences have weak graph overlap but strong facts/title alignment
        title = "Nepal Rastra Bank updates monetary policy"
        body = (
            "Nepal Rastra Bank unveiled its quarterly monetary policy review in Kathmandu today. "
            "The central bank maintained the policy rate at 5.5 percent for the current fiscal quarter. "
            "Commercial banks must keep a minimum liquidity ratio of 20 percent under the directive. "
            "Officials noted that annual consumer inflation eased to 4.1 percent last month. "
            "Business chambers welcomed the stable interest corridor ahead of the festival season."
        )
        brief = summ.generate_lexrank_english_summary(title, body, max_sentences=2, max_chars=450)
        self.assertTrue(brief)
        self.assertIn("Nepal Rastra Bank unveiled its quarterly monetary policy review", brief)
        # Sentence 2 should be a factual early sentence rather than failing due to sparse graph
        self.assertTrue("5.5 percent" in brief or "20 percent" in brief or "4.1 percent" in brief)
        self.assertLessEqual(len(brief), 450)

    def test_mmr_bigram_diversity_rejects_near_paraphrase_for_distinct_entity(self):
        title = "Supreme Court hears hydropower project petition"
        body = (
            "The Supreme Court began hearings on the Upper Karnali hydropower project petition in Kathmandu today. "
            "The Supreme Court heard arguments on the Upper Karnali hydropower project dispute in Kathmandu today. "
            "The Energy Ministry confirmed that Rs 45 billion in foreign investment remains committed to the 900 MW project."
        )
        brief = summ.generate_lexrank_english_summary(title, body, max_sentences=2, max_chars=450)
        self.assertIn("Upper Karnali hydropower project petition", brief)
        # Near-paraphrase sentence 2 must be rejected in favor of sentence 3 with distinct entity + numbers
        self.assertNotIn("heard arguments on the Upper Karnali", brief)
        self.assertIn("900 MW", brief)

    def test_quote_aware_clause_splitting_preserves_quoted_boundaries(self):
        long_quoted = (
            'Prime Minister told reporters, "We will review the electricity tariff; however, no final rate '
            'has been fixed — and stakeholder consultations will continue throughout this week" before departing '
            "for Pokhara to attend the provincial energy summit; Nepal Electricity Authority separately confirmed "
            "that Rs 12 billion in high-voltage transmission upgrades will begin immediately across three eastern districts."
        )
        self.assertGreater(len(long_quoted.split()), 55)
        sents = summ._split_sentences(long_quoted)
        self.assertEqual(len(sents), 2)
        # Quoted semicolon and em-dash must remain intact inside the first clause
        self.assertIn("tariff; however, no final rate has been fixed — and stakeholder consultations", sents[0])
        self.assertTrue(sents[1].startswith("Nepal Electricity Authority separately confirmed"))

    def test_short_sentence_length_calibrated_bigram_guard_retains_sentence_two(self):
        title = "Nepal Rastra Bank policy update"
        # Sentence 2 is <= 11 words, shares "Nepal Rastra" and "Rastra Bank" bigrams (~0.36-0.40 Jaccard)
        # with Sentence 1, but introduces a new numeric figure (5.5%) and must be retained.
        body = (
            "Nepal Rastra Bank issued new liquidity rules in Kathmandu. "
            "Nepal Rastra Bank set rates at 5.5 percent."
        )
        # Also test via >= 3 sentences so LexRank diversity loop executes
        body_3 = (
            "Nepal Rastra Bank issued new liquidity rules in Kathmandu. "
            "Nepal Rastra Bank set rates at 5.5 percent. "
            "Commercial lenders welcomed the clarity for quarterly treasury planning."
        )
        brief_2 = summ.generate_lexrank_english_summary(title, body, max_sentences=2, max_chars=450)
        self.assertIn("5.5 percent", brief_2)

        brief_3 = summ.generate_lexrank_english_summary(title, body_3, max_sentences=2, max_chars=450)
        self.assertIn("Nepal Rastra Bank issued new liquidity rules", brief_3)
        self.assertIn("5.5 percent", brief_3)

    def test_enrich_batch_metrics_and_salient_char_budget_guardrail(self):
        # Verify clamping of NATIVE_SALIENT_MAX_CHARS env overrides to [400, 3000]
        with mock.patch.dict(os.environ, {"NATIVE_SALIENT_MAX_CHARS": "100"}):
            self.assertEqual(summ._get_salient_char_budget(), 400)
        with mock.patch.dict(os.environ, {"NATIVE_SALIENT_MAX_CHARS": "9999"}):
            self.assertEqual(summ._get_salient_char_budget(), 3000)
        with mock.patch.dict(os.environ, {"NATIVE_SALIENT_MAX_CHARS": "1500"}):
            self.assertEqual(summ._get_salient_char_budget(), 1500)

        articles = [
            {
                "title": "नेपालमा नयाँ ऊर्जा योजना",
                "full_content": (
                    "नेपाल सरकारले आज ५० अर्ब रुपैयाँको नयाँ ऊर्जा योजना स्वीकृत गरेको छ। "
                    "ऊर्जा मन्त्रालयका अनुसार आगामी वर्ष ५०० मेगावाट बिजुली उत्पादन गरिनेछ।"
                ),
                "link": "",
                "language": "Nepali",
            }
        ]
        cache_dir = os.path.join(tempfile.gettempdir(), "test_metrics_cache")
        shutil.rmtree(cache_dir, ignore_errors=True)
        test_cache = summ.TranslationLRUCache(maxsize=16, cache_dir=cache_dir)
        try:
            with mock.patch.dict(os.environ, {"NATIVE_SALIENT_MAX_CHARS": "5000"}), \
                 mock.patch("nepal_summarizer._TRANSLATION_CACHE", test_cache), \
                 mock.patch(
                     "nepal_summarizer._translate_batch_group_meta",
                     return_value=(
                         [
                             "New energy plan in Nepal",
                             "Nepal government approved a Rs 50 billion energy plan today. The Energy Ministry said 500 MW will be generated next year.",
                         ],
                         "indictrans2",
                     ),
                 ), \
                 self.assertLogs("nepal_summarizer", level="INFO") as cm:
                out = summ.enrich_articles_with_english_summaries(articles, max_workers=2)

            self.assertEqual(out[0]["headline_english"], "New energy plan in Nepal")
            self.assertIn("Rs 50 billion", out[0]["summary"])
            metric_lines = [line for line in cm.output if "enrich_batch_metrics" in line]
            self.assertEqual(len(metric_lines), 1)
            line = metric_lines[0]
            for key in (
                "count=1",
                "scrape_ms=",
                "extract_ms=",
                "mt_ms=",
                "lexrank_ms=",
                "total_ms=",
                "avg_per_article_ms=",
                "cache_hits=0",
                "cache_misses=2",
            ):
                self.assertIn(key, line)
        finally:
            test_cache.close()
            shutil.rmtree(cache_dir, ignore_errors=True)


class TestIndicTrans2CloudRouting(unittest.TestCase):
    def test_indictrans2_ct2_routing_token_format_and_cleanup(self):
        mock_tr = mock.MagicMock()
        mock_hyp = mock.MagicMock()
        mock_hyp.hypotheses = [["npi_Deva", "eng_Latn", "▁Nepal", "▁economy", "▁grows", "▁.", "</s>", "<unk>"]]
        mock_tr.translate_batch.return_value = [mock_hyp]

        mock_sp_src = mock.MagicMock()
        mock_sp_src.encode.return_value = ["▁नेपाल", "▁अर्थतन्त्र", "▁2083"]
        mock_sp_tgt = mock.MagicMock()
        mock_sp_tgt.decode.side_effect = lambda toks: "".join(toks).replace("▁", " ").strip()

        with mock.patch.dict(
            os.environ,
            {
                "LOCAL_MT_ENGINE": "indictrans2",
                "INDICTRANS2_MODEL_ID": "adalat-ai/ct2-rotary-indictrans2-indic-en-dist-200M",
                "HF_TOKEN": "hf_test_token_123",
            },
        ), mock.patch(
            "nepal_summarizer._load_local_indictrans2_model",
            return_value=("ct2", mock_tr, mock_sp_src, mock_sp_tgt),
        ) as mock_loader:
            out = summ._translate_with_local_model("नेपाल अर्थतन्त्र २०८३", source_lang="ne")

        mock_loader.assert_called_once()
        mock_sp_src.encode.assert_called_once_with("नेपाल अर्थतन्त्र 2083", out_type=str)
        mock_tr.translate_batch.assert_called_once_with(
            [["npi_Deva", "eng_Latn", "▁नेपाल", "▁अर्थतन्त्र", "▁2083", "</s>"]],
            beam_size=4,
            max_decoding_length=256,
        )
        self.assertEqual(out, "Nepal economy grows.")

    def test_indictrans2_is_default_and_nllb_override_works(self):
        self.assertEqual(summ.LOCAL_MT_ENGINE, "indictrans2")
        self.assertEqual(summ.INDICTRANS2_MODEL_ID, "adalat-ai/ct2-rotary-indictrans2-indic-en-dist-200M")

        # Default (no env override) routes to IndicTrans2
        with mock.patch("nepal_summarizer._translate_with_indictrans2_batch_meta", return_value=(["Default IT2 Output"], "indictrans2")) as mock_it2, \
             mock.patch("nepal_summarizer._translate_with_nllb_model", return_value="NLLB Output") as mock_nllb:
            out_default = summ._translate_with_local_model("नेपाल", source_lang="ne")
        mock_it2.assert_called_once_with(["नेपाल"], source_lang="ne")
        mock_nllb.assert_not_called()
        self.assertEqual(out_default, "Default IT2 Output")

        # Empty result from IndicTrans2 automatically falls back to NLLB-200
        with mock.patch("nepal_summarizer._translate_with_indictrans2_batch_meta", return_value=([""], "indictrans2")), \
             mock.patch("nepal_summarizer._translate_with_nllb_model", return_value="NLLB Empty Fallback") as mock_nllb_empty:
            out_empty = summ._translate_with_local_model("नेपाल", source_lang="ne")
        mock_nllb_empty.assert_called_once_with("नेपाल", source_lang="ne")
        self.assertEqual(out_empty, "NLLB Empty Fallback")

        # Explicit LOCAL_MT_ENGINE=nllb override bypasses IndicTrans2
        with mock.patch.dict(os.environ, {"LOCAL_MT_ENGINE": "nllb"}), \
             mock.patch("nepal_summarizer._translate_with_indictrans2_batch_meta") as mock_it2_skip, \
             mock.patch("nepal_summarizer._translate_with_nllb_model", return_value="Explicit NLLB") as mock_nllb_ov:
            out_nllb = summ._translate_with_local_model("नेपाल", source_lang="ne")
        mock_it2_skip.assert_not_called()
        mock_nllb_ov.assert_called_once_with("नेपाल", source_lang="ne")
        self.assertEqual(out_nllb, "Explicit NLLB")

    def test_indictrans2_graceful_fallback_to_nllb_on_error(self):
        with mock.patch.dict(os.environ, {"LOCAL_MT_ENGINE": "indictrans2"}), \
             mock.patch("nepal_summarizer._load_local_indictrans2_model", side_effect=RuntimeError("Missing weights")), \
             mock.patch("nepal_summarizer._translate_with_nllb_model", return_value="NLLB Fallback Output") as mock_nllb:
            out = summ._translate_with_local_model("नेपालको समाचार", source_lang="ne")

        mock_nllb.assert_called_once_with("नेपालको समाचार", source_lang="ne")
        self.assertEqual(out, "NLLB Fallback Output")

    def test_hf_token_forwarded_and_nested_ct2_vocab_discovered(self):
        tmp_dir = os.path.join(tempfile.gettempdir(), "test_it2_hf_tok")
        nested_ct2 = os.path.join(tmp_dir, "indic-en-200m-ct2", "ctranslate2_model")
        vocab_dir = os.path.join(nested_ct2, "vocab")
        os.makedirs(vocab_dir, exist_ok=True)
        for p in (
            os.path.join(nested_ct2, "model.bin"),
            os.path.join(vocab_dir, "model.SRC"),
            os.path.join(vocab_dir, "model.TGT"),
        ):
            with open(p, "wb") as f:
                f.write(b"stub")

        old_cached = summ._LOCAL_IT2_MODEL
        summ._LOCAL_IT2_MODEL = None
        mock_spm_mod = mock.MagicMock()
        try:
            with mock.patch.dict(
                os.environ,
                {
                    "INDICTRANS2_MODEL_ID": "adalat-ai/ct2-rotary-indictrans2-indic-en-dist-200M",
                    "HF_TOKEN": "hf_secret_abc",
                },
            ), mock.patch.dict(sys.modules, {"sentencepiece": mock_spm_mod}), \
               mock.patch("huggingface_hub.snapshot_download", return_value=tmp_dir) as mock_dl, \
               mock.patch("ctranslate2.Translator", return_value=mock.MagicMock()) as mock_ct2:
                res = summ._load_local_indictrans2_model()
            self.assertEqual(res[0], "ct2")
            self.assertEqual(len(res), 4)
            mock_dl.assert_called_once_with(
                repo_id="adalat-ai/ct2-rotary-indictrans2-indic-en-dist-200M",
                token="hf_secret_abc",
            )
            mock_ct2.assert_called_once_with(nested_ct2, device="cpu", compute_type="int8")
            self.assertEqual(mock_spm_mod.SentencePieceProcessor.call_count, 2)
        finally:
            summ._LOCAL_IT2_MODEL = old_cached
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestTranslationEngineAttribution(unittest.TestCase):
    def test_cache_preserves_engine_and_handles_legacy_plain_strings(self):
        cache_dir = os.path.join(tempfile.gettempdir(), "test_engine_meta_cache")
        shutil.rmtree(cache_dir, ignore_errors=True)
        cache = None
        try:
            cache = summ.TranslationLRUCache(maxsize=2, cache_dir=cache_dir)
            cache.set_with_meta("ne::एक", "One", engine="indictrans2")
            cache.set_with_meta("ne::दुई", "Two", engine="google")
            # Legacy plain string directly written to L2 diskcache
            if cache._disk_cache is not None:
                cache._disk_cache.set("ne::तीन", "Three")

            # Backward-compatible string lookup
            self.assertEqual(cache["ne::दुई"], "Two")
            # Evicted from L1 ("ne::एक") still restores engine="indictrans2" from L2
            val1, eng1 = cache.get_with_meta("ne::एक")
            self.assertEqual(val1, "One")
            self.assertEqual(eng1, "indictrans2")

            if cache._disk_cache is not None:
                val3, eng3 = cache.get_with_meta("ne::तीन")
                self.assertEqual(val3, "Three")
                self.assertEqual(eng3, "google")
        finally:
            if cache is not None:
                cache.close()
            shutil.rmtree(cache_dir, ignore_errors=True)

    def test_google_and_indictrans2_metadata_in_payloads_and_english_omission(self):
        cache_dir = os.path.join(tempfile.gettempdir(), "test_engine_payload_cache")
        shutil.rmtree(cache_dir, ignore_errors=True)
        test_cache = summ.TranslationLRUCache(maxsize=16, cache_dir=cache_dir)
        try:
            with mock.patch("nepal_summarizer._TRANSLATION_CACHE", test_cache):
                # 1. Google Translate path
                with mock.patch("nepal_summarizer._translate_chunk_with_failover_meta", return_value=("Nepal cabinet decision", "google")):
                    txt, eng = summ._translate_ne_to_en_with_meta("मन्त्रिपरिषद्को निर्णय", source_lang="ne")
                self.assertEqual(txt, "Nepal cabinet decision")
                self.assertEqual(eng, "google")

                # Cache hit preserves "google"
                txt_hit, eng_hit = summ._translate_ne_to_en_with_meta("मन्त्रिपरिषद्को निर्णय", source_lang="ne")
                self.assertEqual(txt_hit, "Nepal cabinet decision")
                self.assertEqual(eng_hit, "google")

                # 2. IndicTrans2 path in extract_on_demand_full_article
                with mock.patch("nepal_news_store.hydrate_article_full_content", return_value=None), \
                     mock.patch("nepal_fetcher.extract_article_full_text", return_value=""), \
                     mock.patch("nepal_summarizer._translate_chunk_with_failover_meta", return_value=("Parliament passed the bill.", "indictrans2")):
                    rd = summ.extract_on_demand_full_article(
                        {"title": "विधेयक पारित", "full_content": "संसदले विधेयक पारित गरेको छ।", "link": "", "language": "Nepali"},
                        translate_to_english=True,
                    )
                self.assertTrue(rd["ok"])
                self.assertEqual(rd["translation_engine"], "IndicTrans2")

                # 3. Natively English article has empty translation_engine
                en_brief = summ.generate_on_demand_news_brief(
                    {"title": "Nepal exports power", "full_content": "Nepal exported 40 MW of electricity to Bangladesh today.", "link": "", "language": "English"}
                )
                self.assertTrue(en_brief["ok"])
                self.assertEqual(en_brief["translation_engine"], "")
        finally:
            test_cache.close()
            shutil.rmtree(cache_dir, ignore_errors=True)

    def test_app_renders_subtle_engine_badge_only_when_translated(self):
        # Run in an isolated subprocess so importing app.py in bare mode does not mutate parent Streamlit state for AppTest
        import subprocess
        code = (
            "import app as app_mod\n"
            "ne_card = app_mod.render_apple_article_card({"
            "'source': 'OnlineKhabar', 'title': 'शीर्षक', 'headline_english': 'Headline', "
            "'summary': 'Summary text', 'translation_engine': 'IndicTrans2', 'link': 'https://example.com/1'})\n"
            "assert 'Translated via IndicTrans2' in ne_card\n"
            "en_card = app_mod.render_apple_article_card({"
            "'source': 'The Kathmandu Post', 'title': 'English Headline', 'headline_english': 'English Headline', "
            "'summary': 'English summary', 'translation_engine': '', 'link': 'https://example.com/2'})\n"
            "assert 'Translated via' not in en_card\n"
            "x_card = app_mod.render_apple_x_post_card({"
            "'author_name': 'Balen', 'handle': '@balen', 'text': 'Translated text', "
            "'translation_engine': 'Google Translate', 'link': 'https://x.com/balen/status/1'})\n"
            "assert 'Translated via Google Translate' in x_card\n"
        )
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
