"""
app/threads_client.py
=====================
Meta Threads API Client
Handles:
  - Text post publishing (2-step: create container -> publish)
  - Image post publishing (media_type: IMAGE)
  - Quote post publishing (quote_post_id)
  - Fetching replies/comments on a post
  - Replying to a specific comment (reply_to_id)

Official API docs: https://developers.facebook.com/docs/threads
"""

import os
import time
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "")

BASE_URL = "https://graph.threads.net/v1.0"

# Delay between container creation and publish (Threads API requirement: >= 30s)
PUBLISH_DELAY_SECONDS = 33

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _headers() -> dict:
    return {"Authorization": f"Bearer {THREADS_ACCESS_TOKEN}"}


def _get_user_id() -> str:
    """Fetch the authenticated user's Threads user ID if not cached in env."""
    if THREADS_USER_ID:
        return THREADS_USER_ID
    url = f"{BASE_URL}/me"
    resp = requests.get(url, headers=_headers(), params={"fields": "id"}, timeout=15)
    resp.raise_for_status()
    uid = resp.json().get("id")
    if not uid:
        raise RuntimeError("Could not retrieve Threads user ID from /me endpoint.")
    logger.info("Resolved Threads user ID: %s", uid)
    return uid


def _create_media_container(payload: dict) -> str:
    """
    Step 1 — Create a Threads media container.
    Returns the container ID.
    """
    user_id = _get_user_id()
    url = f"{BASE_URL}/{user_id}/threads"
    payload["access_token"] = THREADS_ACCESS_TOKEN

    resp = requests.post(url, data=payload, timeout=20)
    if not resp.ok:
        logger.error("Container creation failed: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()

    container_id = resp.json().get("id")
    if not container_id:
        raise RuntimeError(f"No container ID returned: {resp.json()}")
    logger.info("Container created: %s", container_id)
    return container_id


def _publish_container(container_id: str) -> str:
    """
    Step 2 — Publish the Threads media container.
    Returns the published post/thread ID.
    """
    user_id = _get_user_id()
    url = f"{BASE_URL}/{user_id}/threads_publish"
    payload = {
        "creation_id": container_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }

    resp = requests.post(url, data=payload, timeout=20)
    if not resp.ok:
        logger.error("Publish failed: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()

    post_id = resp.json().get("id")
    if not post_id:
        raise RuntimeError(f"No post ID returned: {resp.json()}")
    logger.info("Post published successfully. Thread ID: %s", post_id)
    return post_id


# ---------------------------------------------------------------------------
# Public Publishing Methods
# ---------------------------------------------------------------------------


def post_text(text: str) -> str:
    """
    Publish a plain text post to Threads.

    Args:
        text: The post content (<= 500 characters).

    Returns:
        The published thread ID.
    """
    if len(text) > 500:
        logger.warning("Text exceeds 500 chars (%d), trimming.", len(text))
        text = text[:497] + "..."

    payload = {
        "media_type": "TEXT",
        "text": text,
    }
    container_id = _create_media_container(payload)

    logger.info("Waiting %ds before publishing...", PUBLISH_DELAY_SECONDS)
    time.sleep(PUBLISH_DELAY_SECONDS)

    return _publish_container(container_id)


def post_image(image_url: str, caption: str) -> str:
    """
    Publish an image post to Threads.

    Args:
        image_url: Publicly accessible URL of the image.
        caption: Caption text for the image post (<= 500 chars).

    Returns:
        The published thread ID.
    """
    if len(caption) > 500:
        logger.warning("Caption exceeds 500 chars (%d), trimming.", len(caption))
        caption = caption[:497] + "..."

    payload = {
        "media_type": "IMAGE",
        "image_url": image_url,
        "text": caption,
    }
    container_id = _create_media_container(payload)

    logger.info("Waiting %ds before publishing image post...", PUBLISH_DELAY_SECONDS)
    time.sleep(PUBLISH_DELAY_SECONDS)

    return _publish_container(container_id)


def post_quote(text: str, quote_post_id: str) -> str:
    """
    Publish a quote post that references an existing Threads post.

    Args:
        text: Your reaction/commentary text.
        quote_post_id: The thread ID of the post you are quoting.

    Returns:
        The published thread ID.
    """
    if len(text) > 500:
        text = text[:497] + "..."

    payload = {
        "media_type": "TEXT",
        "text": text,
        "quote_post_id": quote_post_id,
    }
    container_id = _create_media_container(payload)

    logger.info("Waiting %ds before publishing quote post...", PUBLISH_DELAY_SECONDS)
    time.sleep(PUBLISH_DELAY_SECONDS)

    return _publish_container(container_id)


def reply_to_comment(reply_text: str, reply_to_id: str) -> str:
    """
    Reply to a specific comment or thread.

    Args:
        reply_text: The reply content.
        reply_to_id: The thread/comment ID to reply to.

    Returns:
        The published reply thread ID.
    """
    if len(reply_text) > 500:
        reply_text = reply_text[:497] + "..."

    payload = {
        "media_type": "TEXT",
        "text": reply_text,
        "reply_to_id": reply_to_id,
    }
    container_id = _create_media_container(payload)

    logger.info("Waiting %ds before publishing reply...", PUBLISH_DELAY_SECONDS)
    time.sleep(PUBLISH_DELAY_SECONDS)

    return _publish_container(container_id)


# ---------------------------------------------------------------------------
# Fetching Replies / Comments
# ---------------------------------------------------------------------------


def get_user_threads(limit: int = 5) -> list:
    """
    Fetch the authenticated user's recent Threads posts.

    Args:
        limit: Maximum number of posts to fetch.

    Returns:
        List of thread dicts with 'id' and 'text' fields.
    """
    user_id = _get_user_id()
    url = f"{BASE_URL}/{user_id}/threads"
    params = {
        "fields": "id,text,timestamp,media_type",
        "limit": limit,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    resp = requests.get(url, params=params, timeout=15)
    if not resp.ok:
        logger.error("Failed to fetch user threads: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()

    data = resp.json().get("data", [])
    logger.info("Fetched %d user threads.", len(data))
    return data


def get_thread_replies(thread_id: str) -> list:
    """
    Fetch replies/comments on a specific Threads post.

    Args:
        thread_id: The thread ID to fetch replies for.

    Returns:
        List of reply dicts with 'id', 'text', 'username' fields.
    """
    url = f"{BASE_URL}/{thread_id}/replies"
    params = {
        "fields": "id,text,timestamp,username",
        "access_token": THREADS_ACCESS_TOKEN,
    }
    resp = requests.get(url, params=params, timeout=15)
    if not resp.ok:
        logger.error("Failed to fetch replies for thread %s: %s %s",
                     thread_id, resp.status_code, resp.text)
        resp.raise_for_status()

    data = resp.json().get("data", [])
    logger.info("Fetched %d replies for thread %s.", len(data), thread_id)
    return data
