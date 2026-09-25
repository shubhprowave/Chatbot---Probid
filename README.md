# ProBee — AI Chatbot for ProBid Consultants LLP

A production-ready **RAG (Retrieval-Augmented Generation) chatbot** that answers questions about **government tenders, tender processes, and required documents** in **English, Hinglish (Roman-script Hindi), and Hindi (Devanagari)**. Grounded in company documents (PostgreSQL + pgvector) with live tender search via MySQL.

---

## 🎯 Key Features

| Feature | Description |
|---------|-------------|
| **Trilingual RAG** | Answers in English, Hinglish, and Hindi (Devanagari) with automatic language detection |
| **Document-Grounded Answers** | Every response cites sources from ingested company PDFs/DOCs/HTML/Markdown |
| **Live Tender Search** | Real-time queries against MySQL `probid` database (1.7L+ tenders via `all_tenders` view) |
| **Lead Capture** | Mandatory name + mobile gate before chat (stored in Postgres) |
| **Service Menus** | 10-service quick-access buttons with sub-question chips |
| **Admin Console** | Token-gated dashboard: docs, prompt tuning, conversations, evals, cost tracking, users |
| **Streaming SSE** | Token-by-token response streaming via `/api/chat` |
| **Exact-Match Cache** | Redis cache for repeat questions (sub-millisecond responses) |
| **Embeddable Widget** | React chatbot at `/` — iframe-ready for any website |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND (Port 8000)              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  /api/chat  │  │ /api/admin  │  │ /api/ingest │  ...        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         ▼                ▼                ▼                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    RAG PIPELINE                         │   │
│  │  Contact Short-Circuit → Greeting → Tender SQL → Hybrid │   │
│  │  Retrieval (Dense + Sparse + RRF) → Rerank → Generate   │   │
│  └─────────────────────────────────────────────────────────┘   │
│         │                │                │                     │
│    ┌────┴────┐      ┌────┴────┐      ┌────┴────┐               │
│    ▼         ▼      ▼         ▼      ▼         ▼               │
│ PostgreSQL  Redis   MySQL     Groq    BGE-M3    BGE-Reranker   │
│ (pgvector)  (Cache) (Tenders)  (LLM)   (Embed)   (CrossEnc)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (Served by Backend)                 │
│  ┌──────────────────┐         ┌──────────────────────────────┐  │
│  │  Chatbot at `/`  │         │  Admin at `/admin/*`         │  │
│  │  (ChatWidget)    │         │  (Overview, Docs, Prompt,    │  │
│  │  ChatbotDemo     │         │   Conversations, Users,      │  │
│  │                  │         │   Evaluations, Cost, Settings)│  │
│  └──────────────────┘         └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**No reverse proxy** — single uvicorn process serves API + chatbot + admin on port 8000. HTTPS via Cloudflare.

---

## 📁 Project Structure

```
.
├── backend/                     # FastAPI + RAG (Python 3.13)
│   ├── main.py                  # Entrypoint, routers, frontend hosting
│   ├── config.py                # Pydantic Settings (.env driven)
│   ├── models.py                # BGE-M3 embedder + BGE reranker (CPU)
│   ├── api/
│   │   ├── chat.py              # POST /api/chat (streaming SSE)
│   │   ├── admin.py             # /api/admin/* (token-guarded)
│   │   ├── ingest.py            # Document ingestion
│   │   ├── metrics.py           # Dashboard metrics
│   │   ├── feedback.py          # 👍/👎 on messages
│   │   ├── eval.py              # Golden Q&A eval runs
│   │   └── users.py             # Lead capture (name + phone)
│   ├── rag/
│   │   ├── pipeline.py          # Orchestrator with contact short-circuit
│   │   ├── retriever.py         # Hybrid dense + sparse + RRF
│   │   ├── reranker.py          # Cross-encoder rerank (top-4)
│   │   ├── generator.py         # Prompt + streaming + contact answers
│   │   ├── llm_client.py        # Groq OpenAI-compatible streaming
│   │   ├── router.py            # Query routing
│   │   └── query_rewrite.py     # Query normalization
│   ├── tenders/
│   │   ├── mysql.py             # Read-only MySQL + all_tenders view
│   │   └── text_to_sql.py       # NL→SQL for tender queries
│   ├── ingestion/
│   │   ├── loader.py            # PDF/DOCX/HTML/MD/TXT extraction
│   │   └── chunker.py           # Strategy-aware chunking
│   ├── db/
│   │   ├── postgres.py          # Async SQLAlchemy + asyncpg pool
│   │   ├── models.py            # ORM: Document, Chunk, Conversation, Message, Feedback, User, Eval
│   │   ├── schema.sql           # DDL with HNSW, GIN, pg_trgm indexes
│   │   └── redis_client.py      # Async Redis cache (rag:qa:* keys)
│   ├── analytics/               # SQL for metrics, cost, evals
│   ├── scripts/                 # benchmark, rebuild_embeddings
│   ├── .env                     # Local secrets (NOT committed)
│   └── requirements.txt
│
├── frontend/                    # React 18 + TS + Vite 5 (flat)
│   ├── src/
│   │   ├── App.tsx              # Routes: `/` (public) + `/admin/*` (token)
│   │   ├── components/
│   │   │   ├── ChatWidget.tsx   # Embeddable chatbot (SSE streaming)
│   │   │   ├── ChatWidget.css
│   │   │   ├── serviceMenus.ts  # 10 services + sub-questions
│   │   │   └── ... (charts, tables, modals, sidebar, icons)
│   │   ├── pages/
│   │   │   ├── ChatbotDemo.tsx  # Public full-page demo (iframe target)
│   │   │   ├── Overview.tsx
│   │   │   ├── Documents.tsx
│   │   │   ├── Prompt.tsx       # System prompt editor
│   │   │   ├── Conversations.tsx
│   │   │   ├── Users.tsx        # Leads
│   │   │   ├── Evaluations.tsx
│   │   │   ├── Cost.tsx
│   │   │   └── Settings.tsx
│   │   ├── api.ts               # Admin API calls (Bearer token)
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts           # Dev proxy /api → :8000
│
├── deploy/
│   ├── setup-vm.sh              # VPS provisioner (venv → build → uvicorn)
│   └── README.md                # VPS runbook + iframe embed snippet
│
├── PROJECT_DOCS.md              # Full technical documentation
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start (Local)

### Prerequisites
- **PostgreSQL 15+** with `pgvector`, `pg_trgm`, `uuid-ossp` extensions (database: `ragdb`)
- **MySQL 8+** (database: `probid` with `live_tenders`, `fresh_tenders` tables)
- **Redis 7+** (optional but recommended for caching)
- **Python 3.13** + **Node 20+**

### 1. Backend Setup
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your DB URLs, Groq API key, ADMIN_TOKEN, etc.
```

### 2. Frontend Setup
```powershell
cd frontend
npm ci
```

### 3. Run (Two Terminals)

**Terminal 1 — Backend:**
```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — Frontend Dev Server:**
```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

### 4. Access
| Surface | URL |
|---------|-----|
| **Chatbot (public)** | http://127.0.0.1:8000/ |
| **Admin Console** | http://127.0.0.1:8000/admin (token = `ADMIN_TOKEN` from `.env`) |
| **API Docs** | http://127.0.0.1:8000/docs |
| **Health Check** | http://127.0.0.1:8000/health |

---

## ⚙️ Configuration (`backend/.env`)

```ini
# Database
POSTGRES_URL=postgresql+asyncpg://user:pass@localhost:5432/ragdb
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=pass
MYSQL_DB=probid

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# LLM (Groq OpenAI-compatible)
GROQ_API_KEY=your_groq_key
LLM_MODEL=qwen/qwen3-8b-27b
LLM_BASE_URL=https://api.groq.com/openai/v1

# Embedding / Reranker (local CPU)
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-base

# Retrieval knobs
TOP_K_RETRIEVE=20
TOP_K_RERANK=4

# Auth / CORS
ADMIN_TOKEN=your-secure-random-token
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:8000

# HF Cache (Windows fix auto-detects ~/.cache/huggingface)
# HF_HOME=
# TRANSFORMERS_CACHE=
```

---

## 📡 API Endpoints

### Public
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Streaming chat (SSE) — requires `session_id` |
| `POST` | `/api/user/register` | Lead capture (name + 10-digit mobile) |
| `POST` | `/api/feedback` | 👍/👎 on a message |
| `GET` | `/health` | Health check |

### Admin (Bearer Token: `ADMIN_TOKEN`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/metrics/overview` | Dashboard stats |
| `GET` | `/api/admin/metrics/timeseries` | Time-series charts |
| `GET` | `/api/admin/metrics/latency` | Latency distribution |
| `GET` | `/api/admin/metrics/top-questions` | Top asked questions |
| `GET` | `/api/admin/metrics/unanswered` | Unanswered queries |
| `GET/POST` | `/api/admin/documents` | Document CRUD + upload |
| `POST` | `/api/admin/documents/upload` | Upload PDF/DOCX/HTML/MD/TXT |
| `POST` | `/api/admin/documents/{id}/reembed` | Re-embed document chunks |
| `GET` | `/api/admin/prompt` | Get current system prompt |
| `PUT` | `/api/admin/prompt` | Update system prompt (in-memory) |
| `POST` | `/api/admin/prompt/reset` | Reset to default |
| `GET` | `/api/admin/conversations` | List conversations |
| `GET` | `/api/admin/conversations/{id}` | Conversation detail |
| `GET` | `/api/admin/users` | List leads |
| `GET/POST` | `/api/admin/eval/golden` | Golden Q&A CRUD |
| `POST` | `/api/admin/eval/run` | Run evaluation |
| `GET` | `/api/admin/health` | System health |
| `GET` | `/api/admin/cost` | Token cost breakdown |

---

## 🔧 Key Technical Details

### RAG Pipeline Flow (`backend/rag/pipeline.py`)
1. **SQL Injection Guard** — rejects malicious queries
2. **Redis Exact-Match Cache** — instant return for repeated questions
3. **Contact Short-Circuit** — phone/email questions answered deterministically (no LLM)
4. **Greeting Fast-Path** — instant canned response for hellos
5. **Tender Intent Detection** — routes to MySQL text-to-SQL for live tender queries
6. **Hybrid Retrieval** — dense (pgvector HNSW) + sparse (BM25/pg_trgm) fused via RRF
7. **Cross-Encoder Rerank** — BGE reranker down to top-4 chunks
8. **Streaming Generation** — Groq Qwen 27B with trilingual system prompt

### Contact Handling (Fixed)
- System prompt includes `Mobile: +91 70166 28865` + `sales@probidconsultants.com`
- Rule 12: Contact questions **must** answer from prompt header (overrides retrieval rules)
- Typo-tolerant matchers: `moblie`, `mobail`, `contect`, `contact probi`, `मोबाइल नंबर`, etc.
- `CONTACT_LINES` footers appended to every answer in detected language

### Lead Gate
- ChatWidget requires **name + 10-digit mobile** before first message
- `POST /api/user/register` upserts on phone (idempotent)
- Stored in `sessionStorage` — persists across page reloads

---

## 🌐 Deployment (VPS)

### One-Command Provisioning
```bash
# On fresh Ubuntu 22.04+ VPS
curl -fsSL https://raw.githubusercontent.com/shubhprowave/Chatbot---Probid/main/deploy/setup-vm.sh | bash
```

### What `setup-vm.sh` Does
1. Installs system packages (Python 3.13, Node 20, PostgreSQL, Redis, MySQL client)
2. Creates Python venv + installs CPU torch + requirements
3. Runs `npm ci && npm run build` in `frontend/`
4. Starts single **uvicorn on port 8000** (serves API + chatbot + admin)
5. Configures systemd service for auto-restart

### Production URLs (after Cloudflare)
| Route | Purpose |
|-------|---------|
| `https://your-domain/` | Public chatbot (embed via iframe) |
| `https://your-domain/admin` | Admin console |
| `https://your-domain/api/*` | JSON API |
| `https://your-domain/health` | Health check |

### Iframe Embed (for client websites)
```html
<iframe 
  src="https://your-domain/" 
  width="400" 
  height="620" 
  style="border:none; border-radius:8px;"
  title="ProBee - ProBid Tender Assistant">
</iframe>
```

---

## 📊 Admin Dashboard Guide

1. **Login**: Visit `/admin`, enter `ADMIN_TOKEN` from `.env`
2. **Overview** — Real-time stats: conversations, messages, avg latency, cache hit rate
3. **Documents** — Upload PDFs/DOCX/HTML/MD/TXT; list with chunk counts; re-embed
4. **Prompt** — Live system prompt editor (changes apply instantly, in-memory)
5. **Conversations** — Browse all chats with message-level detail
6. **Users** — Leads captured via lead gate (name, phone, created_at)
6. **Evaluations** — Manage golden Q&A sets; run evals; track RAG quality
7. **Cost** — Token usage & estimated cost per day/model
8. **Settings** — System health, storage stats, configuration

> ⚠️ Prompt edits via dashboard are **in-memory only**. Restart backend to persist, or edit `backend/rag/generator.py::DEFAULT_SYSTEM_PROMPT` for permanence.

---

## 🧪 Testing & Quality

### Run Benchmark
```bash
cd backend
.\venv\Scripts\python.exe scripts/benchmark.py
```

### Rebuild All Embeddings
```bash
cd backend
.\venv\Scripts\python.exe scripts/rebuild_embeddings.py
```

### Run Evaluation
1. Add golden Q&A pairs in Admin → Evaluations
2. Click "Run Evaluation"
3. Results show retrieval accuracy, answer quality, latency

---

## 🛠 Troubleshooting

| Issue | Fix |
|-------|-----|
| Stale answers after prompt change | Clear Redis: `redis-cli KEYS "rag:qa:*" | xargs redis-cli DEL` |
| "Model not found" on startup | Ensure `HF_HOME`/`TRANSFORMERS_CACHE` set or models exist in `~/.cache/huggingface` |
| MySQL tender queries fail | Verify `probid` DB accessible, `all_tenders` view exists (`live_tenders ∪ fresh_tenders`) |
| Frontend not loading | Run `npm run build` in `frontend/`, restart backend |
| CORS errors | Add origin to `CORS_ORIGINS` in `.env`, restart backend |
| Port 8000 in use | `netstat -ano \| findstr :8000` → `taskkill /PID <pid> /F` |

---

## 📄 License

Proprietary — ProBid Consultants LLP. All rights reserved.

---

## 📞 Contact

**ProBid Consultants LLP**  
📧 sales@probidconsultants.com  
📞 +91 70166 28865  

---

*Built with FastAPI, PostgreSQL/pgvector, Redis, MySQL, React, Vite, BGE-M3, BGE-Reranker, Groq (Qwen 27B)*