"""Job log view for human-friendly progress in pt-BR.

Curated, whitelist-based view: friendly progress lines only — no file paths,
model names, encoder details or pipeline internals. Non-technical users see
human status messages in Brazilian Portuguese.
"""
import re

# Strips any slashy path token (output/…/clip.mp4, /app/uploads/x.mp4, …).
_PATH_RE = re.compile(r'(?:/?[\w.\-]+/)+[\w.\-]+')


def _strip_paths(line):
    return _PATH_RE.sub('', line).rstrip(' :')


# Ordered rules; first match wins. Replacement is a template using the
# match's groups, or a string literal, or None to keep the (path-stripped) line verbatim.
_RULES = [
    # Worker/job lifecycle + errors in pt-BR
    (re.compile(r'^Job started', re.I), '🚀 Iniciando processamento do vídeo...'),
    (re.compile(r'^(?:Process finished|🎉 Processamento finalizado)', re.I), '🎉 Processamento concluído com sucesso!'),
    (re.compile(r'^(?:Process failed|Execution error)', re.I), '❌ Ocorreu uma falha no processamento.'),
    (re.compile(r'^❌\s*(.*)'), '❌ {0}'),

    # Download progress
    (re.compile(r'📥 Baixando vídeo:\s*(\d+)%'), '📥 Baixando vídeo: {0}%'),
    (re.compile(r'\[download\]\s+(\d+(?:\.\d+)?)%'), '📥 Baixando vídeo: {0}%'),
    (re.compile(r'(?:Downloading video from YouTube|Iniciando download do vídeo)', re.I), '📥 Iniciando download do vídeo...'),
    (re.compile(r'(?:Download succeeded|Video downloaded in|✅ Download concluído)', re.I), '✅ Download concluído com sucesso!'),

    # Transcription progress
    (re.compile(r'🎙️ Transcrição em andamento:\s*(\d+)%'), '🎙️ Transcrição em andamento: {0}%'),
    (re.compile(r'🎙️ Transcribing…\s*(\d+)%'), '🎙️ Transcrição em andamento: {0}%'),
    (re.compile(r'Transcribing…\s*(\d+)%'), '🎙️ Transcrição em andamento: {0}%'),
    (re.compile(r'(?:🎙️\s*)?(?:Iniciando transcrição|Transcribing (?:video|audio))', re.I), '🎙️ Iniciando transcrição do áudio...'),
    (re.compile(r'Transcrição iniciada com sucesso', re.I), '🎙️ Transcrição iniciada com sucesso!'),
    (re.compile(r'Detected language', re.I), '✅ Transcrição concluída com sucesso!'),

    # AI Analysis & Viral Clips
    (re.compile(r'Analisando momentos virais com Inteligência Artificial', re.I), '🤖 Analisando momentos virais com Inteligência Artificial...'),
    (re.compile(r'(?:Found|identificados)\s+(\d+)\s+(?:viral\s+)?(?:clips|momentos virais)', re.I), '🔥 {0} momentos virais identificados!'),
    (re.compile(r'Found (\d+) clips', re.I), '🔥 {0} momentos virais identificados!'),

    # Clip generation & subtitles
    (re.compile(r'(?:Processing Clip|Gerando corte|Creating clip)\s+(\d+)', re.I), '🎬 Gerando corte {0}…'),
    (re.compile(r'(?:Captions burned|Auto-captions|Aplicando legendas automáticas)', re.I), '💬 Aplicando legendas automáticas…'),
    (re.compile(r'(?:Clip|Corte)\s+(\d+)\s+(?:ready|pronto)', re.I), '✅ Corte {0} pronto!'),
]


def friendly_log_line(line):
    """Map one raw log line to its user-visible pt-BR form, or None to hide it."""
    stripped = line.strip()
    if not stripped:
        return None
    for pattern, template in _RULES:
        match = pattern.search(stripped)
        if match:
            if template is None:
                return _strip_paths(stripped)
            # If the template references groups
            if '{0}' in template and match.groups():
                cleaned_groups = [_strip_paths(str(g)) for g in match.groups()]
                return template.format(*cleaned_groups)
            return template
    return None


def friendly_logs(logs):
    """Curated log list for users in pt-BR, consecutive duplicates collapsed."""
    out = []
    for line in logs:
        friendly = friendly_log_line(line)
        if friendly and (not out or out[-1] != friendly):
            out.append(friendly)
    return out
