"""
app/brain.py
============
Gemini AI Brain -- handles all content generation:
  - Gaming quotes & philosophy
  - Anime quotes & deep thoughts
  - Valorant meta/lore news
  - Image prompt crafting (for Imagen / external generators)
  - Comment reply generation
"""

import os
import random
import logging
import textwrap
import time
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

GAMING_SOURCES = [
    "Elden Ring", "The Witcher 3", "God of War", "Dark Souls",
    "Hollow Knight", "Sekiro", "Cyberpunk 2077", "Red Dead Redemption 2",
    "Hades", "NieR: Automata",
]

ANIME_SOURCES = [
    "Attack on Titan", "Vinland Saga", "Jujutsu Kaisen", "Demon Slayer",
    "Hunter x Hunter", "Berserk", "Fullmetal Alchemist: Brotherhood",
    "Chainsaw Man", "Frieren: Beyond Journey's End", "Blue Lock",
]

VALORANT_AGENTS = [
    "Jett", "Reyna", "Sage", "Omen", "Killjoy", "Cypher", "Viper",
    "Chamber", "Neon", "Iso", "Clove", "Tejo", "Vyse",
]

HASHTAG_SETS = {
    "gaming": "#Gaming #GamingQuotes #EldenRing #GodOfWar #Witcher #GamePhilosophy #NightOwlGamer",
    "anime": "#Anime #AnimeQuotes #AttackOnTitan #JJK #VinlandSaga #AnimeWisdom #DemonSlayer",
    "valorant": "#Valorant #VCT #VALORANT #EsportsNews #FPS #ValorantLore #PROScene",
    "image": "#AIArt #GamingArt #AnimeArt #ConceptArt #DigitalArt #AIGenerated #ThreadsArt",
}

# ---------------------------------------------------------------------------
# Gemini Client
# ---------------------------------------------------------------------------


def _get_model(model_name: str = "gemini-1.5-flash") -> genai.GenerativeModel:
    """Configure and return a Gemini GenerativeModel instance."""
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(model_name)


def _safe_generate(model: genai.GenerativeModel, prompt: str, retries: int = 3) -> str:
    """Call Gemini with exponential-backoff retry on transient errors."""
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning(
                "Gemini generation error (attempt %d/%d): %s -- retrying in %ds",
                attempt + 1, retries, exc, wait,
            )
            time.sleep(wait)
    raise RuntimeError("Gemini API failed after multiple retries.")


# ---------------------------------------------------------------------------
# Mode A -- Gaming Quotes & Philosophy
# ---------------------------------------------------------------------------


def generate_gaming_post() -> str:
    """Generate a punchy gaming philosophy quote post (<= 480 chars + hashtags)."""
    source = random.choice(GAMING_SOURCES)
    model = _get_model()
    prompt = textwrap.dedent(f"""
        You are a gaming philosopher with a deep, authentic voice.
        Create ONE original quote or philosophical insight inspired by the game: {source}.
        Rules:
        - Maximum 320 characters for the quote/insight itself.
        - Do NOT start with "Quote:" or any label.
        - Sound authentic, poetic, or punchy -- like something a real gamer would share.
        - Do NOT add hashtags (they will be added separately).
        - Do NOT use quotation marks around the full text.
        Output ONLY the quote/insight text.
    """).strip()

    text = _safe_generate(model, prompt)
    text = _trim_to_char_limit(text, 320)
    return f"{text}\n\n{HASHTAG_SETS['gaming']}"


# ---------------------------------------------------------------------------
# Mode B -- Anime Quotes & Deep Thoughts
# ---------------------------------------------------------------------------


def generate_anime_post() -> str:
    """Generate a deep anime quote or thought post (<= 480 chars + hashtags)."""
    source = random.choice(ANIME_SOURCES)
    model = _get_model()
    prompt = textwrap.dedent(f"""
        You are an anime philosopher and content creator.
        Create ONE original quote or deep thought inspired by the anime: {source}.
        Rules:
        - Maximum 320 characters for the text.
        - Sound authentic, emotional, or thought-provoking -- not generic.
        - Do NOT add hashtags (they will be added separately).
        - Do NOT start with any label or "Quote:".
        Output ONLY the quote/thought text.
    """).strip()

    text = _safe_generate(model, prompt)
    text = _trim_to_char_limit(text, 320)
    return f"{text}\n\n{HASHTAG_SETS['anime']}"


# ---------------------------------------------------------------------------
# Mode C -- Valorant Meta & Lore News
# ---------------------------------------------------------------------------


def generate_valorant_post() -> str:
    """Generate a Valorant meta tip, patch humor, or lore snippet."""
    agent = random.choice(VALORANT_AGENTS)
    post_type = random.choice(["meta_tip", "patch_humor", "lore_snippet", "vct_hype"])
    model = _get_model()

    type_instructions = {
        "meta_tip": f"Write a sharp, practical META tip for playing {agent} effectively. Max 280 chars.",
        "patch_humor": f"Write a funny, relatable take on a recent Valorant patch change affecting {agent} or the game. Max 280 chars.",
        "lore_snippet": f"Share an intriguing lore fact or story beat about {agent} from the Valorant universe. Max 280 chars.",
        "vct_hype": "Write hype commentary about the Valorant Champions Tour (VCT) pro scene. Max 280 chars.",
    }

    prompt = textwrap.dedent(f"""
        You are a Valorant content creator with expert game knowledge.
        {type_instructions[post_type]}
        Rules:
        - Be punchy, engaging, and authentic to the Valorant community.
        - Do NOT add hashtags.
        - Output ONLY the post text.
    """).strip()

    text = _safe_generate(model, prompt)
    text = _trim_to_char_limit(text, 320)
    return f"{text}\n\n{HASHTAG_SETS['valorant']}"


# ---------------------------------------------------------------------------
# Mode D -- AI Image Post (generates caption + image prompt)
# ---------------------------------------------------------------------------


def generate_image_post() -> dict:
    """
    Generate an AI-art post payload.

    Returns a dict with:
        - 'caption': str  -- the Threads caption
        - 'image_prompt': str -- descriptive prompt for image generation
    """
    theme = random.choice([
        "dark fantasy warrior from an Elden Ring-inspired world",
        "a samurai anime protagonist standing against a blood-red moon",
        "a futuristic Valorant agent in a neon-lit cyberpunk cityscape",
        "a lone anime traveler walking through ruins of a fallen civilization",
        "a god of war emerging from the depths of a glowing abyss",
        "a hunter from the world of Berserk facing a demonic creature",
    ])

    model = _get_model()

    caption_prompt = textwrap.dedent(f"""
        You are an AI art content creator for social media.
        Write a short, captivating caption for an AI-generated image of: {theme}.
        Rules:
        - Maximum 260 characters.
        - Evoke emotion, mystery, or awe.
        - Do NOT add hashtags.
        Output ONLY the caption text.
    """).strip()

    image_prompt_text = textwrap.dedent(f"""
        Write a detailed, vivid image generation prompt for: {theme}.
        Include: lighting style, mood, color palette, artistic style (e.g., digital painting, cinematic),
        and character details. Max 200 words. Output ONLY the image prompt.
    """).strip()

    caption = _safe_generate(model, caption_prompt)
    img_prompt = _safe_generate(model, image_prompt_text)

    caption = _trim_to_char_limit(caption, 260)
    full_caption = f"{caption}\n\n{HASHTAG_SETS['image']}"

    return {
        "caption": full_caption,
        "image_prompt": img_prompt,
        "theme": theme,
    }


# ---------------------------------------------------------------------------
# Comment Reply Generation
# ---------------------------------------------------------------------------


def generate_comment_reply(post_text: str, comment_text: str) -> Optional[str]:
    """
    Generate a witty, short, non-bot-like reply to a comment.

    Returns None if the comment appears to be spam or unworthy of a reply.
    """
    model = _get_model()

    spam_check_prompt = textwrap.dedent(f"""
        Determine if this comment is spam, a bot reply, or completely irrelevant gibberish.
        Comment: "{comment_text}"
        Answer with ONLY "SPAM" or "OK". Nothing else.
    """).strip()

    verdict = _safe_generate(model, spam_check_prompt).upper().strip()
    if "SPAM" in verdict:
        logger.info("Comment flagged as spam, skipping: %s", comment_text[:60])
        return None

    reply_prompt = textwrap.dedent(f"""
        You are a witty, authentic social media personality responding to a comment on your post.
        Your post was about: "{post_text[:200]}"
        The comment you received: "{comment_text}"

        Write a reply that is:
        - 1-2 sentences MAX (under 120 characters).
        - Witty, warm, or thought-provoking -- never robotic.
        - Contextually relevant to the comment.
        - Natural human tone -- no emoji overload, no forced enthusiasm.
        Output ONLY the reply text.
    """).strip()

    reply = _safe_generate(model, reply_prompt)
    return _trim_to_char_limit(reply, 120)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _trim_to_char_limit(text: str, limit: int) -> str:
    """Trim text to character limit at a word boundary."""
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rsplit(" ", 1)[0]
    return trimmed.rstrip(",.;:") + "..."


def get_post_modes() -> list:
    """Return all available post mode names."""
    return ["gaming", "anime", "valorant", "image"]
