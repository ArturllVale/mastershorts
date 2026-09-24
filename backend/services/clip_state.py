"""clip_state — regras canônicas de estado para clips e jobs.

Estados canônicos:
    Clip:  queued | rendering | ready | failed
    Job:   queued | processing | completed | partial | failed

Regras:
    job = completed  se TODOS os clips estão ready
    job = partial    se ≥1 ready E ≥1 failed
    job = failed     se TODOS failed, ou lista vazia
"""

from __future__ import annotations

import json
import traceback as _tb
from typing import Any

# ---------------------------------------------------------------------------
# Estado do job derivado dos estados dos clips
# ---------------------------------------------------------------------------

CLIP_TERMINAL = frozenset({"ready", "failed"})
CLIP_ALL = frozenset({"queued", "rendering", "ready", "failed"})


def compute_job_status(clip_statuses: list[str]) -> str:
    """Calcula o status final do job a partir da lista de estados de seus clips.

    Ignora clips ainda em estados não-terminais (queued/rendering) para o
    cálculo — eles não devem impedir a finalização quando o pool já encerrou.
    """
    if not clip_statuses:
        return "failed"

    n_ready = sum(1 for s in clip_statuses if s == "ready")
    n_failed = sum(1 for s in clip_statuses if s == "failed")

    if n_ready == 0 and n_failed == 0:
        # Nenhum clip atingiu estado terminal (edge case: pool encerrou sem
        # emitir nenhum marker — trata como falha total).
        return "failed"

    if n_failed == 0:
        return "completed"

    if n_ready == 0:
        return "failed"

    # ≥1 ready e ≥1 failed
    return "partial"


# ---------------------------------------------------------------------------
# Helpers para serialização de erros de clip
# ---------------------------------------------------------------------------

def make_clip_error(exc: BaseException) -> dict[str, Any]:
    """Serializa uma exceção capturada num worker de clip."""
    tb_text = _tb.format_exc()
    return {
        "exc_type": type(exc).__name__,
        "message": str(exc)[:500],
        "traceback": tb_text[:2000],
    }


def encode_clip_failed_marker(index: int, exc: BaseException) -> str:
    """Retorna a linha stdout a ser emitida quando um clip falha."""
    return json.dumps({"v": 1, "type": "clip.failed", "index": index, "error": make_clip_error(exc)}, ensure_ascii=False)

def decode_clip_failed_marker(line: str) -> tuple[int, dict[str, Any]] | None:
    """Parseia uma linha do stdout do filho.

    Retorna ``(index, error_dict)`` ou ``None`` se inválida.
    """
    try:
        ev = json.loads(line)
        if ev.get("type") == "clip.failed":
            return ev.get("index"), ev.get("error", {})
        return None
    except Exception:
        return None
