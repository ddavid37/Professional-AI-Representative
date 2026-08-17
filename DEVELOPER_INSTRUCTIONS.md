# Developer Instructions (BE + FE)

This guide covers local development and production deployment for the current stack: **FastAPI + LangGraph backend** and **Next.js frontend**.

## 1) Prerequisites

- Node.js 18+
- Python 3.10+
- `npm` and `pip`
- OpenAI API key
- Twilio account with WhatsApp sandbox (or business number) for lead notifications
- Tavily API key for web search (optional locally; required for internet retrieval)

## 2) One-time setup

From repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

From `frontend/`:

```bash
npm install
cp .env.local.example .env.local   # optional; or use root .env for NEXT_PUBLIC_*
```

## 3) Environment variables

Keep secrets in a root `.env` file (gitignored):

```env
# Backend (private)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Twilio WhatsApp — required for lead notifications
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+972XXXXXXXXX

# Tavily web search — public / current facts
TAVILY_API_KEY=tvly-...

# Frontend (public — baked in at build time on Vercel)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Rules:
- Never commit `.env`.
- Never put secrets in `NEXT_PUBLIC_*`.
- Changing `NEXT_PUBLIC_*` on Vercel requires a **frontend redeploy**.

---

## 4) Local run (2 terminal tabs)

### Terminal A — Backend

Working directory: repo root

```bash
source .venv/bin/activate
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/healthz
# {"status":"ok"}
```

Test WhatsApp (optional):

```bash
curl -X POST http://localhost:8000/api/test/whatsapp
```

### Terminal B — Frontend

Working directory: `frontend/`

```bash
npm run dev
```

URLs:
- `http://localhost:3000` — home
- `http://localhost:3000/chat` — AI chat
- `http://localhost:3000/resume` — CV viewer
- `http://localhost:3000/contact` — contact form

---

## 5) Restart rules

| Change | Action |
|--------|--------|
| Backend code or `OPENAI_*` / `TWILIO_*` / `TAVILY_*` env | Restart Terminal A |
| Frontend code | Hot-reloads automatically |
| `NEXT_PUBLIC_*` env | Restart Terminal B (local) or redeploy frontend (Vercel) |
| Files in `knowledge/` | Restart backend (content loaded at startup; audit runs automatically) |

Knowledge changes are tracked in `knowledge/.audit/` (`state.json` + append-only `events.jsonl`). Version snapshots live in `knowledge/.audit/versions/` (gitignored). Inspect via `GET /api/knowledge/audit` or trigger `POST /api/knowledge/reload`.

### Developer panel (`/dev`)

Unlisted UI at `http://localhost:3000/dev` (not in public nav). Shows env var names (configured/missing), local + Vercel health, knowledge sources, and full audit log.

- Set `DEV_PANEL_SECRET` on the **API** project (required in production).
- Optional on **frontend** for Vercel health tiles: `NEXT_PUBLIC_PRODUCTION_API_URL`, `NEXT_PUBLIC_PRODUCTION_FRONTEND_URL`.
- Unlock once per browser session; secret is sent as `X-Dev-Panel-Secret` header.

---

## 6) Troubleshooting

### Backend

- **`uvicorn: command not found`** — Activate venv: `source .venv/bin/activate`
- **`address already in use` on :8000** — `lsof -ti :8000 | xargs kill`
- **Chat errors / 500** — Check `OPENAI_API_KEY` and OpenAI billing/quota
- **WhatsApp not sending** — Verify all four `TWILIO_*` vars; test with `/api/test/whatsapp`
- **Web search fails** — Verify `TAVILY_API_KEY` (no spaces around `=`)
- **Agent gives stale bio** — Restart backend after updating `knowledge/` files

### Frontend

- **Wrong backend** — Check `NEXT_PUBLIC_API_URL` points to running backend
- **Chat loops on lead capture** — Clear `daniel_ai_chat_history` in browser localStorage or use "New chat"
- **Resume 404** — Ensure `knowledge/Daniel_David_CV_May_2026_Har.pdf` exists

---

## 7) Deployment (Vercel)

Use **two separate Vercel projects** from the same GitHub repo.

### Project 1 — Backend API

- **Root directory:** `.` (repo root)
- **Framework:** Other (Python via `api/index.py` + root `vercel.json`)
- **Env vars:** `OPENAI_API_KEY`, `OPENAI_MODEL`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TWILIO_WHATSAPP_TO`, `TAVILY_API_KEY`, `DEV_PANEL_SECRET`
- **Verify:** `https://<api-domain>/healthz`

Example production API: `https://professional-ai-representative-api.vercel.app`

### Project 2 — Frontend

- **Root directory:** `frontend`
- **Framework:** Next.js
- **Env vars:** `NEXT_PUBLIC_API_URL=https://<api-domain-from-step-1>`; optional `NEXT_PUBLIC_PRODUCTION_API_URL`, `NEXT_PUBLIC_PRODUCTION_FRONTEND_URL` for `/dev` health tiles
- **Verify:** `https://<frontend-domain>/chat`

Example production frontend: `https://professional-ai-representative.vercel.app`

Notes:
- Backend env changes → redeploy API project
- `NEXT_PUBLIC_*` changes → redeploy frontend project (rebuild required)
- `knowledge/` changes → redeploy API project so the agent loads new content

---

## 8) Architecture summary

```
Browser → Next.js (frontend/) → FastAPI (backend/app.py)
                                    ↓
                              LangGraph agent (backend/agent.py)
                                    ↓
                         knowledge/ + OpenAI gpt-4o-mini
                                    ↓
                         Tavily (public / current facts)
                         Twilio WhatsApp (unknown Daniel facts)
```

Lead capture flow:
1. User asks something not in knowledge → if it is public/current, agent calls `search_web` (Tavily)
2. If it is personal/unknown about Daniel → agent asks for name + email
3. User provides contact info → `_maybe_whatsapp_reply` in `app.py` sends WhatsApp immediately when full conversation history is present
4. Agent tool `notify_daniel_on_whatsapp` is a fallback for the same path

---

## 9) Legacy `custom/` path (optional)

Not used in production. Requires Azure OpenAI + SendGrid env vars:

```bash
python custom/main.py          # terminal chat
python custom/app_gradio.py    # Gradio UI
```

See `custom/` for the original OpenAI Agents SDK implementation.
