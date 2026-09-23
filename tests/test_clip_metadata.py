import pytest
from clip_metadata import (
    is_placeholder_or_empty,
    generate_fallback_hook,
    generate_fallback_title,
    generate_fallback_description,
    clean_or_generate_clip_metadata,
)


def test_is_placeholder_or_empty():
    assert is_placeholder_or_empty(None) is True
    assert is_placeholder_or_empty("") is True
    assert is_placeholder_or_empty("   ") is True
    assert is_placeholder_or_empty("placeholder") is True
    assert is_placeholder_or_empty("PLACEHOLDER") is True
    assert is_placeholder_or_empty("hook") is True
    assert is_placeholder_or_empty("<short overlay max 10 words>") is True
    assert is_placeholder_or_empty("<title max 100 chars>") is True
    assert is_placeholder_or_empty("untitled") is True
    assert is_placeholder_or_empty("null") is True
    assert is_placeholder_or_empty("this is a real hook") is False


def test_clean_or_generate_clip_metadata_replaces_placeholder():
    dummy_clip = {
        "start": 10.0,
        "end": 35.0,
        "source_window_id": "window_001",
        "predicted_score": 0,
        "explanation": "",
        "video_description_for_tiktok": "",
        "video_description_for_instagram": "",
        "video_title_for_youtube_short": "",
        "viral_hook_text": "placeholder",
        "auto_hook": {"text": "placeholder", "style": "red"}
    }
    transcript = {
        "language": "pt",
        "segments": [
            {
                "start": 10.0,
                "end": 20.0,
                "text": "Você sabia que isso muda tudo?",
                "words": [
                    {"word": "Você", "start": 10.0, "end": 11.0},
                    {"word": "sabia", "start": 11.0, "end": 12.0},
                    {"word": "que", "start": 12.0, "end": 12.5},
                    {"word": "isso", "start": 12.5, "end": 13.0},
                    {"word": "muda", "start": 13.0, "end": 14.0},
                    {"word": "tudo?", "start": 14.0, "end": 15.0},
                ]
            }
        ]
    }

    cleaned = clean_or_generate_clip_metadata(
        dummy_clip, transcript=transcript, video_title="Video Sobre Curiosidades Incríveis")

    # Assert NO placeholders exist
    assert "placeholder" not in cleaned["viral_hook_text"].lower()
    assert "placeholder" not in cleaned["auto_hook"]["text"].lower()
    assert len(cleaned["viral_hook_text"]) > 3
    assert len(cleaned["video_title_for_youtube_short"]) > 3
    assert len(cleaned["video_description_for_tiktok"]) > 10
    assert len(cleaned["video_description_for_instagram"]) > 10
    assert "#shorts" in cleaned["video_description_for_tiktok"]
    assert "#viral" in cleaned["video_description_for_instagram"]
    assert cleaned["predicted_score"] > 0
    assert len(cleaned["explanation"]) > 5


def test_clean_or_generate_clip_metadata_preserves_valid_metadata():
    valid_clip = {
        "start": 5.0,
        "end": 25.0,
        "source_window_id": "window_002",
        "predicted_score": 88,
        "explanation": "Ótimo momento de tensão.",
        "video_description_for_tiktok": "Descubra o segredo! #shorts",
        "video_description_for_instagram": "Veja até o final! #viral",
        "video_title_for_youtube_short": "O Grande Mistério Revelado",
        "viral_hook_text": "Você viu isso?! 😱",
    }

    cleaned = clean_or_generate_clip_metadata(valid_clip)
    assert cleaned["viral_hook_text"] == "Você viu isso?! 😱"
    assert cleaned["video_title_for_youtube_short"] == "O Grande Mistério Revelado"
    assert cleaned["video_description_for_tiktok"] == "Descubra o segredo! #shorts"
    assert cleaned["predicted_score"] == 88
    assert cleaned["explanation"] == "Ótimo momento de tensão."


def test_fallback_title_never_quotes_verbatim_speech():
    clip_text = "E aí quando você acorda de manhã e sente muito medo do futuro."
    title = generate_fallback_title(clip_text, video_title="UM_VÍDEO_NECESSÁRIO_pra__VOCÊ,_que_VIVE_COM_MEDO")
    assert "E aí quando você acorda" not in title
    assert len(title) <= 70
    assert "medo" in title.lower()


def test_verbatim_speech_title_is_replaced():
    clip_text = "então eu decidi começar a investir meu dinheiro ontem."
    dummy_clip = {
        "start": 0.0,
        "end": 20.0,
        "video_title_for_youtube_short": "então eu decidi começar a investir",
        "video_description_for_tiktok": "",
        "video_description_for_instagram": "",
    }
    transcript = {"segments": [{"start": 0.0, "end": 20.0, "text": clip_text}]}
    cleaned = clean_or_generate_clip_metadata(dummy_clip, transcript=transcript, video_title="Vídeo Sobre Dinheiro")
    assert cleaned["video_title_for_youtube_short"] != "então eu decidi começar a investir"
    assert len(cleaned["video_title_for_youtube_short"]) > 5


def test_social_description_has_hook_cta_and_hashtags():
    clip_text = "Se você quer superar o medo, precisa dar o primeiro passo hoje."
    desc = generate_fallback_description(clip_text, video_title="Como Vencer o Medo", platform="tiktok")
    assert "#shorts" in desc
    assert "#viral" in desc
    assert "#medo" in desc
    assert "👇" in desc
    assert "\n\n" in desc

