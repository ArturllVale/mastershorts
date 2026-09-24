# Master Shorts

Plataforma proprietária de inteligência artificial para transformar vídeos longos (podcasts, aulas, entrevistas, webinars) em vídeos curtos virais no formato 9:16 para TikTok, Instagram Reels e YouTube Shorts.

---

## Estrutura do Projeto

O projeto é organizado no formato monorepo modular:

```
├── backend/            # API FastAPI (processamento de vídeo, IA, filas, endpoints)
│   ├── core/           # Configurações, modelos Pydantic e estado da aplicação
│   ├── database/       # Acesso ao banco de dados com Prisma Client (e legado SQLAlchemy)
│   ├── prisma/         # Schemas Prisma (schema.prisma para SQLite, schema.prod.prisma para Postgres)
│   ├── routes/         # Rotas modularizadas (clips, thumbnails, processamento)
│   ├── services/       # Fila de trabalhos assíncrona (job queue) e workers
│   └── requirements.txt
├── frontend/           # Interface web em React + Vite + TailwindCSS
├── remotion/           # Composição e renderização de vídeo programática
├── render-service/     # Microsserviço Express de renderização Remotion
├── scripts/            # Scripts auxiliares de inicialização e instalação do ambiente
└── package.json        # Scripts de conveniência na raiz do projeto
```

---

## Pré-requisitos

- **Python**: 3.11 ou superior
- **Node.js**: 18 ou superior
- **FFmpeg**: Instalado e acessível no `PATH` do sistema
- **Git**

---

## Instalação e Configuração Rápida

### 1. Clonar o repositório e configurar o ambiente

```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd master-shorts
cp .env.example .env
```

Edite o arquivo `.env` e configure suas variáveis:
- **Essenciais:** `GEMINI_API_KEY` (IA de momentos), `DATABASE_URL` (banco de dados).
- **Serviços:** `RENDER_SERVICE_URL` (padrão `http://localhost:3100`), `VITE_PROXY_TARGET` (padrão `http://127.0.0.1:8000`).
- **Telemetria/Analytics (Opcional):** `VITE_OPENPANEL_API_URL` e `VITE_OPENPANEL_CLIENT_ID` (mantenha vazios `""` para desativar a coleta de métricas e suprimir alertas de compilação do Vite).

### 2. Instalar dependências

Você pode instalar as dependências de todos os componentes da aplicação de uma só vez através do script raiz:

```bash
npm run install:all
```

*(O comando acima executa `npm install` na raiz e instala dependências do `frontend`, `render-service`, `remotion` e pacotes Python do `backend`).*

Ou instalar os componentes individualmente:

```bash
# Frontend
npm run install:frontend

# Backend
npm run install:backend
# (Ou manualmente via pip: pip install -r backend/requirements.txt)

# Microsserviço de Renderização
npm run install:renderer

# Pacotes do Remotion
npm run install:remotion
```

### Configurando o Banco de Dados (Prisma)

O backend utiliza o **Prisma Client Python** para mapeamento ORM:
- **Desenvolvimento:** Utilizamos o arquivo `backend/prisma/schema.prisma` com provider `sqlite`. O `.env` deve ter `DATABASE_URL="file:./dev.db"`.
- **Produção:** Utilizamos o arquivo `backend/prisma/schema.prod.prisma` com provider `postgresql`. O `.env` deve ter a URL completa do banco PostgreSQL, por exemplo `DATABASE_URL="postgres://user:pass@host:5432/mastershorts"`.

Para executar as migrações localmente, utilizamos um script auxiliar em Python (`prisma_migrate.py`) que detecta o ambiente e invoca o comando apropriado do Prisma com o schema correto.

**Geração inicial do banco de desenvolvimento (SQLite):**

Linux / macOS (Bash):
```bash
cd backend
export DATABASE_URL="file:./dev.db"
python prisma_migrate.py dev --name init
```

Windows (PowerShell):
```powershell
cd backend
$env:DATABASE_URL="file:./dev.db"
python prisma_migrate.py dev --name init
```
*(Nota: `prisma_migrate.py` assume `file:./dev.db` por padrão se `DATABASE_URL` não for definido).*

---

## Executando o Projeto

Para rodar backend, frontend e render-service simultaneamente:

```bash
npm run dev # backend: 8000 # frontend: 5173 # renderer: 3100
```

- **Frontend**: `http://localhost:5173`
- **Backend API**: `http://localhost:8000`
- **Renderer Service (Remotion)**: `http://localhost:3100` (Health Check: `http://localhost:3100/health`)
- **Documentação Swagger**: `http://localhost:8000/docs`

Você também pode executar os serviços individualmente em terminais separados:

```bash
# Terminal 1 - Backend (FastAPI)
npm run dev:backend

# Terminal 2 - Frontend (Vite)
npm run dev:frontend

# Terminal 3 - Renderer Service (Remotion)
npm run dev:renderer
```

---

## Troubleshooting: Render Service (`render-service`)

O `render-service` é responsável pela composição e renderização programática via Remotion. Caso encontre inconsistências durante a execução, verifique os pontos abaixo:

1. **Porta 3100 em uso ou conexão recusada (`ECONNREFUSED`):**
   - Certifique-se de que o serviço foi iniciado via `npm run dev:renderer` ou `npm run dev`.
   - Teste a conectividade acessando `http://localhost:3100/health`. Deve retornar `{"ok": true, "ready": true}` quando pronto.
   - Caso a porta 3100 esteja ocupada, finalize o processo concorrente ou altere `PORT` nas variáveis de ambiente do `render-service`.

2. **Bundle do Remotion em compilação inicial (`ready: false`):**
   - Na primeira inicialização, o `@remotion/bundler` compila dinamicamente as composições contidas em `remotion/`.
   - Enquanto a compilação ocorre, requisições para `/health` retornarão `ready: false` e renderizações serão retidas até que o bundle esteja pronto.

3. **Módulos Remotion ausentes:**
   - Se ocorrer erro de módulo não encontrado (`Cannot find module '@remotion/renderer'` ou `@remotion/bundler`), certifique-se de ter rodado:
     ```bash
     npm run install:renderer
     npm run install:remotion
     ```

4. **Dependências de sistema do Chromium headless (Linux / Docker):**
   - O Remotion requer uma instância do Chromium instalada no ambiente. Em servidores Linux sem interface gráfica, garanta a presença das bibliotecas nativas:
     ```bash
     sudo apt-get update && sudo apt-get install -y \
       libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
       libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
       libpango-1.0-0 libasound2
     ```

5. **Volume de saída compartilhado (`SHARED_OUTPUT_DIR` / `OUTPUT_DIR`):**
   - O FastAPI (`backend`) e o `render-service` precisam acessar o mesmo diretório de arquivos de mídia (`output/`).
   - Se os vídeos gerados não puderem ser encontrados pelo renderer, configure a variável `SHARED_OUTPUT_DIR` apontando para o mesmo caminho absoluto em ambos os serviços.

---

## Scripts Disponíveis no `package.json`

| Comando | Descrição |
|---|---|
| `npm run dev` | Executa Backend (8000), Frontend (5173) e Renderer (3100) simultaneamente |
| `npm run dev:backend` | Inicia o servidor FastAPI com hot-reload na porta 8000 via `scripts/dev-backend.js` |
| `npm run dev:frontend` | Inicia o servidor Vite do frontend na porta 5173 |
| `npm run dev:renderer` | Inicia o microsserviço de renderização Remotion na porta 3100 |
| `npm run install:all` | Instala dependências da raiz, frontend, render-service, remotion e backend |
| `npm run install:frontend` | Instala dependências em `frontend/` |
| `npm run install:backend` | Instala dependências Python em `backend/requirements.txt` via virtualenv |
| `npm run install:renderer` | Instala dependências em `render-service/` |
| `npm run install:remotion` | Instala dependências em `remotion/` |
| `npm run build:frontend` | Gera o build de produção do frontend em `frontend/dist` |
| `npm run lint` | Executa o linter ESLint em todo o repositório |

---

## Aceleração por GPU (NVENC / CUDA)

O MasterShorts detecta e utiliza automaticamente a aceleração por hardware (NVIDIA GPU) caso esteja disponível no sistema, o que pode acelerar as renderizações em até 5x e reduzir drasticamente o uso da CPU.

Para garantir que o FFmpeg está usando sua GPU (`h264_nvenc`):

**1. Instalação do Driver NVIDIA**
- Tenha uma GPU NVIDIA compatível.
- Instale ou atualize o driver oficial da sua placa de vídeo mais recente a partir do [NVIDIA Driver Downloads](https://www.nvidia.com/Download/index.aspx) ou do GeForce Experience.
- Instale o CUDA Toolkit se não foi incluído com o seu ambiente.

**2. Instalação do FFmpeg com Suporte NVENC**
- **Windows:** Baixe a versão mais recente em [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (a build "essentials" ou "full" já traz o nvenc embutido por padrão).
- **Linux:** O FFmpeg padrão das distros geralmente **não** vem com nvenc devido a restrições de licença.
  - Para Ubuntu/Debian: Instale dependências de hardware (`sudo apt install nvidia-cuda-toolkit`) ou compile o FFmpeg / instale build estática.
- **macOS:** NVENC não é suportado no macOS, o sistema cairá no fallback para CPU (`libx264`).

**Verificação de Suporte:**
- O servidor avisa na inicialização ou no primeiro encode: `Encoder escolhido: h264_nvenc (GPU)` ou `libx264 (CPU)`.
- Você também pode rodar no terminal: `ffmpeg -hide_banner -encoders` e verificar se `h264_nvenc` está na lista de encoders suportados.

---

## Licença e Termos de Uso

**Proprietário e Confidencial.** Todos os direitos reservados.  
Este software é privado e de uso restrito. Nenhuma parte deste código-fonte pode ser copiada, distribuída, sublicenciada, modificada ou utilizada comercialmente sem autorização prévia por escrito do autor.
