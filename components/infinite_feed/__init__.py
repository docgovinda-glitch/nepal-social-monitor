"""
components/infinite_feed/__init__.py
Lightweight bidirectional Streamlit component for true incremental infinite-scroll feed rendering.
Appends only newly fetched 20-item batches to the DOM without reconstructing prior cards.
"""

import os
from typing import Any, Dict, List, Optional
import streamlit.components.v1 as components

_COMPONENT_DIR = os.path.dirname(os.path.abspath(__file__))
_infinite_feed_component = components.declare_component("infinite_feed", path=_COMPONENT_DIR)


def render_infinite_feed_component(
    session_key: str,
    batches: List[Dict[str, Any]],
    has_more: bool,
    total_count: int,
    loaded_count: int,
    noun: str,
    theme_css: str = "",
    error_msg: str = "",
    key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Renders the incremental infinite-scroll feed component.
    Each entry in `batches` is `{"seq": int, "html": str}`.
    Returns a dict event from JS when triggered:
      - {"event": "load_more", "next_seq": int, "ts": int}
      - {"event": "retry", "next_seq": int, "ts": int}
      - {"event": "action", "action": "read"|"share", "item_uid": str, "ts": int}
    """
    return _infinite_feed_component(
        session_key=session_key,
        batches=batches,
        has_more=bool(has_more),
        total_count=int(total_count),
        loaded_count=int(loaded_count),
        noun=str(noun),
        theme_css=theme_css,
        error_msg=str(error_msg or ""),
        default=None,
        key=key,
    )
