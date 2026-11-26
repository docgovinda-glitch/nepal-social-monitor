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
