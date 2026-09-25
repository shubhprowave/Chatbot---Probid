# Railway + Vercel Deployment Guide

This guide covers deploying the ProBee chatbot:
- **Backend (FastAPI)** → Railway
- **Frontend (React + Vite)** → Vercel

---

## 📋 Prerequisites

- GitHub account (repo: `shubhprowave/Chatbot---Probid`)
- Railway account (railway.app)
- Vercel account (vercel.com)
- External databases:
  - PostgreSQL with pgvector (e.g., Neon, Supabase, Railway PostgreSQL)
  - MySQL for tenders (e.g., PlanetScale, Railway MySQL, external)
  - Redis (e.g., Upstash, Railway Redis, Redis Cloud)

---

## 🚂 Railway Backend Deployment

### 1. Create Railway Project

1. Go to [railway.app](https://railway.app) → New Project
2. Select "Deploy from GitHub repo" → `shubhprowave/Chatbot---Probid`
3. Railway will auto-detect the `Dockerfile` in `backend/`

### 2. Add Database Services

In Railway project, click **New** → **Database** and add:
- **PostgreSQL** (with pgvector extension)
- **Redis**
- **MySQL** (for tender data)

Or use external providers and skip this step.

### 3. Configure Environment Variables

In Railway → Variables tab, add:

```bash
# PostgreSQL (from Railway PostgreSQL service or external)
POSTGRES_URL=postgresql+asyncpg://user:pass@host:5432/ragdb

# MySQL (from Railway MySQL service or external)
MYSQL_HOST=your-mysql-host
MYSQL_PORT=3306
MYSQL_USER=your-user
MYSQL_PASSWORD=your-pass
MYSQL_DB=probid

# Redis (from Railway Redis service or external)
REDIS_URL=redis://user:pass@host:6379/0

# Groq LLM (get free key at console.groq.com)
GROQ_API_KEY=gsk_xxxxxxxxxxxx
LLM_MODEL=qwen/qwen3-8b-27b
LLM_BASE_URL=https://api.groq.com/openai/v1

# Embeddings & Reranker (local CPU models)
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-base
TOP_K_RETRIEVE=20
TOP_K_RERANK=4

# Auth
ADMIN_TOKEN=your-secure-random-token-here

# CORS - ADD YOUR VERCEL URL HERE
CORS_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com

# HF Cache (Railway persistent volume path)
HF_HOME=/app/models
TRANSFORMERS_CACHE=/app/models
```

### 4. Configure PostgreSQL (pgvector)

Connect to your PostgreSQL and run:

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Run the schema
\i backend/db/schema.sql
```

### 5. Configure MySQL (Tender DB)

Import your tender data and create the view:

```sql
-- Assuming you have live_tenders and fresh_tenders tables
CREATE OR REPLACE VIEW all_tenders AS
SELECT * FROM live_tenders
UNION ALL
SELECT * FROM fresh_tenders;
```

### 6. Deploy

Railway will build and deploy automatically. Note your backend URL:
```
https://your-app-name.up.railway.app
```

### 7. Verify Backend

Test these endpoints:
- `GET https://your-app.up.railway.app/health` → `{"status":"ok"}`
- `GET https://your-app.up.railway.app/docs` → Swagger UI
- `GET https://your-app.up.railway.app/` → Should serve frontend (after Vercel deploy)

---

## △ Vercel Frontend Deployment

### 1. Import Project

1. Go to [vercel.com](https://vercel.com) → Add New → Project
2. Import `shubhprowave/Chatbot---Probid`
3. Vercel detects Vite framework automatically

### 2. Configure Build Settings

| Setting | Value |
|---------|-------|
| Framework Preset | Vite |
| Build Command | `cd frontend && npm run build` |
| Output Directory | `frontend/dist` |
| Install Command | `cd frontend && npm ci` |
| Root Directory | (leave empty) |

### 3. Environment Variables

In Vercel → Settings → Environment Variables:

| Name | Value | Environment |
|------|-------|-------------|
| `VITE_API_URL` | `https://your-railway-backend.up.railway.app` | Production, Preview, Development |

### 4. Deploy

Click **Deploy**. Vercel will build and deploy. Your frontend URL:
```
https://your-app.vercel.app
```

### 5. Update Railway CORS

Go back to Railway → Variables and update:
```bash
CORS_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com
```
Redeploy backend (or wait for auto-redeploy).

---

## 🔗 Connect Frontend ↔ Backend

### API Proxy (Vercel Rewrites)

The `vercel.json` configures rewrites so frontend calls to `/api/*` proxy to Railway:

```json
"rewrites": [
  { "source": "/api/(.*)", "destination": "https://your-railway.up.railway.app/api/$1" },
  { "source": "/health", "destination": "https://your-railway.up.railway.app/health" }
]
```

**Update `vercel.json`** with your actual Railway URL before deploying.

### Iframe Embedding

Other sites can embed the chatbot:

```html
<iframe 
  src="https://your-app.vercel.app/" 
  width="400" 
  height="620" 
  style="border:none; border-radius:8px;"
  title="ProBee - ProBid Tender Assistant">
</iframe>
```

---

## 🔧 Post-Deployment Checklist

- [ ] Backend `/health` returns 200
- [ ] Backend `/docs` accessible
- [ ] Frontend loads at Vercel URL
- [ ] Chat widget sends messages → streams response
- [ ] Lead gate works (name + mobile)
- [ ] Admin console at `/admin` works with `ADMIN_TOKEN`
- [ ] Document upload works
- [ ] Tender queries return live data
- [ ] CORS allows Vercel domain
- [ ] Redis caching works (repeat questions instant)

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| CORS errors | Check `CORS_ORIGINS` in Railway includes Vercel URL exactly |
| "Failed to fetch" | Verify `VITE_API_URL` in Vercel matches Railway URL |
| Models not loading | Ensure `HF_HOME=/app/models` and volume persists |
| pgvector missing | Run `CREATE EXTENSION vector;` in PostgreSQL |
| MySQL connection failed | Check Railway MySQL service or external host allows Railway IPs |
| Build fails on Railway | Check Dockerfile uses correct Python version, check logs |
| Vercel build fails | Ensure `frontend/package.json` has correct build script |

---

## 💰 Cost Estimation

| Service | Free Tier | Paid Estimate |
|---------|-----------|---------------|
| Railway | $5/mo credit | ~$10-20/mo (CPU, RAM, DB) |
| Vercel | Unlimited personal | $20/mo (Pro) |
| PostgreSQL | Neon/Supabase free | $19-25/mo |
| MySQL | PlanetScale free | $29/mo |
| Redis | Upstash free | $10/mo |
| Groq LLM | Free tier (14k req/day) | Pay per token |

---

## 🔄 CI/CD (Optional)

### GitHub Actions for Auto-Deploy

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  railway:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: railwayapp/railway-deploy@v1
        with:
          token: ${{ secrets.RAILWAY_TOKEN }}
          service: your-backend-service

  vercel:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: ./frontend
```

---

## 📞 Support

- **Railway Docs**: docs.railway.app
- **Vercel Docs**: vercel.com/docs
- **Project Issues**: GitHub Issues tab