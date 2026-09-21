# Master Shorts

Plataforma de inteligência artificial de código aberto para transformar vídeos longos (podcasts, aulas, entrevistas, webinars) em vídeos curtos virais no formato 9:16 para TikTok, Instagram Reels e YouTube Shorts.

---

## Estrutura do Projeto

O projeto é organizado no formato monorepo modular:

```
├── backend/            # API FastAPI (processamento de vídeo, IA, filas, endpoints)
│   ├── core/           # Configurações, modelos Pydantic e estado da aplicação
│   ├── database/       # Conexão SQLAlchemy e modelos de persistência
│   ├── routes/         # Rotas modularizadas (clips, thumbnails, processamento)
│   ├── services/       # Fila de trabalhos assíncrona (job queue) e workers
│   └── requirements.txt
├── frontend/           # Interface web em React + Vite + TailwindCSS
├── remotion/           # Composição e renderização de vídeo programática
├── render-service/     # Microsserviço de renderização
├── docker-compose.yml  # Orquestração de containers para produção/desenvolvimento
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

---

## Executando o Projeto

### Opção 1: Via Docker Compose (Recomendado para Produção)

Para subir todos os serviços (backend, frontend e renderer):

```bash
docker compose up --build
```

- **Frontend**: `http://localhost:5175`
- **Backend API**: `http://localhost:8000`
- **Documentação Swagger**: `http://localhost:8000/docs`

### Opção 2: Desenvolvimento Local

Para rodar o backend e o frontend simultaneamente:

```bash
npm run dev
```

Ou execute individualmente em terminais separados:

```bash
# Terminal 1 - Backend (FastAPI)
npm run dev:backend
# ou: uvicorn app:app --app-dir backend --port 8000 --reload

# Terminal 2 - Frontend (Vite)
npm run dev:frontend
# ou: npm --prefix frontend run dev
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
