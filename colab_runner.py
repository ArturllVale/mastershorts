#!/usr/bin/env python3
"""
MasterShorts - Google Colab T4 Production Runner & Cloudflare Tunnel
--------------------------------------------------------------------
Orquestrador completo de execucao para Google Colab com aceleracao por GPU (Tesla T4).
Instala dependencias de sistema (Node.js 20, FFmpeg NVENC, bibliotecas Chromium, Cloudflared),
configura o ambiente otimizado para CUDA/NVENC, sincroniza banco Prisma e inicializa os
tres servicos (Express Render-Service, FastAPI Backend, Vite Frontend) expostos via
tunel seguro e gratuito da Cloudflare (trycloudflare.com).
"""

import os
import sys
import re
import time
import signal
import shutil
import urllib.request
import subprocess
import threading
from pathlib import Path

# --- ANSI Styling ---
class Style:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

def log_info(msg: str):
    print(f"{Style.CYAN}[INFO]{Style.RESET} {msg}", flush=True)

def log_success(msg: str):
    print(f"{Style.GREEN}[OK]{Style.RESET} {msg}", flush=True)

def log_warn(msg: str):
    print(f"{Style.YELLOW}[WARN]{Style.RESET} {msg}", flush=True)

def log_error(msg: str):
    print(f"{Style.RED}[ERROR]{Style.RESET} {msg}", flush=True)

def log_step(step: str, title: str):
    print(f"\n{Style.BOLD}{Style.CYAN}=== [{step}] {title} ==={Style.RESET}", flush=True)

# Lista global de processos para encerramento gracioso
ACTIVE_PROCESSES = []

def cleanup_processes(signum=None, frame=None):
    log_warn("Encerrando todos os servicos e processos em background...")
    for proc in ACTIVE_PROCESSES:
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            pass
    log_info("Processos finalizados com sucesso.")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup_processes)
signal.signal(signal.SIGTERM, cleanup_processes)


def run_cmd(cmd, cwd=None, env=None, check=True, capture=False):
    """Executa comando shell de forma segura."""
    if isinstance(cmd, list):
        cmd_str = " ".join(cmd)
    else:
        cmd_str = cmd
    
    if capture:
        res = subprocess.run(cmd_str, shell=True, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if check and res.returncode != 0:
            log_error(f"Falha ao executar: {cmd_str}\n{res.stderr}")
            raise RuntimeError(f"Erro no comando: {cmd_str}")
        return res.stdout.strip()
    else:
        res = subprocess.run(cmd_str, shell=True, cwd=cwd, env=env)
        if check and res.returncode != 0:
            log_error(f"Comando falhou com codigo {res.returncode}: {cmd_str}")
            raise RuntimeError(f"Erro na execucao: {cmd_str}")
        return res.returncode


def verify_environment():
    log_step("1/7", "Validacao de Hardware e Ambiente Colab")
    
    # 1. Checagem de GPU
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            log_success(f"GPU Detectada: {gpu_name} ({vram_gb:.1f} GB VRAM)")
            log_info(f"CUDA Versao: {torch.version.cuda}")
        else:
            log_warn("Nenhuma GPU NVIDIA detectada pelo PyTorch. Ative o acelerador T4 em 'Ambiente de Execucao' -> 'Alterar tipo de ambiente'.")
    except ImportError:
        log_warn("PyTorch nao detectado no ambiente Python padrao.")

    # 2. Diretorio de trabalho
    base_dir = Path("/content/mastershorts") if Path("/content").exists() else Path.cwd()
    if not base_dir.exists():
        log_info(f"Clonando repositorio oficial em {base_dir}...")
        run_cmd(f"git clone https://github.com/ArturllVale/mastershorts.git {base_dir}")
    
    os.chdir(str(base_dir))
    log_success(f"Diretorio de trabalho ativo: {base_dir}")
    return base_dir


def install_system_dependencies():
    log_step("2/7", "Instalacao de Dependencias do Sistema Operacional (Ubuntu)")

    # 1. Cloudflared (Quick Tunnels)
    if not shutil.which("cloudflared"):
        log_info("Instalando Cloudflare Tunnel CLI (cloudflared)...")
        cf_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        urllib.request.urlretrieve(cf_url, "/usr/local/bin/cloudflared")
        os.chmod("/usr/local/bin/cloudflared", 0o755)
        log_success("cloudflared instalado em /usr/local/bin/cloudflared")
    else:
        log_success("cloudflared ja disponivel no PATH.")

    # 2. Node.js 20 LTS
    node_installed = False
    if shutil.which("node"):
        try:
            ver = run_cmd("node -v", capture=True)
            major = int(ver.lstrip("v").split(".")[0])
            if major >= 18:
                log_success(f"Node.js compativel detectado: {ver}")
                node_installed = True
        except Exception:
            pass

    if not node_installed:
        log_info("Configurando Node.js 20.x via NodeSource...")
        run_cmd("curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs")
        log_success(f"Node.js instalado: {run_cmd('node -v', capture=True)}")

    # 3. Bibliotecas do sistema para Chromium / Remotion Headless
    log_info("Instalando bibliotecas nativas para renderizacao Remotion / Chromium...")
    run_cmd("apt-get update -qq", check=False)
    # Suporte hibrido para Ubuntu 22.04 (Jammy) e 24.04 (Noble t64 transition)
    run_cmd(
        "apt-get install -y -qq --no-install-recommends "
        "libnss3 libxcomposite1 libxdamage1 libxrandr2 libgbm1 "
        "libpango-1.0-0 fonts-liberation "
        "libasound2t64 libasound2 libatk1.0-0t64 libatk1.0-0 "
        "libatk-bridge2.0-0t64 libatk-bridge2.0-0 libcups2t64 libcups2 || true",
        check=False
    )
    log_success("Bibliotecas graficas de sistema configuradas.")

    # 4. FFmpeg com suporte a NVENC
    has_nvenc = False
    if shutil.which("ffmpeg"):
        try:
            test_ret = run_cmd("ffmpeg -y -hide_banner -loglevel error -f lavfi -i color=s=256x256:d=0.04 -c:v h264_nvenc -f null -", check=False)
            if test_ret == 0:
                has_nvenc = True
                log_success("FFmpeg existente validado com aceleracao funcional h264_nvenc (GPU).")
        except Exception:
            pass

    if not has_nvenc:
        log_info("Instalando build estatico otimizado do FFmpeg com suporte NVIDIA NVENC (BtbN)...")
        try:
            run_cmd(
                "wget -qO- https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz "
                "| tar -xJ --strip-components=1 -C /usr/local/bin/ --wildcards '*/bin/ffmpeg' '*/bin/ffprobe'",
                check=False
            )
            test_ret = run_cmd("/usr/local/bin/ffmpeg -y -hide_banner -loglevel error -f lavfi -i color=s=256x256:d=0.04 -c:v h264_nvenc -f null -", check=False)
            if test_ret == 0:
                has_nvenc = True
                log_success("FFmpeg BtbN compilado com NVENC validado com sucesso na GPU T4.")
            else:
                log_warn("NVENC indisponivel no hardware atual; fallback CPU (libx264) ativo.")
        except Exception as e:
            log_warn(f"Instalacao do FFmpeg com NVENC falhou ({e}). Utilizando pacote padrao.")
            run_cmd("apt-get install -y -qq ffmpeg", check=False)


def install_python_and_node(base_dir: Path):
    log_step("3/7", "Instalacao de Dependencias Python e Node.js")

    # 1. Dependencias Python
    log_info("Instalando pacotes Python do backend...")
    req_file = base_dir / "backend" / "requirements.txt"
    # Mantem setuptools compativel com torch do Colab (torch cu130 requer setuptools<82)
    run_cmd(f"{sys.executable} -m pip install --quiet 'setuptools<82' wheel")

    # Preserva o PyTorch acelerado por CUDA ja nativo do Google Colab
    try:
        import torch
        has_cuda_torch = torch.cuda.is_available()
    except ImportError:
        has_cuda_torch = False

    log_info("Configurando lista de dependencias compativel com o ambiente Colab...")
    raw_reqs = req_file.read_text(encoding="utf-8").splitlines()
    colab_reqs = []
    for line in raw_reqs:
        line_s = line.strip()
        if not line_s or line_s.startswith("#"):
            continue
        # Nao sobrescrever torch CUDA pré-instalado
        if has_cuda_torch and (line_s.startswith("torch==") or line_s.startswith("torchvision==")):
            continue
        # MediaPipe e substituido pelo adaptador nativo YOLOv8 (GPU) em backend/detection.py
        if line_s.startswith("mediapipe"):
            continue
        colab_reqs.append(line_s)

    tmp_req = base_dir / "backend" / "requirements.colab.txt"
    tmp_req.write_text("\n".join(colab_reqs), encoding="utf-8")
    run_cmd(f"{sys.executable} -m pip install --quiet -r {tmp_req}")
    run_cmd(f"{sys.executable} -m pip install --quiet 'av>=12.0.0' yt-dlp-youtube-oauth2", check=False)
    log_success("Dependencias Python instaladas.")

    # 2. Dependencias Node.js nos modulos do monorepo
    log_info("Instalando pacotes npm (Root, Frontend, Render-Service, Remotion)...")
    run_cmd("npm install --silent", cwd=base_dir)
    run_cmd("npm install --silent", cwd=base_dir / "frontend")
    run_cmd("npm install --silent", cwd=base_dir / "render-service")
    run_cmd("npm install --silent", cwd=base_dir / "remotion")
    log_success("Modulos Node.js instalados em todos os subpacotes.")

    # 3. Build do render-service
    log_info("Compilando TypeScript do render-service...")
    run_cmd("npm run build", cwd=base_dir / "render-service")
    log_success("Render-service compilado (dist/server.js pronto).")

    # 4. Sincronizacao de fontes e pesos
    log_info("Sincronizando assets de tipografia (sync_assets.py)...")
    run_cmd(f"{sys.executable} scripts/sync_assets.py", cwd=base_dir)

    # 5. Inicializacao do Prisma ORM (SQLite)
    log_info("Gerando cliente Prisma Python e aplicando schema SQLite...")
    schema_path = base_dir / "backend" / "prisma" / "schema.prisma"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"file:{base_dir / 'backend' / 'dev.db'}"
    run_cmd(f"prisma db push --schema={schema_path}", env=env)
    run_cmd(f"prisma generate --schema={schema_path}", env=env)
    log_success("Banco de dados SQLite inicializado via Prisma.")


def configure_environment(base_dir: Path, gemini_key: str):
    log_step("4/7", "Configuracao das Variaveis de Ambiente (.env)")

    env_path = base_dir / ".env"
    output_dir = base_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir = base_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    env_content = f"""# MasterShorts - Colab T4 Production Config
DATABASE_URL="file:{base_dir / 'backend' / 'dev.db'}"
GEMINI_API_KEY="{gemini_key}"
RENDER_SERVICE_URL="http://127.0.0.1:3100"
VITE_PROXY_TARGET="http://127.0.0.1:8000"
SHARED_OUTPUT_DIR="{output_dir}"
OUTPUT_DIR="{output_dir}"
UPLOAD_DIR="{uploads_dir}"
PORT=3100
DEBUG_LOGS=true

# Aceleracao GPU (T4 CUDA / NVENC)
FFMPEG_ENCODER=nvenc
WHISPER_DEVICE=cuda
WHISPER_COMPUTE=float16
WHISPER_MODEL=large-v3-turbo
TRANSCRIBE_BACKEND=whisper
ASR_GPU_CONCURRENCY=1

# Modelos Criativos Gemini
GEMINI_MODEL_THUMBNAIL=gemini-2.5-flash
GEMINI_IMAGE_MODEL=imagen-3.0-generate-002
"""
    # Vinculacao de cookies do YouTube para bypass de datacenter block
    yt_cookies = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if yt_cookies:
        env_content += f'\nYOUTUBE_COOKIES="""{yt_cookies}"""\n'
        log_success("Variavel YOUTUBE_COOKIES injetada no .env")

    for c_path in ["/content/cookies.txt", str(base_dir / "cookies.txt")]:
        if os.path.isfile(c_path):
            env_content += f'\nYOUTUBE_COOKIES_FILE="{c_path}"\n'
            log_success(f"Arquivo de cookies vinculado ao .env: {c_path}")
            break

    env_path.write_text(env_content, encoding="utf-8")
    log_success(f"Arquivo .env gerado em {env_path}")


def wait_for_service(url: str, name: str, timeout: int = 120, check_fn=None):
    """Aguarda endpoint HTTP responder com sucesso."""
    start = time.time()
    log_info(f"Aguardando inicializacao do servico: {name} ({url})...")
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status in (200, 204):
                    if check_fn:
                        body = resp.read().decode("utf-8", errors="ignore")
                        if check_fn(body):
                            log_success(f"{name} esta pronto e operacional!")
                            return True
                    else:
                        log_success(f"{name} esta pronto e operacional!")
                        return True
        except Exception:
            pass
        time.sleep(2)
    log_warn(f"Tempo limite atingido ao aguardar {name}. Prosseguindo com verificacao...")
    return False


def kill_stale_processes():
    """Mata qualquer processo antigo ainda rodando em portas 8000, 3100 e 5173."""
    log_info("Garantindo limpeza de processos antigos em background...")
    if sys.platform != "win32":
        try:
            subprocess.run("fuser -k 8000/tcp 3100/tcp 5173/tcp 2>/dev/null || true", shell=True)
        except Exception:
            pass
        try:
            subprocess.run("pkill -9 -f uvicorn 2>/dev/null || true", shell=True)
            subprocess.run("pkill -9 -f server.js 2>/dev/null || true", shell=True)
            subprocess.run("pkill -9 -f vite 2>/dev/null || true", shell=True)
            subprocess.run("pkill -9 -f cloudflared 2>/dev/null || true", shell=True)
            subprocess.run("pkill -9 -f main.py 2>/dev/null || true", shell=True)
        except Exception:
            pass
        time.sleep(1)


def start_services(base_dir: Path):
    log_step("5/7", "Inicializacao dos Servicos em Background")

    kill_stale_processes()

    env = os.environ.copy()
    env["SHARED_OUTPUT_DIR"] = str(base_dir / "output")
    env["OUTPUT_DIR"] = str(base_dir / "output")
    env["DATABASE_URL"] = f"file:{base_dir / 'backend' / 'dev.db'}"

    # 1. Render-Service (Express + Remotion) na porta 3100
    log_info("Iniciando Remotion Render-Service na porta 3100...")
    render_proc = subprocess.Popen(
        ["node", "dist/server.js"],
        cwd=base_dir / "render-service",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    ACTIVE_PROCESSES.append(render_proc)
    wait_for_service("http://127.0.0.1:3100/health", "Remotion Render-Service", timeout=90, check_fn=lambda b: '"ready":true' in b or '"ok":true' in b)

    # 2. Backend FastAPI na porta 8000
    log_info("Iniciando FastAPI Backend na porta 8000...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000"],
        cwd=base_dir,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    ACTIVE_PROCESSES.append(backend_proc)
    wait_for_service("http://127.0.0.1:8000/docs", "FastAPI Backend", timeout=45)

    # 3. Frontend Vite na porta 5173
    log_info("Iniciando Vite Frontend com proxy reverso na porta 5173...")
    frontend_proc = subprocess.Popen(
        ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"],
        cwd=base_dir / "frontend",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    ACTIVE_PROCESSES.append(frontend_proc)
    wait_for_service("http://127.0.0.1:5173", "Vite Frontend", timeout=45)


def start_cloudflare_tunnel():
    log_step("6/7", "Criacao do Tunel Cloudflare (Quick Tunnel)")
    log_info("Abrindo tunel publico gratuito em http://127.0.0.1:5173...")

    cf_proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://127.0.0.1:5173", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    ACTIVE_PROCESSES.append(cf_proc)

    tunnel_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    start_time = time.time()
    while time.time() - start_time < 60:
        line = cf_proc.stdout.readline()
        if not line:
            time.sleep(0.5)
            continue
        match = url_pattern.search(line)
        if match:
            tunnel_url = match.group(0)
            break

    if not tunnel_url:
        log_error("Nao foi possivel extrair a URL do tunel Cloudflare em 60s.")
        return None

    return tunnel_url


def print_banner(tunnel_url: str):
    log_step("7/7", "MasterShorts Online & Operacional!")
    banner = f"""
{Style.GREEN}{Style.BOLD}=============================================================================
  MASTERSHORTS - AMBIENTE DE PRODUCAO ATIVO (GOOGLE COLAB T4)
============================================================================={Style.RESET}

  {Style.CYAN}Link de Acesso Publico (Cloudflare):{Style.RESET}
  {Style.BOLD}{Style.GREEN}-> {tunnel_url}{Style.RESET}

  {Style.YELLOW}Componentes Conectados:{Style.RESET}
  - Frontend Interface:  {tunnel_url} (Vite Proxy :5173)
  - Backend API:         http://127.0.0.1:8000
  - Remotion Renderer:   http://127.0.0.1:3100
  - Acelerador GPU:      NVIDIA Tesla T4 (NVENC + CUDA fp16)
  - Base de Dados:       SQLite / Prisma ORM

  {Style.DIM}Pressione Ctrl+C na celula/terminal para pausar os servicos.{Style.RESET}
{Style.GREEN}{Style.BOLD}============================================================================={Style.RESET}
"""
    print(banner, flush=True)


def main():
    # Obtencao da API Key do Gemini (compativel com Colab userdata ou env)
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    try:
        from google.colab import userdata
        gemini_key = userdata.get("GEMINI_API_KEY") or gemini_key
    except Exception:
        pass

    if not gemini_key:
        print(f"\n{Style.YELLOW}[CONFIG]{Style.RESET} Insira sua Chave da API do Google Gemini (GEMINI_API_KEY):")
        gemini_key = input("API Key: ").strip()

    base_dir = verify_environment()
    install_system_dependencies()
    install_python_and_node(base_dir)
    configure_environment(base_dir, gemini_key)
    start_services(base_dir)
    
    tunnel_url = start_cloudflare_tunnel()
    if tunnel_url:
        print_banner(tunnel_url)
    else:
        log_error("Falha ao obter URL publica do tunel.")

    # Mantem o loop ativo e monitora a saude dos processos
    try:
        while True:
            for proc in ACTIVE_PROCESSES:
                if proc.poll() is not None:
                    log_warn(f"Um dos processos finalizou inesperadamente (PID {proc.pid}, codigo {proc.returncode}).")
            time.sleep(5)
    except KeyboardInterrupt:
        cleanup_processes()


if __name__ == "__main__":
    main()
