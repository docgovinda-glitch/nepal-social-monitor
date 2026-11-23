"""
test_media_logos.py
Comprehensive unit tests for media logo and social avatar resolution engine.
"""

import unittest
from media_logos import (
    resolve_media_domain,
    get_source_logo_urls,
    get_source_logo_html,
    get_x_author_avatar_html,
    _source_initials,
    _LOCAL_LOGOS,
)


class TestMediaLogos(unittest.TestCase):

    def test_source_initials(self):
        self.assertEqual(_source_initials("eKantipur"), "EK")
        self.assertEqual(_source_initials("Annapurna Post"), "AP")
        self.assertEqual(_source_initials("Nepal News"), "NN")
        self.assertEqual(_source_initials("The Hindu"), "TH")
        self.assertEqual(_source_initials(""), "•")

    def test_domain_resolution_known_nepal_portals(self):
        self.assertEqual(resolve_media_domain("eKantipur"), "ekantipur.com")
        self.assertEqual(resolve_media_domain("Kantipur"), "ekantipur.com")
        self.assertEqual(resolve_media_domain("Annapurna Post"), "annapurnapost.com")
        self.assertEqual(resolve_media_domain("OnlineKhabar (NP)"), "onlinekhabar.com")
        self.assertEqual(resolve_media_domain("Setopati"), "setopati.com")
        self.assertEqual(resolve_media_domain("Ratopati"), "ratopati.com")
        self.assertEqual(resolve_media_domain("Nepal News"), "nepalnews.com")

    def test_domain_resolution_known_indian_media(self):
        self.assertEqual(resolve_media_domain("The Indian Express"), "indianexpress.com")
        self.assertEqual(resolve_media_domain("The Hindu"), "thehindu.com")
        self.assertEqual(resolve_media_domain("Hindustan Times"), "hindustantimes.com")
        self.assertEqual(resolve_media_domain("NDTV"), "ndtv.com")
        self.assertEqual(resolve_media_domain("India Today"), "indiatoday.in")

    def test_domain_resolution_from_link(self):
        domain = resolve_media_domain("Unlisted Paper", link="https://www.reuters.com/world/asia-pacific/story-123")
        self.assertEqual(domain, "reuters.com")

    def test_local_logos_cached(self):
        self.assertIn("ekantipur.com.png", _LOCAL_LOGOS)
        self.assertIn("annapurnapost.com.png", _LOCAL_LOGOS)
        self.assertIn("nepalnews.com.png", _LOCAL_LOGOS)
        self.assertIn("onlinekhabar.com.png", _LOCAL_LOGOS)
        self.assertIn("thehindu.com.png", _LOCAL_LOGOS)

    def test_source_logo_urls_local_priority(self):
        primary, fallback = get_source_logo_urls("ekantipur.com")
        self.assertEqual(primary, "/app/static/media_logos/ekantipur.com.png")
        self.assertIn("google.com/s2/favicons", fallback)

    def test_get_source_logo_html_media(self):
        html_out = get_source_logo_html("eKantipur", link="https://ekantipur.com")
        self.assertIn('class="hl-av ', html_out)
        self.assertIn('src="/app/static/media_logos/ekantipur.com.png"', html_out)
        self.assertIn('class="hl-av-fb">EK</span>', html_out)
        self.assertIn('data-fallback-src="https://www.google.com/s2/favicons?domain=ekantipur.com', html_out)

    def test_get_source_logo_html_indian(self):
        html_out = get_source_logo_html("The Hindu", link="https://thehindu.com", is_indian=True)
        self.assertIn("hl-av--in", html_out)
        self.assertIn("thehindu.com.png", html_out)

    def test_get_source_logo_html_social_x(self):
        html_out = get_source_logo_html("X", link="https://x.com/post/123")
        self.assertIn("hl-av--x", html_out)
        self.assertIn("ico-x", html_out)
        self.assertIn("<svg", html_out)

    def test_get_source_logo_html_social_youtube(self):
        html_out = get_source_logo_html("YouTube", link="https://youtube.com/watch?v=123")
        self.assertIn("hl-av--social", html_out)
        self.assertIn("<svg", html_out)

    def test_get_x_author_avatar_html(self):
        account = {
            "name": "Kathmandu Post",
            "handle": "@kathmandupost",
            "avatar_bg": "#111827",
            "initials": "KP",
        }
        avatar_html = get_x_author_avatar_html(account)
        self.assertIn('class="x-avatar"', avatar_html)
        self.assertIn('src="https://unavatar.io/x/kathmandupost"', avatar_html)
        self.assertIn('class="x-avatar-fb">KP</span>', avatar_html)
        self.assertIn('class="x-avatar-platform-badge"', avatar_html)

    def test_get_x_author_avatar_directory_mode(self):
        account = {
            "name": "Bipin Adhikari",
            "handle": "BipinAdhikari_",
            "avatar_bg": "#047857",
            "initials": "BA",
        }
        avatar_html = get_x_author_avatar_html(account, is_acct_card=True)
        self.assertIn('class="acct-card-rich__avatar"', avatar_html)
        self.assertIn('class="acct-card-rich__avatar-img"', avatar_html)
        self.assertIn('class="acct-card-rich__avatar-fb">BA</span>', avatar_html)


if __name__ == "__main__":
    unittest.main()
