"""
main.py
=======
Orchestrator — wires together the Gemini Brain, Threads Client, and State Manager.

Execution flow:
  1. Load persistent state.
  2. Randomly pick a post mode (gaming / anime / valorant / image).
     - Every ~4th run, attempt a quote-post of the last published thread.
  3. Generate content via Gemini (brain.py).
  4. Publish to Threads (threads_client.py).
  5. Process replies on recent posts and auto-reply via Gemini.
  6. Save updated state back to disk.

In GitHub Actions the state file is committed back to the repo automatically.
"""

import logging
import os
import random
import sys

from dotenv import load_dotenv

# Load .env for local development (no-op in GitHub Actions where secrets are env vars)
load_dotenv()

from app import brain, threads_client, state

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
# Image hosting helper
# ---------------------------------------------------------------------------

def _get_image_url_from_prompt(image_prompt: str, theme: str) -> str:
    """
    Generate an image URL from a prompt.

    Strategy (in order):
      1. Use Pollinations.ai (free, no auth needed) for immediate, clean image URLs.
         URL format: https://image.pollinations.ai/prompt/{url_encoded_prompt}
      2. Fallback: a public placeholder themed image via picsum.photos.

    Pollinations.ai generates AI images on-the-fly and returns a stable URL
    that Threads can fetch directly -- no file hosting needed.
    """
    import urllib.parse

    # Pollinations.ai: free AI image generation, returns stable public URL
    encoded = urllib.parse.quote(image_prompt[:500])
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&nologo=true"
    logger.info("Image URL (Pollinations.ai): %s", url[:120] + "...")
    return url


# ---------------------------------------------------------------------------
# Core task: Publish a new post
# ---------------------------------------------------------------------------

def run_post(current_state: dict) -> None:
    """Choose a random mode and publish a Threads post."""
    modes = brain.get_post_modes()
    last_post_id = state.get_last_post_id(current_state)

    # Every ~4th run (25% chance), do a quote post if we have a previous post
    if last_post_id and random.random() < 0.25:
        logger.info("Mode: QUOTE POST (quoting last thread %s)", last_post_id)
        last_text = state.get_last_post_text(current_state)
        # Generate a fresh gaming or anime post as the "reaction" to quote with
        reaction_mode = random.choice(["gaming", "anime"])
        if reaction_mode == "gaming":
            reaction_text = brain.generate_gaming_post()
        else:
            reaction_text = brain.generate_anime_post()

        post_id = threads_client.post_quote(
            text=reaction_text,
            quote_post_id=last_post_id,
        )
        state.set_last_post(current_state, post_id, reaction_text)
        logger.info("Quote post published: %s", post_id)
        return

    # Standard random mode selection
    mode = random.choice(modes)
    logger.info("Mode selected: %s", mode.upper())

    if mode == "gaming":
        post_text = brain.generate_gaming_post()
        logger.info("Publishing gaming post (%d chars)...", len(post_text))
        post_id = threads_client.post_text(post_text)
        state.set_last_post(current_state, post_id, post_text)

    elif mode == "anime":
        post_text = brain.generate_anime_post()
        logger.info("Publishing anime post (%d chars)...", len(post_text))
        post_id = threads_client.post_text(post_text)
        state.set_last_post(current_state, post_id, post_text)

    elif mode == "valorant":
        post_text = brain.generate_valorant_post()
        logger.info("Publishing Valorant post (%d chars)...", len(post_text))
        post_id = threads_client.post_text(post_text)
        state.set_last_post(current_state, post_id, post_text)

    elif mode == "image":
        payload = brain.generate_image_post()
        image_url = _get_image_url_from_prompt(payload["image_prompt"], payload["theme"])
        logger.info("Publishing image post...")
        post_id = threads_client.post_image(image_url, payload["caption"])
        state.set_last_post(current_state, post_id, payload["caption"])

    logger.info("Post published. Thread ID: %s", post_id)


# ---------------------------------------------------------------------------
# Core task: Engagement Engine (reply to comments)
# ---------------------------------------------------------------------------

def run_engagement(current_state: dict) -> None:
    """Fetch recent thread replies and auto-respond using Gemini."""
    logger.info("Starting engagement engine...")

    try:
        recent_threads = threads_client.get_user_threads(limit=3)
    except Exception as exc:
        logger.error("Could not fetch user threads: %s", exc)
        return

    if not recent_threads:
        logger.info("No threads found to process replies for.")
        return

    total_replied = 0

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

        for reply in replies:
            reply_id = reply.get("id")
            reply_text = reply.get("text", "").strip()
            reply_username = reply.get("username", "unknown")

            if not reply_id or not reply_text:
                continue

            # Skip if already processed
            if state.is_comment_processed(current_state, reply_id):
                logger.debug("Already replied to comment %s, skipping.", reply_id)
                continue

            logger.info("Generating reply to @%s (comment: %s)...", reply_username, reply_id)

            try:
                reply_content = brain.generate_comment_reply(thread_text, reply_text)
            except Exception as exc:
                logger.warning("Brain failed to generate reply: %s", exc)
                state.mark_comment_processed(current_state, reply_id)
                continue

            if reply_content is None:
                logger.info("Skipping spam/irrelevant comment from @%s.", reply_username)
                state.mark_comment_processed(current_state, reply_id)
                continue

            try:
                threads_client.reply_to_comment(reply_content, reply_to_id=reply_id)
                state.mark_comment_processed(current_state, reply_id)
                state.increment_replies(current_state)
                total_replied += 1
                logger.info("Replied to @%s: %s", reply_username, reply_content[:60])
            except Exception as exc:
                logger.error("Failed to post reply to comment %s: %s", reply_id, exc)

    logger.info("Engagement engine done. Replied to %d new comments.", total_replied)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Main orchestrator. Returns exit code 0 on success, 1 on failure."""
    logger.info("=" * 60)
    logger.info("Threads AI Bot starting...")
    logger.info("=" * 60)

    # Validate required environment variables
    required_env = ["GEMINI_API_KEY", "THREADS_ACCESS_TOKEN"]
    missing = [k for k in required_env if not os.environ.get(k)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        logger.error("Please set them in .env (local) or GitHub Secrets (CI).")
        return 1

    # Load persistent state
    current_state = state.load_state()

    # Step 1: Publish a new post
    try:
        run_post(current_state)
    except Exception as exc:
        logger.error("Post publishing failed: %s", exc, exc_info=True)
        # Do not exit -- still attempt engagement engine

    # Step 2: Run engagement (reply to comments)
    try:
        run_engagement(current_state)
    except Exception as exc:
        logger.error("Engagement engine failed: %s", exc, exc_info=True)

    # Save updated state
    state.save_state(current_state)

    logger.info("Bot run complete. Stats: posts=%d, replies=%d",
                current_state.get("total_posts_made", 0),
                current_state.get("total_replies_made", 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
