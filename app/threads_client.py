"""
app/threads_client.py
=====================
Meta Threads API Client (Graph API v1.0).

Supports:
  - post_text()         -- plain text post
  - post_image()        -- image post (media_type: IMAGE)
  - post_quote()        -- quote post (quote_post_id)
  - reply_to_comment()  -- reply to a comment (reply_to_id)
  - get_user_threads()  -- fetch recent user posts
  - get_thread_replies()-- fetch replies on a post
  - get_active_token()  -- return best available access token
  - check_and_refresh_token() -- refresh long-lived token if eligible
"""

import logging
import os
import time
from typing import Optional

import requests

from app import state as _state

logger = logging.getLogger(__name__)

BASE_URL = "https://graph.threads.net/v1.0"

# Threads API requires >= 30s between container creation and publish
PUBLISH_DELAY_SECONDS = 33

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def get_active_token(current_state: Optional[dict] = None) -> str:
    """Return the best available access token (state cache > env var)."""
    if current_state:
        cached = current_state.get("current_token", "")
        if cached:
            return cached
    return os.environ.get("THREADS_ACCESS_TOKEN", "")


def check_and_refresh_token(current_state: dict) -> None:
    """
    Attempt to refresh the long-lived Threads access token.

    The Threads refresh endpoint accepts a token that is at least 24 hours
    old and returns a new token valid for 60 days. This is called once per
    bot run and silently skips on failure (token may not yet be eligible).
    """
    token = get_active_token(current_state)
    if not token:
        logger.warning("No access token available -- skipping refresh check.")
        return

    try:
        url = f"{BASE_URL}/refresh_access_token"
        params = {
            "grant_type": "th_refresh_token",
            "access_token": token,
        }
        resp = requests.get(url, params=params, timeout=15)
        if resp.ok:
            new_token = resp.json().get("access_token", "")
            if new_token and new_token != token:
                logger.info("Access token refreshed successfully.")
                _state.set_active_token(current_state, new_token)
            else:
                logger.info("Token refresh returned same token -- still valid.")
        else:
            # 400 usually means too early to refresh (< 24h old); not an error
            logger.info(
                "Token refresh skipped (HTTP %d): %s",
                resp.status_code, resp.json().get("error", {}).get("message", ""),
            )
    except Exception as exc:
        logger.warning("Token refresh attempt failed: %s", exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _auth_headers(current_state: Optional[dict] = None) -> dict:
    return {"Authorization": f"Bearer {get_active_token(current_state)}"}


def _resolve_user_id(current_state: Optional[dict] = None) -> str:
    """Return the Threads user ID from env or via API call."""
    uid = os.environ.get("THREADS_USER_ID", "")
    if uid:
        return uid
    resp = requests.get(
        f"{BASE_URL}/me",
        headers=_auth_headers(current_state),
        params={"fields": "id"},
        timeout=15,
    )
    resp.raise_for_status()
    uid = resp.json().get("id", "")
    if not uid:
        raise RuntimeError("Could not resolve Threads user ID from /me.")
    logger.info("Resolved Threads user ID: %s", uid)
    return uid


def _create_container(payload: dict, current_state: Optional[dict] = None) -> str:
    """Step 1: Create a Threads media container. Returns container ID."""
    uid = _resolve_user_id(current_state)
    url = f"{BASE_URL}/{uid}/threads"
    payload["access_token"] = get_active_token(current_state)

    resp = requests.post(url, data=payload, timeout=20)
    if not resp.ok:
        logger.error("Container creation failed [%d]: %s", resp.status_code, resp.text)
        resp.raise_for_status()

    cid = resp.json().get("id")
    if not cid:
        raise RuntimeError(f"No container ID in response: {resp.json()}")
    logger.info("Container created: %s", cid)
    return cid


def _publish_container(container_id: str, current_state: Optional[dict] = None) -> str:
    """Step 2: Publish a Threads container. Returns published thread ID."""
    uid = _resolve_user_id(current_state)
    url = f"{BASE_URL}/{uid}/threads_publish"
    payload = {
        "creation_id": container_id,
        "access_token": get_active_token(current_state),
    }
    resp = requests.post(url, data=payload, timeout=20)
    if not resp.ok:
        logger.error("Publish failed [%d]: %s", resp.status_code, resp.text)
        resp.raise_for_status()

    pid = resp.json().get("id")
    if not pid:
        raise RuntimeError(f"No post ID in response: {resp.json()}")
    logger.info("Thread published: %s", pid)
    return pid


def _two_step_publish(payload: dict, current_state: Optional[dict] = None) -> str:
    """Full 2-step create-and-publish flow with mandatory delay."""
    cid = _create_container(payload, current_state)
    logger.info("Waiting %ds before publish...", PUBLISH_DELAY_SECONDS)
    time.sleep(PUBLISH_DELAY_SECONDS)
    return _publish_container(cid, current_state)


# ---------------------------------------------------------------------------
# Public publishing API
# ---------------------------------------------------------------------------


def post_text(text: str, current_state: Optional[dict] = None) -> str:
    """Publish a plain text post. Returns thread ID."""
    if len(text) > 500:
        text = text[:497] + "..."
    return _two_step_publish({"media_type": "TEXT", "text": text}, current_state)


def post_image(image_url: str, caption: str, current_state: Optional[dict] = None) -> str:
    """Publish an image post. Returns thread ID."""
    if len(caption) > 500:
        caption = caption[:497] + "..."
    return _two_step_publish(
        {"media_type": "IMAGE", "image_url": image_url, "text": caption},
        current_state,
    )


def post_quote(text: str, quote_post_id: str, current_state: Optional[dict] = None) -> str:
    """Publish a quote post referencing an existing thread. Returns thread ID."""
    if len(text) > 500:
        text = text[:497] + "..."
    return _two_step_publish(
        {"media_type": "TEXT", "text": text, "quote_post_id": quote_post_id},
        current_state,
    )


def reply_to_comment(
    reply_text: str,
    reply_to_id: str,
    current_state: Optional[dict] = None,
) -> str:
    """Post a reply to an existing comment/thread. Returns reply thread ID."""
    if len(reply_text) > 500:
        reply_text = reply_text[:497] + "..."
    return _two_step_publish(
        {"media_type": "TEXT", "text": reply_text, "reply_to_id": reply_to_id},
        current_state,
    )


# ---------------------------------------------------------------------------
# Fetching user threads and replies
# ---------------------------------------------------------------------------


def get_user_threads(limit: int = 5, current_state: Optional[dict] = None) -> list:
    """Fetch the authenticated user's recent Threads posts."""
    uid = _resolve_user_id(current_state)
    params = {
        "fields": "id,text,timestamp,media_type",
        "limit": limit,
        "access_token": get_active_token(current_state),
    }
    resp = requests.get(f"{BASE_URL}/{uid}/threads", params=params, timeout=15)
    if not resp.ok:
        logger.error("get_user_threads failed [%d]: %s", resp.status_code, resp.text)
        resp.raise_for_status()
    data = resp.json().get("data", [])
    logger.info("Fetched %d user threads.", len(data))
    return data


def get_thread_replies(thread_id: str, current_state: Optional[dict] = None) -> list:
    """Fetch replies/comments on a specific Threads post."""
    params = {
        "fields": "id,text,timestamp,username",
        "access_token": get_active_token(current_state),
    }
    resp = requests.get(f"{BASE_URL}/{thread_id}/replies", params=params, timeout=15)
    if not resp.ok:
        logger.error("get_thread_replies [%s] failed [%d]: %s",
                     thread_id, resp.status_code, resp.text)
        resp.raise_for_status()
    data = resp.json().get("data", [])
    logger.info("Fetched %d replies for thread %s.", len(data), thread_id)
    return data