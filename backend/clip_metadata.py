"""Sanitization and intelligent fallback generation for clip metadata.

Guarantees that every clip delivered to the user has:
- A non-empty, compelling viral hook (NEVER 'placeholder' or template tokens).
- A non-empty, curiosity-driven YouTube/Shorts title.
- Ready-to-copy TikTok and Instagram descriptions with CTAs and hashtags.
- A valid viral explanation and score.
"""
from __future__ import annotations

import re
from typing import Optional

# Words or tokens that indicate a model dumped dummy/template text
_PLACEHOLDER_PATTERNS = re.compile(
    r"^(placeholder|untitled|no title|hook|viral hook|viral_hook_text|"
    r"<[^>]+>|none|null|undefined|\.+|-+)$",
    re.IGNORECASE
)

_COMMON_HASHTAGS = "#shorts #viral #cortes #podcast #curiosidades"


def is_placeholder_or_empty(text: Optional[str]) -> bool:
    """True if text is None, blank, or matches known dummy placeholder strings."""
    if not text:
        return True
    cleaned = str(text).strip()
    if not cleaned or len(cleaned) < 2:
        return True
    if _PLACEHOLDER_PATTERNS.match(cleaned):
        return True
    if "placeholder" in cleaned.lower():
        return True
    if cleaned.startswith("<") and cleaned.endswith(">"):
        return True
    return False


def get_clip_transcript_text(transcript: Optional[dict], start: float, end: float) -> str:
    """Extract spoken text within the [start, end] window."""
    if not transcript:
        return ""
    words_collected = []
    segments = transcript.get("segments") or []
    for seg in segments:
        seg_start = float(seg.get("start") or 0.0)
        seg_end = float(seg.get("end") or 0.0)
        if seg_end < start or seg_start > end:
            continue
        # If segment has word timestamps, pick exact words
        seg_words = seg.get("words") or []
        if seg_words:
            for w in seg_words:
                ws = float(w.get("start") or 0.0)
                we = float(w.get("end") or 0.0)
                if we >= start and ws <= end:
                    words_collected.append(str(w.get("word") or "").strip())
        else:
            words_collected.append(str(seg.get("text") or "").strip())

    return " ".join(w for w in words_collected if w).strip()


def generate_fallback_hook(clip_text: str, language: str = "pt") -> str:
    """Generate a punchy, scroll-stopping hook overlay from the clip's spoken text."""
    if clip_text:
        # Check for direct questions or exclamations in the first 150 chars
        sentences = re.split(r"[.?!]\s+", clip_text)
        for s in sentences:
            s_clean = s.strip()
            # If there's a strong question or short sentence (3 to 8 words)
            word_count = len(s_clean.split())
            if 3 <= word_count <= 8:
                if not s_clean.endswith(("?", "!")):
                    s_clean += " 🤯"
                return s_clean[:60]

        # Extract first 4-7 words as a punchy phrase
        words = clip_text.split()
        if len(words) >= 4:
            phrase = " ".join(words[:min(6, len(words))]).strip()
            return f"Olha isso: \"{phrase}…\" 👀"

    # Default viral hooks in Portuguese
    return "Você não vai acreditar nisso! 🤯"


def generate_fallback_title(clip_text: str, video_title: Optional[str] = None, language: str = "pt") -> str:
    """Generate a curiosity-inducing video title for YouTube Shorts / Reels."""
    if clip_text:
        sentences = re.split(r"[.?!]\s+", clip_text)
        for s in sentences:
            s_clean = s.strip()
            if 4 <= len(s_clean.split()) <= 12 and len(s_clean) <= 80:
                # Capitalize first letter cleanly
                return s_clean[0].upper() + s_clean[1:]

    if video_title:
        clean_title = re.sub(r"[-_]+", " ", video_title).strip()
        if clean_title:
            return f"{clean_title[:70]} (Corte Imperdível)"

    return "Revelação Surpreendente Que Poucos Sabem! 😱"


def generate_fallback_description(clip_text: str, video_title: Optional[str] = None,
                                  platform: str = "tiktok", language: str = "pt") -> str:
    """Generate a complete description ready to copy with CTA and viral hashtags."""
    cta = "Assista até o final! O que você acha disso? Deixe sua opinião nos comentários! 👇"
    summary = ""
    if clip_text:
        sentences = re.split(r"[.?!]\s+", clip_text)
        if sentences and len(sentences[0].split()) > 3:
            summary_text = sentences[0].strip()
            summary = f'"{summary_text}..."'
        else:
            words = clip_text.split()
            if len(words) > 10:
                summary = '"' + " ".join(words[:18]) + '..."'

    parts = []
    if summary:
        parts.append(summary)
    parts.append(cta)
    parts.append(_COMMON_HASHTAGS)
    return "\n\n".join(parts)


def clean_or_generate_clip_metadata(
    clip: dict,
    transcript: Optional[dict] = None,
    start: Optional[float] = None,
    end: Optional[float] = None,
    video_title: Optional[str] = None,
    language: str = "pt"
) -> dict:
    """Ensure every clip has valid, non-placeholder hook, title, descriptions, and scores.

    Mutates and returns the clip dict.
    """
    clip_start = float(clip.get("start") if clip.get("start") is not None else (start or 0.0))
    clip_end = float(clip.get("end") if clip.get("end") is not None else (end or 0.0))
    clip_text = get_clip_transcript_text(transcript, clip_start, clip_end)

    # 1. Sanitize Hook
    current_hook = clip.get("viral_hook_text")
    if is_placeholder_or_empty(current_hook):
        clip["viral_hook_text"] = generate_fallback_hook(clip_text, language)

    # If auto_hook dict is already present, sync its text too
    if "auto_hook" in clip and isinstance(clip["auto_hook"], dict):
        if is_placeholder_or_empty(clip["auto_hook"].get("text")):
            clip["auto_hook"]["text"] = clip["viral_hook_text"]

    # 2. Sanitize Title
    current_title = clip.get("video_title_for_youtube_short")
    if is_placeholder_or_empty(current_title):
        clip["video_title_for_youtube_short"] = generate_fallback_title(clip_text, video_title, language)

    # 3. Sanitize Descriptions
    if is_placeholder_or_empty(clip.get("video_description_for_tiktok")):
        clip["video_description_for_tiktok"] = generate_fallback_description(
            clip_text, video_title, platform="tiktok", language=language)

    if is_placeholder_or_empty(clip.get("video_description_for_instagram")):
        clip["video_description_for_instagram"] = generate_fallback_description(
            clip_text, video_title, platform="instagram", language=language)

    # 4. Sanitize Explanation & Score
    if is_placeholder_or_empty(clip.get("explanation")):
        clip["explanation"] = "Trecho com alto potencial de engajamento e retenção."

    score = clip.get("predicted_score")
    if not isinstance(score, (int, float)) or score <= 0:
        clip["predicted_score"] = 75
    else:
        clip["predicted_score"] = int(score)

    return clip
