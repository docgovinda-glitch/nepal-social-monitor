"""
media_logos.py
High-performance logo and avatar resolution engine for Nepali Media, Indian Press,
and Social Media (X/Twitter, etc.).

Features:
- Instant in-memory domain resolution for 70+ known media portals and social platforms
- Dynamic domain extraction for unlisted or newly added sources
- Zero-latency local caching via /app/static/media_logos/
- Automatic high-res CDN fallback (Google / DuckDuckGo favicon)
- Inline crisp SVG vector logos for social platforms (X, YouTube, Facebook)
- Bulletproof multi-tier fallback: Local Image -> Remote Favicon -> Lettered Initials
"""

import html
import os
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

# Pre-scan available local logo files
_STATIC_MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "media_logos")
try:
    if os.path.isdir(_STATIC_MEDIA_DIR):
        _LOCAL_LOGOS = set(os.listdir(_STATIC_MEDIA_DIR))
    else:
        _LOCAL_LOGOS = set()
except Exception:
    _LOCAL_LOGOS = set()

# Official SVG paths for crisp zero-latency vector rendering
_X_LOGO_SVG = (
    '<svg class="ico-x" width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
    '<path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>'
    '</svg>'
)

_X_MINI_SVG = (
    '<svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
    '<path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>'
    '</svg>'
)

_YT_LOGO_SVG = (
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="#FF0000" aria-hidden="true">'
    '<path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>'
    '</svg>'
)

_FB_LOGO_SVG = (
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="#1877F2" aria-hidden="true">'
    '<path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>'
    '</svg>'
)

# Comprehensive Normalized Domain Mapping
SOURCE_NAME_TO_DOMAIN: Dict[str, str] = {
    # Nepal National Dailies & Major Portals
    "ekantipur": "ekantipur.com",
    "ekantipur.com": "ekantipur.com",
    "kantipur": "ekantipur.com",
    "kantipur daily": "ekantipur.com",
    "onlinekhabar": "onlinekhabar.com",
    "onlinekhabar (np)": "onlinekhabar.com",
    "onlinekhabar (en)": "english.onlinekhabar.com",
    "online khabar": "onlinekhabar.com",
    "online khabar nepali": "onlinekhabar.com",
    "online khabar english": "english.onlinekhabar.com",
    "setopati": "setopati.com",
    "setopati (en)": "en.setopati.com",
    "setopati english": "en.setopati.com",
    "ratopati": "ratopati.com",
    "ratopati (en)": "english.ratopati.com",
    "ratopati english": "english.ratopati.com",
    "annapurna post": "annapurnapost.com",
    "annapurnapost": "annapurnapost.com",
    "the annapurna express": "theannapurnaexpress.com",
    "annapurna express": "theannapurnaexpress.com",
    "nagarik news": "nagariknetwork.com",
    "nagarik": "nagariknetwork.com",
    "nagarik daily": "nagariknetwork.com",
    "nagarik network": "nagariknetwork.com",
    "naya patrika": "nayapatrikadaily.com",
    "nayapatrika": "nayapatrikadaily.com",
    "nepalkhabar": "nepalkhabar.com",
    "nepalkhabar (en)": "en.nepalkhabar.com",
    "nepal khabar": "nepalkhabar.com",
    "gorkhapatra online": "gorkhapatraonline.com",
    "gorkhapatra": "gorkhapatraonline.com",
    "gorkhapatra daily": "gorkhapatraonline.com",
    "news of nepal": "newsofnepal.com",
    "nepal press": "nepalpress.com",
    "nepalpress": "nepalpress.com",
    "baahrakhari": "baahrakhari.com",
    "himal press": "himalpress.com",
    "himalpress": "himalpress.com",
    "himal khabar": "himalkhabar.com",
    "deshsanchar": "deshsanchar.com",
    "shilapatra": "shilapatra.com",
    "nepal live": "nepallive.com",
    "nepallive": "nepallive.com",
    "nepal aaja": "nepalaaja.com",
    "nepalaaja": "nepalaaja.com",
    "nepal news": "nepalnews.com",
    "nepalnews": "nepalnews.com",
    "nepal news (en)": "english.nepalnews.com",
    "nepalnews (en)": "english.nepalnews.com",
    "image khabar": "imagekhabar.com",
    "imagekhabar": "imagekhabar.com",
    "image channel": "imagechannel.com.np",
    "khabarhub": "khabarhub.com",
    "khabarhub (np)": "khabarhub.com",
    "khabarhub (en)": "english.khabarhub.com",
    "techpana": "techpana.com",
    "arthasarokar": "arthasarokar.com",
    "artha sarokar": "arthasarokar.com",
    "the kathmandu post": "kathmandupost.com",
    "kathmandu post": "kathmandupost.com",
    "the himalayan times": "thehimalayantimes.com",
    "the himalayan": "thehimalayantimes.com",
    "himalayan times": "thehimalayantimes.com",
    "myrepublica": "myrepublica.nagariknetwork.com",
    "republica": "myrepublica.nagariknetwork.com",
    "my republica": "myrepublica.nagariknetwork.com",
    "rising nepal daily": "risingnepaldaily.com",
    "the rising nepal": "risingnepaldaily.com",
    "rising nepal": "risingnepaldaily.com",
    "bbc news nepali": "bbc.com",
    "bbc nepali": "bbc.com",
    "bbc": "bbc.com",
    "bizmandu": "bizmandu.com",
    "bizpati": "bizpati.com",
    "bizshala": "bizshala.com",
    "clickmandu": "clickmandu.com",
    "ujyaalo online": "ujyaaloonline.com",
    "swasthya khabar": "swasthyakhabar.com",
    "ap1 tv": "ap1.tv",
    "ap1 hd television": "ap1.tv",
    "cij nepal": "cijnepal.org",
    "cricnepal": "cricnepal.com",

    # Top Indian Media
    "the indian express": "indianexpress.com",
    "indian express": "indianexpress.com",
    "the hindu": "thehindu.com",
    "hindustan times": "hindustantimes.com",
    "the times of india": "timesofindia.indiatimes.com",
    "times of india": "timesofindia.indiatimes.com",
    "the economic times": "economictimes.indiatimes.com",
    "economic times": "economictimes.indiatimes.com",
    "the tribune": "tribuneindia.com",
    "tribune": "tribuneindia.com",
    "india today": "indiatoday.in",
    "abp live": "abplive.com",
    "abp news": "abplive.com",
    "ndtv": "ndtv.com",
    "livemint": "livemint.com",
    "mint": "livemint.com",
    "business standard": "business-standard.com",
    "financial express": "financialexpress.com",
    "moneycontrol": "moneycontrol.com",
    "outlook india": "outlookindia.com",
    "deccan chronicle": "deccanchronicle.com",
    "the quint": "thequint.com",
    "quint": "thequint.com",
    "swarajya": "swarajyamag.com",
    "oneindia": "oneindia.com",
    "ani news": "aninews.in",
    "ani": "aninews.in",
    "pti": "ptinews.com",
    "the print": "theprint.in",
    "the wire": "thewire.in",
    "wion": "wionews.com",
    "firstpost": "firstpost.com",
    "deccan herald": "deccanherald.com",
    "news18": "news18.com",
    "amar ujala": "amarujala.com",
    "live hindustan": "livehindustan.com",
    "dainik jagran": "jagran.com",
    "jagran": "jagran.com",
    "navbharat times": "navbharattimes.indiatimes.com",
    "jansatta": "jansatta.com",
    "prabhat khabar": "prabhatkhabar.com",
    "aaj tak": "aajtak.in",
    "dainik bhaskar": "bhaskar.com",
    "zee news": "zeenews.india.com",

    # Social Media Platforms
    "x": "x.com",
    "twitter": "x.com",
    "x (twitter)": "x.com",
    "facebook": "facebook.com",
    "youtube": "youtube.com",
    "instagram": "instagram.com",
    "tiktok": "tiktok.com",
    "threads": "threads.net",
    "reddit": "reddit.com",
    "linkedin": "linkedin.com",
    "whatsapp": "whatsapp.com",
}


def _source_initials(name: str) -> str:
    """Computes a 1-2 character abbreviation fallback for any source name."""
    parts = re.findall(r"[A-Za-z0-9\u0900-\u097F]+", name or "")
    if not parts:
        return "•"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def resolve_media_domain(source_name: str, link: str = "") -> str:
    """
    Resolves the canonical internet domain for a given source name or article URL.
    Returns clean domain (e.g. 'ekantipur.com') or empty string if undetermined.
    """
    clean_src = (source_name or "").strip().lower()
    if clean_src in SOURCE_NAME_TO_DOMAIN:
        return SOURCE_NAME_TO_DOMAIN[clean_src]

    # Partial / fuzzy matches for source name
    for k, d in SOURCE_NAME_TO_DOMAIN.items():
        if k in clean_src or clean_src in k:
            return d

    # If not found in dictionary, extract directly from article link
    if link:
        try:
            parsed = urlparse(link)
            host = parsed.netloc.lower().split(":")[0]
            if host:
                if host.startswith("www."):
                    host = host[4:]
                return host
        except Exception:
            pass

    return ""


def get_source_logo_urls(domain: str) -> Tuple[str, str]:
    """
    Returns (primary_src, fallback_src) for a given domain.
    Favors local static files when pre-cached, falling back to CDN.
    """
    if not domain:
        return ("", "")

    png_name = f"{domain}.png"
    if png_name in _LOCAL_LOGOS:
        primary = f"/app/static/media_logos/{png_name}"
        fallback = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        return (primary, fallback)

    # If domain has a subdomain (e.g. english.onlinekhabar.com), check base domain
    parts = domain.split(".")
    if len(parts) > 2:
        base_domain = ".".join(parts[-2:])
        base_png = f"{base_domain}.png"
        if base_png in _LOCAL_LOGOS:
            primary = f"/app/static/media_logos/{base_png}"
            fallback = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
            return (primary, fallback)

    primary = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
    fallback = f"https://icons.duckduckgo.com/ip3/{domain}.ico"
    return (primary, fallback)


def get_source_logo_html(
    source_name: str,
    link: str = "",
    is_indian: bool = False,
    extra_class: str = "",
) -> str:
    """
    Generates high-fidelity HTML for a media source logo or social media badge.
    - If social platform (X/Twitter, YouTube, Facebook): returns crisp inline SVG
    - If media outlet: returns rounded logo tile with lazy loading and initials fallback
    """
    clean_src = (source_name or "Unknown").strip()
    src_lower = clean_src.lower()

    # 1. Social Platforms - zero network vector icons
    if src_lower in ("x", "twitter", "x (twitter)") or "x.com" in link or "twitter.com" in link:
        return (
            f'<span class="hl-av hl-av--x {extra_class}" title="X (formerly Twitter)">'
            f'{_X_LOGO_SVG}'
            f'</span>'
        )
    if "youtube" in src_lower or "youtube.com" in link or "youtu.be" in link:
        return (
            f'<span class="hl-av hl-av--social {extra_class}" title="YouTube">'
            f'{_YT_LOGO_SVG}'
            f'</span>'
        )
    if "facebook" in src_lower or "facebook.com" in link:
        return (
            f'<span class="hl-av hl-av--social {extra_class}" title="Facebook">'
            f'{_FB_LOGO_SVG}'
            f'</span>'
        )

    # 2. Media Outlets
    domain = resolve_media_domain(clean_src, link=link)
    in_class = " hl-av--in" if is_indian else ""
    esc_name = html.escape(clean_src, quote=True)
    initials = html.escape(_source_initials(clean_src))

    if domain:
        primary_src, fallback_src = get_source_logo_urls(domain)
        return (
            f'<span class="hl-av{in_class} {extra_class}" title="{esc_name}">'
            f'<img src="{html.escape(primary_src, quote=True)}" '
            f'data-fallback-src="{html.escape(fallback_src, quote=True)}" '
            f'alt="" class="hl-av-img" loading="lazy" />'
            f'<span class="hl-av-fb">{initials}</span>'
            f'</span>'
        )

    # 3. Graceful fallback if no domain could be resolved
    return (
        f'<span class="hl-av{in_class} {extra_class}" title="{esc_name}">'
        f'<span class="hl-av-fb">{initials}</span>'
        f'</span>'
    )


def get_x_author_avatar_html(
    p: Dict[str, Any],
    is_acct_card: bool = False,
) -> str:
    """
    Renders an authenticated X author avatar.
    Displays real profile avatar image with fallback to author initials on avatar_bg,
    adorned with an official mini-X badge in the bottom-right corner.
    """
    clean_handle = (p.get("raw_handle") or p.get("handle") or "").lstrip("@").strip()
    raw_initials = p.get("initials") or (clean_handle[:2].upper() if clean_handle else "X")
    initials = html.escape(raw_initials)
    avatar_bg = html.escape(p.get("avatar_bg") or "#1D9BF0", quote=True)
    avatar_url = (p.get("avatar_url") or "").strip()
    if not avatar_url and clean_handle:
        avatar_url = f"https://unavatar.io/x/{clean_handle}"

    esc_url = html.escape(avatar_url, quote=True) if avatar_url else ""
    card_cls = "acct-card-rich__avatar" if is_acct_card else "x-avatar"
    img_cls = "acct-card-rich__avatar-img" if is_acct_card else "x-avatar-img"
    fb_cls = "acct-card-rich__avatar-fb" if is_acct_card else "x-avatar-fb"

    img_tag = f'<img src="{esc_url}" alt="" class="{img_cls}" loading="lazy" />' if esc_url else ""

    return (
        f'<div class="{card_cls}" style="background:{avatar_bg};">'
        f'{img_tag}'
        f'<span class="{fb_cls}">{initials}</span>'
        f'<span class="x-avatar-platform-badge" title="X (Twitter)">{_X_MINI_SVG}</span>'
        f'</div>'
    )
