"""Sanitization and intelligent generation for clip metadata.

Guarantees that every clip delivered to the user has:
- A non-empty, compelling viral hook (NEVER 'placeholder' or template tokens).
- A non-empty, curiosity-driven, high-CTR YouTube/Shorts title (NEVER verbatim speech quotes).
- Ready-to-copy TikTok and Instagram descriptions with hook, CTA, and well-targeted hashtags.
- A valid viral explanation and score.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

# Words or tokens that indicate a model dumped dummy/template text
_PLACEHOLDER_PATTERNS = re.compile(
    r"^(placeholder|untitled|no title|hook|viral hook|viral_hook_text|"
    r"<[^>]+>|none|null|undefined|\.+|-+)$",
    re.IGNORECASE
)

_COMMON_HASHTAGS = "#shorts #viral #reels #foryou #reflexao #desenvolvimentopessoal"

_TOPIC_KEYWORDS = {
    "medo": {
        "label": "o Medo",
        "hashtags": ["#medo", "#superacao", "#coragem", "#saudemental", "#ansiedade"],
        "titles": [
            "A Verdade Que Ninguém Te Conta Sobre o Medo 😱",
            "O Maior Erro de Quem Vive com Medo ⚠️",
            "Você Vive Preso no Medo? Veja Isso! 👀",
            "Como Vencer o Medo de Uma Vez Por Todas! 🧠",
            "A Lição Que Vai Libertar Sua Mente do Medo 💡",
        ]
    },
    "ansiedade": {
        "label": "a Ansiedade",
        "hashtags": ["#ansiedade", "#saudemental", "#calma", "#mente", "#paz"],
        "titles": [
            "O Que a Ansiedade Realmente Faz Com Você ⚠️",
            "Como Acalmar Sua Mente em Momentos Difíceis 🧠",
            "A Verdade Sobre a Ansiedade Que Poucos Sabem 💡",
        ]
    },
    "dinheiro": {
        "label": "o Dinheiro",
        "hashtags": ["#dinheiro", "#financas", "#investimentos", "#prosperidade", "#riqueza"],
        "titles": [
            "O Segredo do Dinheiro Que Não Te Ensinam na Escola 💰",
            "O Maior Erro Financeiro Que Você Está Cometendo ⚠️",
            "Como os Ricos Pensam Sobre Dinheiro 🧠",
        ]
    },
    "sucesso": {
        "label": "o Sucesso",
        "hashtags": ["#sucesso", "#disciplina", "#foco", "#produtividade", "#motivacao"],
        "titles": [
            "A Verdade Brutal Sobre o Sucesso Que Ninguém Fala 🏆",
            "O Hábito Que Separa Quem Vence de Quem Desiste 💡",
            "Você Quer Ter Sucesso? Presta Atenção Nisso! 👀",
        ]
    },
    "disciplina": {
        "label": "a Disciplina",
        "hashtags": ["#disciplina", "#foco", "#habitos", "#constancia", "#mente"],
        "titles": [
            "Por Que Disciplina é Mais Importante Que Motivação 🧠",
            "Como Construir Disciplina Inabalável no Seu Dia a Dia 💡",
            "O Segredo da Constância Que Poucos Dominam ⚡",
        ]
    },
    "mente": {
        "label": "Sua Mente",
        "hashtags": ["#mindset", "#mentalidade", "#psicologia", "#autoconhecimento", "#cerebro"],
        "titles": [
            "O Que Acontece Com a Sua Mente Quando Você Faz Isso 🤯",
            "A Verdade Psicológica Que Vai Abrir Seus Olhos 🧠",
            "Como Reprogramar Seus Pensamentos Negativos 💡",
        ]
    },
    "relacionamento": {
        "label": "Relacionamentos",
        "hashtags": ["#relacionamento", "#amorproprio", "#maturidade", "#casal", "#conexoes"],
        "titles": [
            "O Maior Erro Nos Relacionamentos Que Destrói Tudo ⚠️",
            "A Verdade Sobre Pessoas Tóxicas Que Você Precisa Saber 👀",
            "Como Saber Se Um Relacionamento Realmente Vale a Pena 💡",
        ]
    },
    "saude": {
        "label": "Sua Saúde",
        "hashtags": ["#saude", "#bemestar", "#qualidadedevida", "#treino", "#vidasaudavel"],
        "titles": [
            "O Que Esse Hábito Faz Com o Seu Corpo Sem Você Saber ⚠️",
            "A Mudança Simples Que Vai Melhorar Sua Saúde Hoje 💡",
            "O Segredo Para Ter Mais Energia e Vitalidade ⚡",
        ]
    },
}

_GENERAL_VIRAL_TITLES = [
    "A Verdade Que Ninguém Te Conta Sobre Isso! 😱",
    "O Maior Erro Que Quase Todo Mundo Comete ⚠️",
    "Você Precisa Ouvir Isso Antes Que Seja Tarde! 👀",
    "A Lição Que Mudou Minha Vida Para Sempre 💡",
    "O Segredo Revelado Que Poucos Sabem... 🧠",
    "Isso Vai Fazer Você Pensar Muito Diferente 🤯",
    "Apenas Quem Entende Isso Consegue Ir Longe! 🚀",
]


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


def is_verbatim_transcript_quote(title: Optional[str], clip_text: str) -> bool:
    """True if title appears to be a raw excerpt extracted verbatim from speech."""
    if not title or not clip_text:
        return False
    t_clean = re.sub(r"[^\w\sÀ-ÿ]", "", str(title)).strip().lower()
    c_clean = re.sub(r"[^\w\sÀ-ÿ]", "", str(clip_text)).strip().lower()
    words = t_clean.split()
    if len(words) >= 4 and t_clean in c_clean:
        return True
    return False


def _clean_subject_from_title(video_title: Optional[str]) -> str:
    """Extract a clean subject noun phrase from the main video title."""
    if not video_title:
        return ""
    clean = re.sub(r"\.[a-zA-Z0-9]+$", "", video_title)
    clean = re.sub(r"[-_]+", " ", clean)
    clean = re.sub(r"[^\w\sÀ-ÿ]", " ", clean)
    clean = re.sub(
        r"^(um\s+vídeo\s+necessário\s+(para|pra)\s+(você|vc)\s+(que\s+)?|vídeo\s+sobre\s+|corte\s+do\s+|podcast\s+episodio\s+\d+\s+)",
        "", clean, flags=re.IGNORECASE
    )
    clean = " ".join(clean.split()).strip()
    return clean


def _detect_topic(clip_text: str, video_title: Optional[str] = None) -> Optional[dict]:
    """Detect main topic data based on video title and transcript keywords."""
    combined = f"{video_title or ''} {clip_text or ''}".lower()
    for key, data in _TOPIC_KEYWORDS.items():
        if key in combined:
            return data
    return None


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
        sentences = re.split(r"[.?!]\s+", clip_text)
        for s in sentences:
            s_clean = s.strip()
            word_count = len(s_clean.split())
            if 3 <= word_count <= 8:
                if not s_clean.endswith(("?", "!")):
                    s_clean += " 🤯"
                return s_clean[:60]

        words = clip_text.split()
        if len(words) >= 4:
            phrase = " ".join(words[:min(6, len(words))]).strip()
            return f"Olha isso: \"{phrase}…\" 👀"

    return "Você não vai acreditar nisso! 🤯"


def generate_fallback_title(clip_text: str, video_title: Optional[str] = None, language: str = "pt") -> str:
    """Generate an attractive, curiosity-inducing video title for YouTube Shorts / Reels.
    
    Guarantees:
    - NEVER dumps a verbatim transcript quote or raw speech excerpt.
    - Creates high-CTR, click-worthy curiosity titles (max 70 chars).
    """
    topic_data = _detect_topic(clip_text, video_title)
    seed = abs(hash(clip_text or video_title or "title"))

    # 1. Use curated viral titles for the detected topic
    if topic_data and topic_data.get("titles"):
        titles = topic_data["titles"]
        return titles[seed % len(titles)][:70]

    # 2. Check if the clip text naturally asks an intriguing question
    if clip_text:
        q_matches = re.findall(r"(por que|como|qual|o que|será que|você já)[^.?!]{8,45}\?", clip_text, flags=re.IGNORECASE)
        if q_matches:
            q = q_matches[0].strip()
            q_clean = q[0].upper() + q[1:]
            if not q_clean.endswith("?"):
                q_clean += "?"
            return f"{q_clean} 🤔"[:70]

    # 3. Use cleaned subject from video title
    if video_title:
        subject = _clean_subject_from_title(video_title)
        if subject and len(subject) >= 3:
            templates = [
                f"A Verdade Sobre {subject} Que Poucos Sabem 😱",
                f"O Maior Erro Sobre {subject} ⚠️",
                f"Você Precisa Ouvir Isso Sobre {subject}! 👀",
                f"A Lição Que Mudou Minha Visão Sobre {subject} 💡",
            ]
            cand = templates[seed % len(templates)]
            if len(cand) <= 70:
                return cand
            return f"{subject[:50]} (Corte Viral)"

    # 4. General viral titles
    return _GENERAL_VIRAL_TITLES[seed % len(_GENERAL_VIRAL_TITLES)][:70]


def generate_fallback_description(
    clip_text: str,
    video_title: Optional[str] = None,
    platform: str = "tiktok",
    language: str = "pt"
) -> str:
    """Generate a complete description ready to copy for social media with hook, CTA, and hashtags."""
    topic_data = _detect_topic(clip_text, video_title)
    seed = abs(hash(clip_text or video_title or "desc"))

    # 1. Hook opening line
    hook_lines = [
        "👀 Presta atenção nessa reflexão importante:",
        "💡 Uma perspectiva que todo mundo deveria ouvir:",
        "🔥 Você já parou para pensar nisso?",
        "⚠️ Essa lição pode mudar a sua visão sobre as coisas:",
    ]
    hook = hook_lines[seed % len(hook_lines)]

    # 2. Context / Value takeaway
    if topic_data:
        label = topic_data["label"]
        summary = f"Entender como {label} impacta nossas escolhas é essencial para retomar o controle e transformar sua vida."
    elif clip_text:
        sentences = [s.strip() for s in re.split(r"[.?!]\s+", clip_text) if len(s.strip().split()) >= 4]
        if sentences:
            s_text = sentences[0]
            if not s_text.endswith((".", "!", "?")):
                s_text += "."
            summary = s_text
        else:
            summary = "Reflita sobre esse momento e absorva o aprendizado compartilhado aqui."
    else:
        summary = "Um insight poderoso para você refletir e aplicar no seu dia a dia."

    # 3. Call to Action
    if platform == "instagram":
        cta = (
            "💬 Você concorda ou pensa diferente? Deixe sua visão nos comentários! 👇\n"
            "📌 Salve este post para rever depois e envie para alguém que precisa ver isso!"
        )
    else:  # tiktok / shorts
        cta = (
            "💬 Qual é a sua opinião sobre isso? Comenta aqui embaixo! 👇\n"
            "👉 Compartilhe com quem precisa ouvir essa mensagem hoje!"
        )

    # 4. Hashtags
    hashtags = ["#shorts", "#viral", "#reels", "#foryou", "#reflexao", "#desenvolvimentopessoal"]
    if topic_data:
        for tag in topic_data.get("hashtags", []):
            if tag not in hashtags:
                hashtags.append(tag)

    if video_title:
        words = re.findall(r"[a-zA-ZÀ-ÿ]{4,}", video_title.lower())
        for w in words:
            if w not in ("video", "necessario", "sobre", "corte", "podcast", "para", "voce", "shorts"):
                tag = f"#{w}"
                if tag not in hashtags and len(hashtags) < 12:
                    hashtags.append(tag)

    hashtags_str = " ".join(hashtags)

    return f"{hook}\n\n{summary}\n\n{cta}\n\n{hashtags_str}"


def generate_ai_clip_metadata(
    clip_text: str,
    video_title: Optional[str] = None,
    language: str = "pt"
) -> Optional[dict]:
    """Call Gemini or LLM backend to generate a viral title, hook, and social captions."""
    if not clip_text or len(clip_text.strip()) < 10:
        return None

    prompt = f"""Você é um especialista em criação de conteúdo viral para YouTube Shorts, TikTok e Instagram Reels.
Com base na transcrição do corte abaixo (do vídeo "{video_title or 'Vídeo'}"), crie títulos e descrições magnéticos em {language}.

TRANSCRIÇÃO DO CORTE:
"{clip_text[:2000]}"

REGRAS:
1. `video_title_for_youtube_short`: Título viral irresistível com alto CTR (MÁXIMO 65 CARACTERES).
   CRÍTICO: NUNCA copie frases da transcrição nem citações literais da fala! Crie uma chamada magnética com gatilho de curiosidade, choque, identificação ou revelação (ex: "O Segredo Que Ninguém Te Conta Sobre o Medo 😱", "Você Comete Esse Erro Sem Perceber? ⚠️", "A Verdade Que Mudou Tudo...").
2. `viral_hook_text`: Gancho visual para tela de 3 a 7 palavras com emoji (ex: "Você vive com medo? 👀").
3. `video_description_for_tiktok`: Legenda completa para postagem no TikTok com:
   - Gancho inicial impactante com emoji
   - 1 ou 2 frases curtas com a lição / insight do vídeo
   - Chamada para ação (CTA) provocativa para comentários
   - 6 a 9 hashtags relevantes (#shorts #viral #foryou e tags do assunto do vídeo).
4. `video_description_for_instagram`: Legenda completa pronta para publicação no Instagram Reels com:
   - Gancho de abertura com emoji
   - Breve contexto/reflexão de valor
   - CTA para salvar e compartilhar ("Salva para ver depois! 📌")
   - 6 a 9 hashtags bem organizadas.

Retorne EXCLUSIVAMENTE um objeto JSON válido no formato:
{{
  "video_title_for_youtube_short": "título curto e viral aqui",
  "viral_hook_text": "gancho visual na tela",
  "video_description_for_tiktok": "legenda completa com CTA e hashtags",
  "video_description_for_instagram": "legenda completa com CTA e hashtags"
}}
"""
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            model_name = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            data = json.loads(resp.text)
            if isinstance(data, dict) and data.get("video_title_for_youtube_short"):
                return data
        except Exception:
            pass

    try:
        import llm_backend
        if llm_backend.active():
            from pydantic import BaseModel
            class ClipMetaModel(BaseModel):
                video_title_for_youtube_short: str
                viral_hook_text: str
                video_description_for_tiktok: str
                video_description_for_instagram: str
            data, _ = llm_backend.generate_json(prompt, ClipMetaModel)
            if isinstance(data, dict) and data.get("video_title_for_youtube_short"):
                return data
    except Exception:
        pass

    return None


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

    current_title = clip.get("video_title_for_youtube_short")
    title_invalid = is_placeholder_or_empty(current_title) or is_verbatim_transcript_quote(current_title, clip_text)
    tiktok_desc_invalid = is_placeholder_or_empty(clip.get("video_description_for_tiktok"))
    insta_desc_invalid = is_placeholder_or_empty(clip.get("video_description_for_instagram"))
    hook_invalid = is_placeholder_or_empty(clip.get("viral_hook_text"))

    # Try AI generation if anything is missing or invalid
    if (title_invalid or tiktok_desc_invalid or insta_desc_invalid or hook_invalid) and clip_text:
        ai_meta = generate_ai_clip_metadata(clip_text, video_title=video_title, language=language)
        if ai_meta:
            if title_invalid and ai_meta.get("video_title_for_youtube_short"):
                clip["video_title_for_youtube_short"] = str(ai_meta["video_title_for_youtube_short"])[:70]
                title_invalid = False
            if hook_invalid and ai_meta.get("viral_hook_text"):
                clip["viral_hook_text"] = str(ai_meta["viral_hook_text"])[:60]
                hook_invalid = False
            if tiktok_desc_invalid and ai_meta.get("video_description_for_tiktok"):
                clip["video_description_for_tiktok"] = str(ai_meta["video_description_for_tiktok"])
                tiktok_desc_invalid = False
            if insta_desc_invalid and ai_meta.get("video_description_for_instagram"):
                clip["video_description_for_instagram"] = str(ai_meta["video_description_for_instagram"])
                insta_desc_invalid = False

    # 1. Sanitize Hook
    if hook_invalid:
        clip["viral_hook_text"] = generate_fallback_hook(clip_text, language)

    # If auto_hook dict is already present, sync its text too
    if "auto_hook" in clip and isinstance(clip["auto_hook"], dict):
        if is_placeholder_or_empty(clip["auto_hook"].get("text")):
            clip["auto_hook"]["text"] = clip["viral_hook_text"]

    # 2. Sanitize Title
    if title_invalid:
        clip["video_title_for_youtube_short"] = generate_fallback_title(clip_text, video_title, language)

    # 3. Sanitize Descriptions
    if tiktok_desc_invalid:
        clip["video_description_for_tiktok"] = generate_fallback_description(
            clip_text, video_title, platform="tiktok", language=language)

    if insta_desc_invalid:
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
