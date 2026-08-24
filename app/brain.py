"""
main.py
=======
Orchestrator for the automated Threads AI Bot.
"""

import logging
import os
import random
import sys

from app import brain, state, threads_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def run_post(current_state: dict) -> None:
    """Selects a random mode and publishes a post to Threads."""
    modes = ["GAMING", "ANIME", "VALORANT", "IMAGE"]
    selected_mode = random.choice(modes)
    logger.info("Mode selected: %s", selected_mode)

    post_id = None
    post_text = ""

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
        logger.warning("No post ID generated for mode: %s", selected_mode)


def run_engagement(current_state: dict) -> None:
    """Scans recent posts and replies to new comments using Gemini."""
    logger.info("Starting engagement engine...")
    replies_made = 0

    try:
        threads = threads_client.get_user_threads(limit=3)
        for t in threads:
            t_id = t.get("id")
            t_text = t.get("text", "")
            if not t_id:
                continue

            logger.info("Checking replies for thread: %s", t_id)
            replies = threads_client.get_thread_replies(t_id)

            for rep in replies:
                rep_id = rep.get("id")
                rep_text = rep.get("text", "")
                rep_user = rep.get("username", "user")

                if not rep_id or state.is_comment_processed(current_state, rep_id):
                    continue

                bot_reply = brain.analyze_and_reply(
                    post_context=t_text,
                    comment_author=rep_user,
                    comment_text=rep_text,
                )

                if bot_reply:
                    logger.info("Replying to @%s on thread %s", rep_user, t_id)
                    threads_client.reply_to_comment(bot_reply, rep_id)
                    replies_made += 1
                    state.increment_replies(current_state)

                state.mark_comment_processed(current_state, rep_id)

    except Exception as exc:
        logger.warning("Engagement engine error: %s", exc)

    logger.info("Engagement engine done. Replied to %d new comments.", replies_made)


def main():
    logger.info("=" * 60)
    logger.info("Threads AI Bot starting...")
    logger.info("=" * 60)

    current_state = state.load_state()

    # 1. Check and refresh access token if eligible
    threads_client.check_and_refresh_token(current_state)

    # 2. Publish post
    try:
        run_post(current_state)
    except Exception as exc:
        logger.error("Post publishing failed: %s", exc, exc_info=True)

    # 3. Handle comment replies
    run_engagement(current_state)

    # 4. Save state
    state.save_state(current_state)
    logger.info("Bot run complete.")


if __name__ == "__main__":
    main()