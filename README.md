# Master Shorts

Plataforma de inteligência artificial de código aberto para transformar vídeos longos (podcasts, aulas, entrevistas, webinars) em vídeos curtos virais no formato 9:16 para TikTok, Instagram Reels e YouTube Shorts.

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
├── render-service/     # Microsserviço de renderização
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

Você pode instalar as dependências de todos os componentes através do script raiz:

```bash
npm run install:all
```

Ou instalar manualmente:

```bash
# Frontend
npm --prefix frontend install

# Backend
pip install -r backend/requirements.txt
```

### Configurando o Banco de Dados (Prisma)

O backend agora utiliza o **Prisma Client Python** para mapeamento ORM.
Devido a restrições do Prisma que impedem o uso de variáveis de ambiente para definir o `provider` do banco de forma dinâmica, usamos a seguinte abordagem:
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

Para rodar o backend e o frontend simultaneamente:

```bash
npm run dev
```

- **Frontend**: `http://localhost:5173`
- **Backend API**: `http://localhost:8000`
- **Documentação Swagger**: `http://localhost:8000/docs`

Você também pode executar os serviços individualmente em terminais separados:

```bash
# Terminal 1 - Backend (FastAPI)
npm run dev:backend

# Terminal 2 - Frontend (Vite)
npm run dev:frontend
```

---

## Scripts Disponíveis no `package.json`

| Comando | Descrição |
|---|---|
| `npm run dev` | Executa Backend e Frontend simultaneamente com logs coloridos |
| `npm run dev:backend` | Inicia o servidor FastAPI com hot-reload na porta 8000 |
| `npm run dev:frontend` | Inicia o servidor Vite do frontend |
| `npm run build:frontend` | Gera o build de produção do frontend em `frontend/dist` |
| `npm run install:all` | Instala dependências do frontend e do backend |

---

## Licença

Distribuído sob a licença MIT. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.

## Aceleração por GPU (NVENC / CUDA)

O MasterShorts detecta e utiliza automaticamente a aceleração por hardware (NVIDIA GPU) caso esteja disponível no sistema, o que pode acelerar as renderizações em até 5x e reduzir drasticamente o uso da CPU.

Para garantir que o FFmpeg está usando sua GPU (h264_nvenc):

**1. Instalação do Driver NVIDIA**
- Tenha uma GPU NVIDIA compatível.
- Instale ou atualize o driver oficial da sua placa de vídeo mais recente a partir do [NVIDIA Driver Downloads](https://www.nvidia.com/Download/index.aspx) ou do GeForce Experience.
- Instale o CUDA Toolkit se não foi incluído com o seu ambiente.

**2. Instalação do FFmpeg com Suporte NVENC**
- **Windows:** Baixe a versão mais recente em [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (a build "essentials" ou "full" já traz o nvenc embutido por padrão).
- **Linux:** O FFmpeg padrão das distros geralmente **não** vem com nvenc devido a restrições de licença.
  - Para Ubuntu/Debian: Instale dependências de hardware (`sudo apt install nvidia-cuda-toolkit`) ou compile o FFmpeg / instale build estática.
- **macOS:** NVENC não é suportado no macOS, o sistema cairá no fallback para CPU (libx264).

**Verificação de Suporte:**
- O servidor avisa na inicialização ou no primeiro encode: `Encoder escolhido: h264_nvenc (GPU)` ou `libx264 (CPU)`.
- Você também pode rodar no terminal: `ffmpeg -hide_banner -encoders` e verificar se `h264_nvenc` está na lista de encoders suportados.
