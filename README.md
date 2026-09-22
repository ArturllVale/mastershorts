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

Edite o arquivo `.env` e configure suas chaves de API (ex: `GEMINI_API_KEY`, etc.).

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
- **Produção:** Utilizamos o arquivo `backend/prisma/schema.prod.prisma` com provider `postgresql`. O `.env` deve ter a URL completa do banco PostgreSQL, por exemplo `DATABASE_URL="postgres://user:pass@host:5432/openshorts"`.

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

Distribuído sob a licença MIT. Consulte o arquivo [LICENSE](file:///c:/Users/Vale/Documents/github/openshorts/LICENSE) para mais detalhes.

## AceleraÃ§Ã£o por GPU (NVENC / CUDA)

O OpenShorts detecta e utiliza automaticamente a aceleraÃ§Ã£o por hardware (NVIDIA GPU) caso esteja disponÃ­vel no sistema, o que pode acelerar as renderizaÃ§Ãµes em atÃ© 5x e reduzir drasticamente o uso da CPU.

Para garantir que o FFmpeg estÃ¡ usando sua GPU (h264_nvenc):

**1. InstalaÃ§Ã£o do Driver NVIDIA**
- Tenha uma GPU NVIDIA compatÃ­vel.
- Instale ou atualize o driver oficial da sua placa de vÃ­deo mais recente a partir do [NVIDIA Driver Downloads](https://www.nvidia.com/Download/index.aspx) ou do GeForce Experience.
- Instale o CUDA Toolkit se nÃ£o foi incluÃ­do com o seu ambiente.

**2. InstalaÃ§Ã£o do FFmpeg com Suporte NVENC**
- **Windows:** Baixe a versÃ£o mais recente em [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (a build "essentials" ou "full" jÃ¡ traz o nvenc embutido por padrÃ£o).
- **Linux:** O FFmpeg padrÃ£o das distros geralmente **nÃ£o** vem com nvenc devido a restriÃ§Ãµes de licenÃ§a.
  - Para Ubuntu/Debian: VocÃª pode precisar instalar dependÃªncias de hardware (`sudo apt install nvidia-cuda-toolkit`) e as vezes compilar o FFmpeg ou instalar uma build estÃ¡tica de [johnvansickle.com/ffmpeg](https://johnvansickle.com/ffmpeg/).
- **macOS:** NVENC nÃ£o Ã© suportado no macOS, o sistema cairÃ¡ no fallback para CPU com gracefully degradada qualidade (x264).

**VerificaÃ§Ã£o de Suporte:**
- O servidor avisa na inicializaÃ§Ã£o ou no primeiro encode: `Encoder escolhido: h264_nvenc (GPU)` ou `libx264 (CPU)`.
- VocÃª tambÃ©m pode rodar no terminal: `ffmpeg -hide_banner -encoders` e verificar visualmente se `h264_nvenc` estÃ¡ na lista de encoders de vÃ­deo com suporte.
