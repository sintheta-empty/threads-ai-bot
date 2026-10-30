"""
app/brain.py
============
Gemini AI Engine for conversational, human-like Threads posts and replies.
Focuses on casual gaming/anime discussions, mini-reviews, hot takes, and debates.
"""

import logging
import os
import random
import time
import urllib.parse
from typing import Dict, List, Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini API Configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Use the latest flash model
MODEL_NAME = "gemini-2.5-flash"


def get_post_modes() -> List[str]:
    """Available post modes."""
    return ["HOT_TAKE", "MINI_REVIEW", "QUESTION_DEBATE", "IMAGE_THOUGHT"]


def _get_model():
    return genai.GenerativeModel(
        MODEL_NAME,
        generation_config={
            "temperature": 0.95,  # Higher temperature gives more creative, casual variety
            "top_p": 0.95,
            "max_output_tokens": 300,
        },
    )


def _safe_generate(prompt: str, max_retries: int = 3) -> str:
    """Executes a prompt through Gemini with retry backoff."""
    model = _get_model()
    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip().strip('"')
            raise RuntimeError("Empty response from Gemini.")
        except Exception as exc:
            logger.warning(
                "Gemini generation error (attempt %d/%d): %s",
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                time.sleep(2**attempt)
            else:
                raise RuntimeError(f"Gemini API failed after {max_retries} attempts: {exc}")


def _clean_for_threads(text: str) -> str:
    """Cleans up markdown quotes and limits length to fit Threads."""
    text = text.strip().strip('"').strip("'")
    if len(text) > 490:
        text = text[:485] + "..."
    return text


# ---------------------------------------------------------------------------
# Human-Style Content Generators
# ---------------------------------------------------------------------------


def generate_hot_take_post() -> str:
    """Generates an opinionated, casual hot take to drive comments."""
    prompt = (
        "Write a short, casual Threads post giving a slightly controversial hot take "
        "about modern gaming, anime, or gaming habits (e.g. Elden Ring vs casual open worlds, "
        "anime pacing, overpriced game remakes, live-service fatigue, or ranked tilt).\n\n"
        "Writing Guidelines:\n"
        "- Write like a real 20-something gamer on Threads/Twitter, NOT an AI or marketer.\n"
        "- Casual, punchy tone. You can use lowercase openings or informal cadence.\n"
        "- NO generic quotes, NO corporate motivational talk.\n"
        "- End with a short punchline or an invitation to disagree (e.g. 'tell me I'm wrong', 'or is it just me?').\n"
        "- Max 1 relevant hashtag or NO hashtags at all (real people rarely spam hashtags).\n"
        "- Under 280 characters total."
    )
    return _clean_for_threads(_safe_generate(prompt))


def generate_mini_review_post() -> str:
    """Generates a raw, personal mini-review of a game or anime."""
    prompt = (
        "Write a realistic, 2-3 sentence personal mini-review of a specific game or anime "
        "(e.g. Cyberpunk 2077, Vinland Saga, Monster, Witcher 3, Sekiro, Jujutsu Kaisen, or Valorant).\n\n"
        "Writing Guidelines:\n"
        "- Start naturally like: 'Just finished...', 'Replaying X and...', or 'Still thinking about...'.\n"
        "- Mention one very specific detail (soundtrack, an emotional scene, a frustrating boss/mechanic).\n"
        "- Give an honest rating or final impression (e.g. 'solid 8/10', 'overhyped but fun', 'genuinely peak fiction').\n"
        "- Zero corporate speak. Do NOT use emojis like 🚀, 🤖, or 🌟.\n"
        "- Under 300 characters total."
    )
    return _clean_for_threads(_safe_generate(prompt))


def generate_question_debate_post() -> str:
    """Generates an engaging question to make people reply and argue in the comments."""
    prompt = (
        "Write an engaging, casual question/debate prompt for gamers and anime fans on Threads.\n\n"
        "Topic Ideas:\n"
        "- 'What's a game you loved as a kid that aged horribly?'\n"
        "- 'Name an anime where the villain was actually 100% right.'\n"
        "- 'Valorant solo queue: what agent pick instantly makes you think you lost?'\n"
        "- 'A single game mechanic that instantly ruins the experience for you?'\n\n"
        "Writing Guidelines:\n"
        "- Keep it short, blunt, and super conversational (1-2 sentences).\n"
        "- Make it easy and tempting for someone scrolling by to drop a 1-word or 1-sentence reply.\n"
        "- NO hashtags, NO emojis, natural lowercase or normal punctuation.\n"
        "- Under 200 characters total."
    )
    return _clean_for_threads(_safe_generate(prompt))


def generate_gaming_post() -> str:
    """Alias for backwards compatibility with main orchestrator."""
    return generate_hot_take_post()


def generate_anime_post() -> str:
    """Alias for backwards compatibility with main orchestrator."""
    return generate_mini_review_post()


def generate_valorant_post() -> str:
    """Alias for backwards compatibility with main orchestrator."""
    return generate_question_debate_post()


# ---------------------------------------------------------------------------
# AI Image Post Generator (Watermark-Free + Casual Caption)
# ---------------------------------------------------------------------------


def generate_image_post() -> Dict[str, str]:
    """Generates an aesthetic image prompt and a casual, human-like caption."""
    concept_prompt = (
        "Write a 1-sentence prompt for a moody, aesthetic, cinematic concept art "
        "(e.g., dark cyber-room with blue ambient glow, lone knight under a shattered moon, "
        "or rainy anime street at midnight). Output ONLY the visual prompt."
    )
    visual_description = _safe_generate(concept_prompt)

    seed = random.randint(1000, 999999)
    encoded_prompt = urllib.parse.quote(visual_description)
    image_url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width=1080&height=1080&seed={seed}&nologo=true"
    )

    caption_prompt = (
        f"Write a very casual 1-sentence Threads caption for this picture: '{visual_description}'.\n"
        "Do NOT describe what's in the picture like a robot. Write a mood or thought, "
        "like: 'current aesthetic', 'need this vibe irl', or 'late night thoughts'.\n"
        "Max 100 characters. No cringe hashtags."
    )
    caption = _clean_for_threads(_safe_generate(caption_prompt))

    return {
        "image_url": image_url,
        "caption": caption,
    }


# ---------------------------------------------------------------------------
# Engagement & Replies Brain
# ---------------------------------------------------------------------------


def analyze_and_reply(post_context: str, comment_author: str, comment_text: str) -> Optional[str]:
    """Generates authentic, short peer-to-peer replies to comments."""
    spam_check_prompt = (
        f"Classify if the following comment is spam, self-promotion, or a bot comment.\n"
        f"Comment: '{comment_text}'\n"
        "Reply strictly with either 'SPAM' or 'VALID'."
    )
    classification = _safe_generate(spam_check_prompt).upper()
    if "SPAM" in classification:
        logger.info("Comment by @%s classified as SPAM. Skipping.", comment_author)
        return None

    reply_prompt = (
        f"Context post: '{post_context}'\n"
        f"User @{comment_author} replied: '{comment_text}'\n\n"
        "Write a quick, authentic reply (1 short sentence, max 15 words).\n"
        "- Reply like a friend texting back (e.g., 'honestly valid', 'nah you're tripping', 'first playthrough was wild').\n"
        "- NO customer-support tone, NO 'Thanks for sharing!', NO hashtags.\n"
        "- Keep it super natural and casual."
    )
    reply_text = _safe_generate(reply_prompt)
    return _clean_for_threads(reply_text)
