"""
main.py
=======
Orchestrator for the automated Threads AI Bot.

Execution flow:
  1. Load persistent state.
  2. Check/refresh Threads access token.
  3. Randomly pick a post mode (GAMING / ANIME / VALORANT / IMAGE).
     - Every ~4th run attempt a quote-post of the last published thread.
  4. Generate content via Gemini (brain.py).
  5. Publish to Threads (threads_client.py).
  6. Process replies on recent posts and auto-reply via Gemini.
  7. Save updated state back to disk.
"""

import logging
import os
import random
import sys

from dotenv import load_dotenv

# Load .env for local development (no-op in GitHub Actions)
load_dotenv()

from app import brain, state, threads_client

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Core task: Publish a new post
# ---------------------------------------------------------------------------


def run_post(current_state: dict) -> None:
    """Selects a random mode and publishes a post to Threads."""
    modes = brain.get_post_modes()          # ["GAMING", "ANIME", "VALORANT", "IMAGE"]
    last_post_id = state.get_last_post_id(current_state)

    post_id = None      # Always initialised -- prevents UnboundLocalError
    post_text = ""

    # Every ~4th run (25% chance), quote the last post if one exists
    if last_post_id and random.random() < 0.25:
        logger.info("Mode: QUOTE POST (quoting %s)", last_post_id)
        reaction_mode = random.choice(["GAMING", "ANIME"])
        if reaction_mode == "GAMING":
            post_text = brain.generate_gaming_post()
        else:
            post_text = brain.generate_anime_post()

        post_id = threads_client.post_quote(text=post_text, quote_post_id=last_post_id)
        if post_id:
            state.set_last_post(current_state, post_id, post_text)
            logger.info("Quote post published: %s", post_id)
        return

    selected_mode = random.choice(modes)
    logger.info("Mode selected: %s", selected_mode)

    if selected_mode == "GAMING":
        post_text = brain.generate_gaming_post()
        logger.info("Publishing gaming post (%d chars)...", len(post_text))
        post_id = threads_client.post_text(post_text)

    elif selected_mode == "ANIME":
        post_text = brain.generate_anime_post()
        logger.info("Publishing anime post (%d chars)...", len(post_text))
        post_id = threads_client.post_text(post_text)

    elif selected_mode == "VALORANT":
        post_text = brain.generate_valorant_post()
        logger.info("Publishing Valorant post (%d chars)...", len(post_text))
        post_id = threads_client.post_text(post_text)

    elif selected_mode == "IMAGE":
        img_payload = brain.generate_image_post()
        post_text = img_payload["caption"]
        logger.info("Publishing AI image post...")
        post_id = threads_client.post_image(
            image_url=img_payload["image_url"],
            caption=post_text,
        )

    if post_id:
        logger.info("Post published. Thread ID: %s", post_id)
        state.set_last_post(current_state, post_id, post_text)
    else:
        logger.warning("No post ID returned for mode: %s", selected_mode)


# ---------------------------------------------------------------------------
# Core task: Engagement Engine (reply to comments)
# ---------------------------------------------------------------------------


def run_engagement(current_state: dict) -> None:
    """Fetch recent thread replies and auto-respond using Gemini."""
    logger.info("Starting engagement engine...")
    replies_made = 0

    try:
        recent_threads = threads_client.get_user_threads(limit=3)
    except Exception as exc:
        logger.error("Could not fetch user threads: %s", exc)
        return

    if not recent_threads:
        logger.info("No threads found to process replies for.")
        return

    for thread in recent_threads:
        thread_id = thread.get("id")
        thread_text = thread.get("text", "")

        if not thread_id:
            continue

        logger.info("Checking replies for thread: %s", thread_id)

        try:
            replies = threads_client.get_thread_replies(thread_id)
        except Exception as exc:
            logger.warning("Could not fetch replies for thread %s: %s", thread_id, exc)
            continue

        for rep in replies:
            rep_id = rep.get("id")
            rep_text = rep.get("text", "").strip()
            rep_user = rep.get("username", "unknown")

            if not rep_id or not rep_text:
                continue

            if state.is_comment_processed(current_state, rep_id):
                logger.debug("Already replied to %s, skipping.", rep_id)
                continue

            logger.info("Generating reply to @%s (comment %s)...", rep_user, rep_id)

            try:
                reply_content = brain.analyze_and_reply(
                    post_context=thread_text,
                    comment_author=rep_user,
                    comment_text=rep_text,
                )
            except Exception as exc:
                logger.warning("Brain failed to generate reply: %s", exc)
                state.mark_comment_processed(current_state, rep_id)
                continue

            if reply_content is None:
                logger.info("Skipping spam from @%s.", rep_user)
                state.mark_comment_processed(current_state, rep_id)
                continue

            try:
                threads_client.reply_to_comment(reply_content, reply_to_id=rep_id)
                state.mark_comment_processed(current_state, rep_id)
                state.increment_replies(current_state)
                replies_made += 1
                logger.info("Replied to @%s: %s", rep_user, reply_content[:60])
            except Exception as exc:
                logger.error("Failed to post reply to %s: %s", rep_id, exc)

    logger.info("Engagement engine done. Replied to %d new comments.", replies_made)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Main orchestrator. Returns exit code 0 on success, 1 on failure."""
    logger.info("=" * 60)
    logger.info("Threads AI Bot starting...")
    logger.info("=" * 60)

    required_env = ["GEMINI_API_KEY", "THREADS_ACCESS_TOKEN"]
    missing = [k for k in required_env if not os.environ.get(k)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        return 1

    current_state = state.load_state()

    # Check and refresh Threads token if eligible
    threads_client.check_and_refresh_token(current_state)

    # Publish post
    try:
        run_post(current_state)
    except Exception as exc:
        logger.error("Post publishing failed: %s", exc, exc_info=True)

    # Reply to comments
    try:
        run_engagement(current_state)
    except Exception as exc:
        logger.error("Engagement engine failed: %s", exc, exc_info=True)

    state.save_state(current_state)
    logger.info(
        "Bot run complete. posts=%d replies=%d",
        current_state.get("total_posts_made", 0),
        current_state.get("total_replies_made", 0),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())