"""
app/brain.py
============
Gemini AI Brain -- all content generation for the Threads bot.
Model: gemini-2.5-flash
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
# Config
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-3.6-flash"

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

IMAGE_THEMES = [
    "dark fantasy warrior from an Elden Ring-inspired world",
    "a samurai anime protagonist standing against a blood-red moon",
    "a futuristic Valorant agent in a neon-lit cyberpunk cityscape",
    "a lone anime traveler walking through ruins of a fallen civilization",
    "a god of war emerging from the depths of a glowing abyss",
    "a hunter from the world of Berserk facing a demonic creature",
]

HASHTAG_SETS = {
    "gaming": "#Gaming #GamingQuotes #EldenRing #GodOfWar #Witcher #GamePhilosophy #NightOwlGamer",
    "anime": "#Anime #AnimeQuotes #AttackOnTitan #JJK #VinlandSaga #AnimeWisdom #DemonSlayer",
    "valorant": "#Valorant #VCT #VALORANT #EsportsNews #FPS #ValorantLore #PROScene",
    "image": "#AIArt #GamingArt #AnimeArt #ConceptArt #DigitalArt #AIGenerated #ThreadsArt",
}

# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------


def _get_model() -> genai.GenerativeModel:
    """Configure and return a Gemini GenerativeModel instance."""
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(MODEL_NAME)


def _safe_generate(model: genai.GenerativeModel, prompt: str, retries: int = 3) -> str:
    """Call Gemini with exponential-backoff retry on transient errors."""
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning(
                "Gemini error (attempt %d/%d): %s -- retrying in %ds",
                attempt + 1, retries, exc, wait,
            )
            time.sleep(wait)
    raise RuntimeError("Gemini API failed after %d retries." % retries)


def _trim(text: str, limit: int) -> str:
    """Trim text to character limit at a word boundary."""
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rsplit(" ", 1)[0]
    return trimmed.rstrip(",.;:") + "..."


# ---------------------------------------------------------------------------
# Post mode registry
# ---------------------------------------------------------------------------


def get_post_modes() -> list:
    """Return all available post mode identifiers."""
    return ["GAMING", "ANIME", "VALORANT", "IMAGE"]


# ---------------------------------------------------------------------------
# Mode A -- Gaming Quotes
# ---------------------------------------------------------------------------


def generate_gaming_post() -> str:
    source = random.choice(GAMING_SOURCES)
    model = _get_model()
    prompt = textwrap.dedent(f"""
        You are a gaming philosopher with a deep, authentic voice.
        Create ONE original quote or philosophical insight inspired by the game: {source}.
        Rules:
        - Maximum 320 characters.
        - Do NOT start with "Quote:" or any label.
        - Sound authentic, poetic, or punchy.
        - Do NOT add hashtags.
        - Do NOT use quotation marks around the full text.
        Output ONLY the quote/insight text.
    """).strip()
    text = _safe_generate(model, prompt)
    return f"{_trim(text, 320)}\n\n{HASHTAG_SETS['gaming']}"


# ---------------------------------------------------------------------------
# Mode B -- Anime Quotes
# ---------------------------------------------------------------------------


def generate_anime_post() -> str:
    source = random.choice(ANIME_SOURCES)
    model = _get_model()
    prompt = textwrap.dedent(f"""
        You are an anime philosopher and content creator.
        Create ONE original quote or deep thought inspired by: {source}.
        Rules:
        - Maximum 320 characters.
        - Sound authentic, emotional, or thought-provoking.
        - Do NOT add hashtags.
        - Do NOT start with any label.
        Output ONLY the quote/thought text.
    """).strip()
    text = _safe_generate(model, prompt)
    return f"{_trim(text, 320)}\n\n{HASHTAG_SETS['anime']}"


# ---------------------------------------------------------------------------
# Mode C -- Valorant Meta & Lore
# ---------------------------------------------------------------------------


def generate_valorant_post() -> str:
    agent = random.choice(VALORANT_AGENTS)
    post_type = random.choice(["meta_tip", "patch_humor", "lore_snippet", "vct_hype"])
    model = _get_model()

    instructions = {
        "meta_tip": f"Write a sharp, practical META tip for playing {agent} effectively. Max 280 chars.",
        "patch_humor": f"Write a funny, relatable take on a Valorant patch change affecting {agent}. Max 280 chars.",
        "lore_snippet": f"Share an intriguing lore fact about {agent} from the Valorant universe. Max 280 chars.",
        "vct_hype": "Write hype commentary about the Valorant Champions Tour (VCT) pro scene. Max 280 chars.",
    }

    prompt = textwrap.dedent(f"""
        You are a Valorant content creator with expert game knowledge.
        {instructions[post_type]}
        Rules:
        - Punchy, engaging, authentic to the Valorant community.
        - Do NOT add hashtags.
        Output ONLY the post text.
    """).strip()
    text = _safe_generate(model, prompt)
    return f"{_trim(text, 320)}\n\n{HASHTAG_SETS['valorant']}"


# ---------------------------------------------------------------------------
# Mode D -- AI Image Post
# ---------------------------------------------------------------------------


def generate_image_post() -> dict:
    """
    Returns:
        dict with keys: 'caption', 'image_prompt', 'image_url', 'theme'
        image_url is built from Pollinations.ai (free, public, no auth required).
    """
    import urllib.parse

    theme = random.choice(IMAGE_THEMES)
    model = _get_model()

    caption_prompt = textwrap.dedent(f"""
        Write a short, captivating caption for an AI-generated image of: {theme}.
        Maximum 260 characters. Evoke emotion, mystery, or awe.
        Do NOT add hashtags. Output ONLY the caption text.
    """).strip()

    image_prompt_text = textwrap.dedent(f"""
        Write a detailed, vivid image generation prompt for: {theme}.
        Include lighting style, mood, color palette, artistic style (e.g., digital painting, cinematic),
        and character details. Max 150 words. Output ONLY the image prompt.
    """).strip()

    caption = _trim(_safe_generate(model, caption_prompt), 260)
    img_prompt = _safe_generate(model, image_prompt_text)

    import random as _random
    seed = _random.randint(1, 999999)
    encoded = urllib.parse.quote(img_prompt[:500])
    image_url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1024&height=1024&seed={seed}&nologo=true"
    )

    return {
        "caption": f"{caption}\n\n{HASHTAG_SETS['image']}",
        "image_prompt": img_prompt,
        "image_url": image_url,
        "theme": theme,
    }


# ---------------------------------------------------------------------------
# Comment reply (called by engagement engine in main.py)
# ---------------------------------------------------------------------------


def generate_comment_reply(post_text: str, comment_text: str) -> Optional[str]:
    """
    Generate a witty, short reply to a comment.
    Returns None if the comment is spam/irrelevant.
    """
    model = _get_model()

    spam_prompt = textwrap.dedent(f"""
        Is this comment spam, a bot reply, or completely irrelevant gibberish?
        Comment: "{comment_text}"
        Answer with ONLY "SPAM" or "OK". Nothing else.
    """).strip()

    verdict = _safe_generate(model, spam_prompt).upper().strip()
    if "SPAM" in verdict:
        logger.info("Comment flagged as spam: %s", comment_text[:60])
        return None

    reply_prompt = textwrap.dedent(f"""
        You are a witty, authentic social media personality.
        Your post: "{post_text[:200]}"
        Comment received: "{comment_text}"
        Write a reply that is:
        - 1-2 sentences MAX (under 120 characters total).
        - Witty, warm, or thought-provoking -- never robotic.
        - Contextually relevant.
        - Natural human tone.
        Output ONLY the reply text.
    """).strip()

    reply = _safe_generate(model, reply_prompt)
    return _trim(reply, 120)


def analyze_and_reply(post_context: str, comment_author: str, comment_text: str) -> Optional[str]:
    """Alias used by main.py engagement engine."""
    return generate_comment_reply(post_context, comment_text)