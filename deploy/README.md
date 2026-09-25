# Deploying ProBee on a VPS (no reverse proxy)

The FastAPI backend is the **only** public process. It serves everything on one port:

| Route | What |
|---|---|
| `/` | React chatbot (public — embed this in other sites via `<iframe src="https://your-domain/">`) |
| `/admin/*` | React admin SPA (token-gated UI; API still enforces `ADMIN_TOKEN`) |
| `/api/*` | JSON API (`/api/chat`, `/api/admin/...`, …; interactive docs at `/docs`) |
| `/health` | Health check |

No nginx: point your domain (or Cloudflare proxy) straight at the VPS on port 8000.

## 0. Before you start
- [ ] A Groq API key (https://console.groq.com/keys)
- [ ] Your MySQL tender dump (`mysqldump probid > probid.sql`) if migrating the tender DB
- [ ] Postgres with the **pgvector** extension available for `backend/db/schema.sql`

## 1. Create the VM
Any Ubuntu 22.04/24.04 VM with 4 vCPU / 8 GB+ RAM (embeddings + reranker run on CPU).
Open port **8000** (and 22 for SSH) to the world.

## 2. Upload the project (skip envs/caches)
```powershell
tar -a -c -f probee.zip --exclude=venv --exclude=node_modules --exclude=models --exclude=dist --exclude=__pycache__ .
scp -i keyfile.pem probee.zip ubuntu@<PUBLIC-IP>:~
ssh -i keyfile.pem ubuntu@<PUBLIC-IP> "sudo mkdir -p /opt/probee && sudo tar -xf probee.zip -C /opt/probee && sudo chown -R ubuntu:ubuntu /opt/probee"
```

## 3. Configure + bootstrap
```bash
ssh -i keyfile.pem ubuntu@<PUBLIC-IP>
cd /opt/probee
cp backend/.env.example backend/.env
nano backend/.env     # set: DATABASE_URL, LLM_API_KEY, ADMIN_TOKEN,
                      #      REDIS_URL, MYSQL_* creds, CORS_ORIGINS=https://your-domain.com
bash deploy/setup-vm.sh /opt/probee
```
The script installs system packages, creates the venv, installs requirements
(CPU torch), builds the frontend (`npm ci && npm run build` → chatbot at `/`,
admin at `/admin`), applies nothing automatically to the DBs (see step 4),
and starts uvicorn on :8000. First boot downloads the ML models (~2 GB).

## 4. Load your data into the fresh DBs
```bash
# Postgres schema (once):
sudo -u postgres psql -d ragdb -f backend/db/schema.sql
# MySQL tenders:
mysql -uroot -p probid < probid.sql
# RAG documents: upload via the admin UI (/admin → Documents) or POST /api/ingest
```

## 5. Verify
- `http://<PUBLIC-IP>:8000/health` → `{"status":"ok",...}`
- `http://<PUBLIC-IP>:8000/` → chatbot UI (React)
- `http://<PUBLIC-IP>:8000/admin` → admin login (token from `backend/.env`)
- Ask it a tender question like `how many construction tenders are in Gujarat?`

## 6. HTTPS via Cloudflare (free)
1. Point a domain at the VM (A record), proxy through Cloudflare (orange cloud).
2. Set `CORS_ORIGINS=https://your-domain.com` in `backend/.env` and restart the backend.
3. Embed the chatbot anywhere: `<iframe src="https://your-domain/" width="400" height="620"></iframe>`

---
## Troubleshooting
| Problem | Command |
|---|---|
| API not healthy | `tail -100 /tmp/probee-backend.log` |
| Tender query returns "database unavailable" | check `MYSQL_*` in `backend/.env`, then `tail /tmp/probee-backend.log \| grep -i tender` |
| `/` shows API JSON instead of chatbot | `frontend/dist` missing → rerun `npm run build` in `frontend/` and restart backend |
| Rebuild after code change | backend: restart uvicorn · frontend: `npm run build` + restart backend |
