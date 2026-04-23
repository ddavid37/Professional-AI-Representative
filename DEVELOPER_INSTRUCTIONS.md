# Developer Instructions (BE + FE)

This guide is split clearly by backend and frontend, with separate terminal tabs.

## 1) Prerequisites
- Node.js 18+
- Python 3.10+
- `npm` and `pip`

## 2) One-time setup

From repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

From `frontend/`:

```bash
npm install
```

## 3) Environment variables (`/.env`)

Keep one root `.env` with BE and FE vars:

```env
# Backend (private)
OPENAI_API_KEY=your_real_openai_key
OPENAI_MODEL=gpt-4o-mini
SENDGRID_API_KEY=
EMAIL_FROM=
EMAIL_TO=

# Frontend (public)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Rules:
- Never commit `.env`.
- Never put secrets in `NEXT_PUBLIC_*`.

---

## 4) Local run with 2 terminal tabs

## Terminal A - Backend (BE)

Working directory: repo root

```bash
source .venv/bin/activate
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Backend verification:

```bash
curl http://localhost:8000/healthz
```

Expected:

```json
{"status":"ok"}
```

## Terminal B - Frontend (FE)

Working directory: `frontend/`

```bash
cd frontend
npm run dev
```

Frontend URLs:
- `http://localhost:3000`
- `http://localhost:3000/chat`

---

## 5) Restart rules (important)

- Changed backend code or backend env (`OPENAI_*`, `SENDGRID_*`, `EMAIL_*`)
  - Restart **Terminal A (BE)**.

- Changed frontend code
  - `npm run dev` hot-reloads automatically.

- Changed frontend env (`NEXT_PUBLIC_*`)
  - Restart **Terminal B (FE)**.

---

## 6) Troubleshooting by terminal

### Backend (Terminal A) issues
- `uvicorn: command not found`
  - You are not in venv. Run:
  - `source .venv/bin/activate`
  - then run `python -m uvicorn ...`

- `address already in use` on `:8000`
  - Another BE process is running.
  - Stop it:
  - `lsof -ti :8000 | xargs kill`

- Chat returns `Connection error`
  - Check `curl http://localhost:8000/healthz`
  - Verify `OPENAI_API_KEY`
  - Check OpenAI quota/billing (429 insufficient_quota)

### Frontend (Terminal B) issues
- `npm: command not found`
  - Install Node.js / npm.

- Wrong backend target
  - Check `NEXT_PUBLIC_API_URL` in root `.env`
  - Restart FE terminal after changing it.

---

## 7) Deployment (Vercel FE + separate BE)

Deploy in this exact order.

### Step 1 - Deploy Backend first
- Platform: Railway/Render/Fly/etc.
- Start command:

```bash
uvicorn backend.app:app --host 0.0.0.0 --port $PORT
```

- Set backend env vars:
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL` (optional)
  - `SENDGRID_API_KEY`, `EMAIL_FROM`, `EMAIL_TO` (optional)

- Verify:
  - `https://<your-backend-domain>/healthz`

### Step 2 - Deploy Frontend on Vercel
- Import repo in Vercel
- Set project root to `frontend`
- Add FE env var:

```env
NEXT_PUBLIC_API_URL=https://<your-backend-domain>
```

- Deploy and test:
  - `https://<your-vercel-domain>/chat`

Notes:
- Changing BE env vars => restart/redeploy backend.
- Changing `NEXT_PUBLIC_*` vars => redeploy/restart frontend.
