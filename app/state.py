"""
app/state.py
============
Persistent state management using a local JSON file (processed_ids.json).

Tracks:
  - Comment/reply IDs that have already been responded to (to avoid duplicates).
  - The last published post ID (for quote-post feature).
  - The last published post text (for contextual replies).

In GitHub Actions, this file is committed back to the repo after each run
so state persists across scheduled workflow executions.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

STATE_FILE = os.environ.get("STATE_FILE", "processed_ids.json")

# Default structure for a fresh state file
_DEFAULT_STATE = {
    "processed_comment_ids": [],
    "last_post_id": None,
    "last_post_text": "",
    "total_posts_made": 0,
    "total_replies_made": 0,
}


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------


def load_state() -> dict:
    """Load state from the JSON file. Returns default state if file not found."""
    if not os.path.exists(STATE_FILE):
        logger.info("No state file found at '%s'. Starting with fresh state.", STATE_FILE)
        return dict(_DEFAULT_STATE)

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge with defaults to handle missing keys from older state files
        for key, default_val in _DEFAULT_STATE.items():
            data.setdefault(key, default_val)
        logger.info(
            "State loaded: %d processed comments, last_post_id=%s",
            len(data["processed_comment_ids"]),
            data["last_post_id"],
        )
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load state file: %s. Resetting to defaults.", exc)
        return dict(_DEFAULT_STATE)


def save_state(state: dict) -> None:
    """Persist state to the JSON file."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        logger.info("State saved to '%s'.", STATE_FILE)
    except OSError as exc:
        logger.error("Failed to save state file: %s", exc)


# ---------------------------------------------------------------------------
# Comment ID Tracking
# ---------------------------------------------------------------------------


def is_comment_processed(state: dict, comment_id: str) -> bool:
    """Return True if the given comment ID has already been replied to."""
    return comment_id in state.get("processed_comment_ids", [])


def mark_comment_processed(state: dict, comment_id: str) -> None:
    """Add a comment ID to the processed set."""
    ids = state.setdefault("processed_comment_ids", [])
    if comment_id not in ids:
        ids.append(comment_id)
    # Keep the list bounded (max 2000 entries) to avoid unbounded growth
    if len(ids) > 2000:
        state["processed_comment_ids"] = ids[-2000:]


# ---------------------------------------------------------------------------
# Last Post Tracking
# ---------------------------------------------------------------------------


def set_last_post(state: dict, post_id: str, post_text: str) -> None:
    """Record the last published post ID and text."""
    state["last_post_id"] = post_id
    state["last_post_text"] = post_text
    state["total_posts_made"] = state.get("total_posts_made", 0) + 1


def get_last_post_id(state: dict) -> Optional[str]:
    """Return the last published post ID, or None."""
    return state.get("last_post_id")


def get_last_post_text(state: dict) -> str:
    """Return the last published post text."""
    return state.get("last_post_text", "")


def increment_replies(state: dict) -> None:
    """Increment the total replies counter."""
    state["total_replies_made"] = state.get("total_replies_made", 0) + 1
