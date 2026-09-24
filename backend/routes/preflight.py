import os
import sys
import shutil
import subprocess
import uuid
import httpx
from typing import List, Dict, Any
from fastapi import APIRouter
from core.config import OUTPUT_DIR, BACKEND_DIR, ROOT_DIR

router = APIRouter()


def _sanitize_url(url: str) -> str:
    """Mask credentials in database / service URLs."""
    if not url:
        return ""
    import re
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)


async def _check_ffmpeg() -> Dict[str, Any]:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return {
            "id": "ffmpeg",
            "name": "FFmpeg",
            "status": "error",
            "message": "Binário do FFmpeg não encontrado no PATH",
            "detail": "Indisponível no PATH do sistema",
            "troubleshooting": "Instale o FFmpeg e adicione o executável ao PATH do sistema."
        }
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5
        )
        first_line = proc.stdout.splitlines()[0] if proc.stdout else "Versão detectada"
        return {
            "id": "ffmpeg",
            "name": "FFmpeg",
            "status": "ok",
            "message": first_line.split(" Copyright")[0].strip(),
            "detail": ffmpeg_bin,
            "troubleshooting": None
        }
    except Exception as e:
        return {
            "id": "ffmpeg",
            "name": "FFmpeg",
            "status": "error",
            "message": f"Erro ao executar FFmpeg: {str(e)}",
            "detail": ffmpeg_bin,
            "troubleshooting": "Verifique as permissões de execução do binário."
        }


async def _check_render_service() -> Dict[str, Any]:
    render_url = os.environ.get("RENDER_SERVICE_URL", "http://localhost:3100").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.get(f"{render_url}/health")
            if resp.status_code == 200:
                data = resp.json()
                is_ready = data.get("ready", True)
                if is_ready:
                    return {
                        "id": "render_service",
                        "name": "Render Service (Remotion)",
                        "status": "ok",
                        "message": "Online e pronto",
                        "detail": f"{render_url}/health (ready: true)",
                        "troubleshooting": None
                    }
                else:
                    return {
                        "id": "render_service",
                        "name": "Render Service (Remotion)",
                        "status": "warn",
                        "message": "Online (compilando bundle Remotion)",
                        "detail": f"{render_url}/health (ready: false)",
                        "troubleshooting": "Aguarde o término do empacotamento inicial das composições Remotion."
                    }
            else:
                return {
                    "id": "render_service",
                    "name": "Render Service (Remotion)",
                    "status": "error",
                    "message": f"Resposta inesperada HTTP {resp.status_code}",
                    "detail": render_url,
                    "troubleshooting": "Verifique os logs de execução do render-service."
                }
    except Exception:
        return {
            "id": "render_service",
            "name": "Render Service (Remotion)",
            "status": "warn",
            "message": "Serviço offline ou inacessível",
            "detail": render_url,
            "troubleshooting": "Inicie o microsserviço com 'npm run dev:renderer' ou 'npm run dev'."
        }


async def _check_prisma() -> Dict[str, Any]:
    db_url = os.environ.get("DATABASE_URL", "file:./dev.db")
    masked_db = _sanitize_url(db_url)
    try:
        from database.connection import get_prisma
        prisma = await get_prisma()
        if not getattr(prisma, "is_connected", lambda: False)():
            await prisma.connect()
        # Verify query execution
        count = await prisma.job.count()
        return {
            "id": "prisma",
            "name": "Banco de Dados (Prisma)",
            "status": "ok",
            "message": f"Conectado ({count} jobs registrados)",
            "detail": masked_db,
            "troubleshooting": None
        }
    except Exception as e:
        return {
            "id": "prisma",
            "name": "Banco de Dados (Prisma)",
            "status": "error",
            "message": f"Erro de conexão: {str(e)}",
            "detail": masked_db,
            "troubleshooting": "Execute 'python prisma_migrate.py dev --name init' na pasta backend para inicializar o banco."
        }


async def _check_llm(request) -> Dict[str, Any]:
    # Check headers first (from UI settings)
    gemini_key = request.headers.get("x-llm-api-key") or request.headers.get("X-LLM-API-Key") or os.environ.get("GEMINI_API_KEY", "").strip()
    openrouter_key = request.headers.get("x-openrouter-key") or request.headers.get("X-OpenRouter-Key") or os.environ.get("OPENROUTER_API_KEY", "").strip()
    mistral_key = request.headers.get("x-mistral-key") or request.headers.get("X-Mistral-Key") or os.environ.get("MISTRAL_API_KEY", "").strip()
    openai_key = request.headers.get("x-llm-api-key") or request.headers.get("X-LLM-API-Key") or os.environ.get("LLM_API_KEY", "").strip()
    openai_base = request.headers.get("x-llm-base-url") or request.headers.get("X-LLM-Base-URL") or os.environ.get("LLM_BASE_URL", "").strip()
    
    try:
        import core.llm_backend as llm_backend
        local_desc = llm_backend.describe()
    except Exception:
        local_desc = None

    def mask(k):
        return f"{k[:4]}...{k[-4:]}" if len(k) > 8 else "***"

    found_keys = []
    if gemini_key:
        found_keys.append(f"Gemini ({mask(gemini_key)})")
    if openrouter_key:
        found_keys.append(f"OpenRouter ({mask(openrouter_key)})")
    if mistral_key:
        found_keys.append(f"Mistral ({mask(mistral_key)})")
    if openai_key or openai_base:
        found_keys.append(f"Endpoint Customizado/OpenAI")

    if found_keys:
        return {
            "id": "llm",
            "name": "Gemini / OpenRouter / Mistral / Endpoint",
            "status": "ok",
            "message": "Chaves configuradas: " + ", ".join(found_keys),
            "detail": f"Chaves detectadas no ambiente",
            "troubleshooting": None
        }
    elif local_desc:
        return {
            "id": "llm",
            "name": "Gemini / Local LLM",
            "status": "ok",
            "message": f"Local LLM ativo ({local_desc})",
            "detail": "Provedor local configurado via ambiente",
            "troubleshooting": None
        }
    else:
        return {
            "id": "llm",
            "name": "Modelos de IA",
            "status": "warn",
            "message": "Nenhuma chave de IA detectada",
            "detail": "Chaves (Gemini, OpenRouter, Mistral, Endpoint Customizado) ausentes",
            "troubleshooting": "Defina as chaves de API no arquivo .env ou através das configurações da interface."
        }


async def _check_output_dir() -> Dict[str, Any]:
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        test_filename = os.path.join(OUTPUT_DIR, f".preflight_test_{uuid.uuid4().hex[:8]}")
        with open(test_filename, "w", encoding="utf-8") as f:
            f.write("preflight_ok")
        if os.path.exists(test_filename):
            os.remove(test_filename)
        return {
            "id": "output_dir",
            "name": "Diretório de Saída (output)",
            "status": "ok",
            "message": "Diretório acessível e gravável",
            "detail": os.path.abspath(OUTPUT_DIR),
            "troubleshooting": None
        }
    except Exception as e:
        return {
            "id": "output_dir",
            "name": "Diretório de Saída (output)",
            "status": "error",
            "message": f"Sem permissão de gravação: {str(e)}",
            "detail": os.path.abspath(OUTPUT_DIR),
            "troubleshooting": "Verifique permissões de leitura/escrita do sistema de arquivos para o diretório output/."
        }


async def _check_gpu_encoder() -> Dict[str, Any]:
    try:
        import ffmpeg_utils
        has_nvenc = ffmpeg_utils.nvenc_available()
        encoder_name = ffmpeg_utils.get_selected_encoder_name()
        if has_nvenc:
            return {
                "id": "gpu_encoder",
                "name": "Aceleração por GPU (NVENC)",
                "status": "ok",
                "message": f"Ativa: {encoder_name}",
                "detail": "NVIDIA NVENC h264_nvenc operacional",
                "troubleshooting": None
            }
        else:
            return {
                "id": "gpu_encoder",
                "name": "Aceleração por GPU (NVENC)",
                "status": "info",
                "message": f"Fallback CPU: {encoder_name}",
                "detail": "GPU não disponível ou driver sem suporte a h264_nvenc",
                "troubleshooting": "Para acelerar renders em até 5x, instale drivers NVIDIA recentes e uma build FFmpeg com suporte NVENC."
            }
    except Exception as e:
        return {
            "id": "gpu_encoder",
            "name": "Aceleração por GPU (NVENC)",
            "status": "info",
            "message": f"Detecção indisponível: {str(e)}",
            "detail": "Fallback automático para CPU",
            "troubleshooting": None
        }


async def _check_ytdlp() -> Dict[str, Any]:
    try:
        import yt_dlp
        version = getattr(yt_dlp.version, "__version__", "instalada")
        return {
            "id": "ytdlp",
            "name": "yt-dlp",
            "status": "ok",
            "message": f"Versão {version} disponível",
            "detail": "Módulo de ingestão do YouTube pronto",
            "troubleshooting": None
        }
    except Exception as e:
        return {
            "id": "ytdlp",
            "name": "yt-dlp",
            "status": "error",
            "message": f"Falha ao carregar yt-dlp: {str(e)}",
            "detail": "Não instalado no ambiente Python",
            "troubleshooting": "Execute 'pip install yt-dlp' no ambiente virtual do backend."
        }


async def _check_cookies() -> Dict[str, Any]:
    cookie_env = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if cookie_env:
        return {
            "id": "cookies",
            "name": "Cookies do YouTube",
            "status": "ok",
            "message": "Configurado via variável YOUTUBE_COOKIES",
            "detail": f"{len(cookie_env)} caracteres em memória",
            "troubleshooting": None
        }

    # Search known candidate paths
    candidates = [
        os.path.join(BACKEND_DIR, "www.youtube.com_cookies.txt"),
        os.path.join(BACKEND_DIR, "cookies.txt"),
        os.path.join(ROOT_DIR, "cookies.txt"),
        "/app/cookies.txt",
    ]
    found_path = None
    for cand in candidates:
        if os.path.exists(cand) and os.path.getsize(cand) > 0:
            found_path = cand
            break

    if found_path:
        size = os.path.getsize(found_path)
        try:
            with open(found_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(500)
            has_cookie_header = "# Netscape" in content or "youtube.com" in content
            return {
                "id": "cookies",
                "name": "Cookies do YouTube",
                "status": "ok" if has_cookie_header else "warn",
                "message": f"Arquivo detectado ({os.path.basename(found_path)} - {size} bytes)",
                "detail": os.path.abspath(found_path),
                "troubleshooting": None if has_cookie_header else "O arquivo de cookies não parece estar no formato Netscape válido."
            }
        except Exception as e:
            return {
                "id": "cookies",
                "name": "Cookies do YouTube",
                "status": "warn",
                "message": f"Erro ao ler arquivo de cookies: {str(e)}",
                "detail": found_path,
                "troubleshooting": "Verifique as permissões de leitura do arquivo."
            }

    return {
        "id": "cookies",
        "name": "Cookies do YouTube",
        "status": "info",
        "message": "Não configurado (opcional)",
        "detail": "Nenhum arquivo cookies.txt encontrado",
        "troubleshooting": "Opcional: adicione um arquivo cookies.txt na raiz ou backend/ para evitar restrições de download em vídeos 1080p+ do YouTube."
    }


from fastapi import APIRouter, Request

@router.get("/api/preflight")
async def run_preflight(request: Request):
    """Execute all system preflight checks and return operational status."""
    checks: List[Dict[str, Any]] = [
        await _check_ffmpeg(),
        await _check_render_service(),
        await _check_prisma(),
        await _check_llm(request),
        await _check_output_dir(),
        await _check_gpu_encoder(),
        await _check_ytdlp(),
        await _check_cookies(),
    ]

    has_error = any(c["status"] == "error" for c in checks)
    has_warn = any(c["status"] == "warn" for c in checks)

    overall_status = "error" if has_error else ("warn" if has_warn else "ok")

    return {
        "status": overall_status,
        "all_ok": not has_error,
        "checks": checks
    }
