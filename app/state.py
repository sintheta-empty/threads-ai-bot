"""
app/state.py
============
Persistent JSON state management.

Reads and writes using standard UTF-8 (no BOM) to prevent decode errors
on Linux-based runners (GitHub Actions, Cloudflare Workers, etc.).

Tracks:
  - processed_comment_ids: set of comment IDs already replied to
  - last_post_id: most recently published Threads post ID
  - last_post_text: text of the most recent post (for reply context)
  - current_token: active access token (updated on refresh)
  - total_posts_made / total_replies_made: counters
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

STATE_FILE = os.environ.get("STATE_FILE", "processed_ids.json")

_DEFAULT_STATE: dict = {
    "processed_comment_ids": [],
    "last_post_id": None,
    "last_post_text": "",
    "current_token": "",
    "total_posts_made": 0,
    "total_replies_made": 0,
}

# ---------------------------------------------------------------------------
# Load / Save  (standard UTF-8, NO BOM)
# ---------------------------------------------------------------------------


def load_state() -> dict:
    """Load state from disk. Returns merged defaults if file is missing/corrupt."""
    if not os.path.exists(STATE_FILE):
        logger.info("No state file at '%s'. Using fresh state.", STATE_FILE)
        return dict(_DEFAULT_STATE)

    try:
        # Open with utf-8 (not utf-8-sig) -- file must be written BOM-free
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for key, default in _DEFAULT_STATE.items():
            data.setdefault(key, default)
        logger.info(
            "State loaded: %d processed IDs, last_post=%s",
            len(data["processed_comment_ids"]),
            data["last_post_id"],
        )
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load state (%s). Resetting to defaults.", exc)
        return dict(_DEFAULT_STATE)


def save_state(state: dict) -> None:
    """Persist state to disk using standard UTF-8 (no BOM)."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(state, fh, indent=2, ensure_ascii=False)
        logger.info("State saved to '%s'.", STATE_FILE)
    except OSError as exc:
        logger.error("Failed to save state: %s", exc)


# ---------------------------------------------------------------------------
# Comment ID tracking
# ---------------------------------------------------------------------------


def is_comment_processed(state: dict, comment_id: str) -> bool:
    return comment_id in state.get("processed_comment_ids", [])


def mark_comment_processed(state: dict, comment_id: str) -> None:
    ids: list = state.setdefault("processed_comment_ids", [])
    if comment_id not in ids:
        ids.append(comment_id)
    # Bound the list to avoid unbounded growth
    if len(ids) > 2000:
        state["processed_comment_ids"] = ids[-2000:]


# ---------------------------------------------------------------------------
# Last post tracking
# ---------------------------------------------------------------------------


def set_last_post(state: dict, post_id: str, post_text: str) -> None:
    state["last_post_id"] = post_id
    state["last_post_text"] = post_text
    state["total_posts_made"] = state.get("total_posts_made", 0) + 1


def get_last_post_id(state: dict) -> Optional[str]:
    return state.get("last_post_id")


def get_last_post_text(state: dict) -> str:
    return state.get("last_post_text", "")


# ---------------------------------------------------------------------------
# Token management helpers
# ---------------------------------------------------------------------------


def get_active_token(state: dict) -> str:
    """Return the cached refreshed token, or fall back to env var."""
    cached = state.get("current_token", "")
    if cached:
        return cached
    return os.environ.get("THREADS_ACCESS_TOKEN", "")


def set_active_token(state: dict, token: str) -> None:
    """Persist a refreshed token in state so threads_client can use it."""
    state["current_token"] = token


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------


def increment_replies(state: dict) -> None:
    state["total_replies_made"] = state.get("total_replies_made", 0) + 1