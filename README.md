# Hospital Flow Agent

Full-stack hospital **operations** management: bed allocation, patient flow, resource inventory, departments,
routing recommendations, transfers, discharges, persistent alerts, audit logging, and an optional AI Operations Assistant.

> **Not a clinical system.** It manages capacity and logistics. It does not diagnose, prescribe or make emergency
> clinical decisions. All demo patients are synthetic. See [Production readiness](#production-readiness).

## Verification status (read this first)

This codebase was generated in a sandbox **without network access**, so dependencies could not be installed. What was and was not verified:

| Item | Status |
|---|---|
| Python syntax of all backend files (`compileall`) | Checked, passes |
| TypeScript **syntax** of all frontend files (global `tsc`) | Checked, no syntax errors |
| Backend unit/API tests (`pytest`) | **Written, NOT run** |
| Alembic migration | **Written, NOT run** |
| Seed script | **Written, NOT run** |
| Frontend type-check and `vite build` | **NOT run** |
| LangGraph / LLM providers / MCP | LangGraph path and LLM adapters are **implemented but unverified**; MCP/A2A are **not implemented** (optional per spec) |

Expect a first-run fix-up pass: run the tests, then fix whatever fails. Commands are below.

## Architecture

```
hospital-flow-agent/
├── backend/                 FastAPI app (layered)
│   ├── app/
│   │   ├── api/v1/          thin route handlers (auth, patients, beds, ... ws)
│   │   ├── core/            config, security (bcrypt + JWT), permissions (RBAC), error handling
│   │   ├── db/              engine/session, UTC datetime type
│   │   ├── models/          SQLAlchemy 2.x models, constraints, partial unique indexes
│   │   ├── schemas/         Pydantic request/response models
│   │   ├── repositories/    query building + pagination
│   │   ├── services/        ALL business rules and transactions
│   │   ├── ai/              read-only tools, workflows (LangGraph or sequential), LLM adapter
│   │   ├── live/            WebSocket manager (publishes only after DB commit)
│   │   ├── seed.py, cli.py  synthetic data; create-admin
│   │   └── main.py
│   ├── alembic/             migrations
│   └── tests/               pytest suite (isolated temp SQLite DB)
├── frontend/                React + TS + Vite + Tailwind + shadcn-style components
│   └── src/{api,components,hooks,layouts,pages,types,lib}
├── docs/
├── docker-compose.yml
└── README.md
```

Key design decisions:

* **Services own the rules.** Routes only authenticate, validate and call a service. Services do not hide commits: each public operation is one DB transaction covering the business change, its **audit row** and its **notifications**, so they succeed or fail together.
* **Concurrency safety is enforced by the database**, not only by checks: partial unique indexes allow only one *active* assignment per bed and per patient, one open transfer / discharge per patient, and one *unresolved* notification per dedup key. Stock changes use a guarded atomic `UPDATE ... WHERE quantity >= :n`.
* **Notifications come from business events** (bed assigned, capacity thresholds, stock thresholds, workflow transitions, AI failures) and carry an `event_key` (idempotency) and optional `dedup_key` (one open alert per condition). Descriptions use internal patient codes, never names.
* **Read ≠ resolved.** Read/unread, acknowledge and resolve are separate states. Resolving closes the alert record only; the next related event re-evaluates the condition.
* **Live updates:** WebSocket sends tiny change signals after commit; the UI re-fetches through the authorised REST API. All queries also poll (15–30 s) as a reliable fallback.
* **AI is optional and read-only.** Facts (from DB tools) are kept separate from deterministic recommendations and from any LLM narrative, and the UI labels each. Without credentials everything still works.

## Local setup

Prerequisites: Python 3.11+, Node 20+.

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
# generate a secret and put it in .env as SECRET_KEY:
python -c "import secrets; print(secrets.token_urlsafe(64))"

alembic upgrade head                 # create the schema
python -m app.seed                   # synthetic demo data + demo users (prints a generated password once)
uvicorn app.main:app --reload        # http://localhost:8000  (Swagger: /docs)
```
If `SEED_USER_PASSWORD` is empty, the seed script generates a random password and prints it **once**.
Demo users: `admin@`, `ops@`, `dept@`, `viewer@` `demo.hospital`.

**Creating the first administrator (no seed data):**
```bash
python -m app.cli create-admin --email you@example.org --name "Your Name"   # prompts for the password
```

### Frontend
```bash
cd frontend
cp .env.example .env
npm install
npm run dev                          # http://localhost:5173
```

### Tests
```bash
cd backend && pytest -v
cd frontend && npm run typecheck && npm run build
```

### Docker
```bash
echo "SECRET_KEY=$(python -c 'import secrets;print(secrets.token_urlsafe(64))')" > .env
docker compose up --build            # UI http://localhost:8080 · API http://localhost:8000/docs
docker compose exec backend python -m app.seed     # optional demo data
```

## Roles & permissions

| Role | Summary |
|---|---|
| Administrator | everything, including users, settings, audit logs |
| Hospital operations staff | all operational actions and approvals, AI assistant; no users/settings/audit |
| Department staff | read all; register/admit patients, assign beds, stock movements, **request** transfers/discharges, manage alerts; cannot approve |
| Read-only viewer | read access and notifications (view only) |

Permissions live in `backend/app/core/permissions.py` and are enforced per route. The frontend hides actions the role lacks, but that is UX only.
Department staff are **not** yet restricted to their own department's records (known limitation).

## API

Versioned under `/api/v1`; interactive docs at `/docs`, schema at `/openapi.json`. Errors share one shape:
`{"error": {"code": "...", "message": "...", "details": ...}}`. Stack traces are never returned.
Health: `GET /api/v1/health`, readiness: `GET /api/v1/ready`. Live notifications: `ws://host/api/v1/ws/notifications?token=<jwt>`.

## AI Operations Assistant

Workflows: operations summary, bed availability, capacity constraints, low stock, pending transfers/discharges, alert prioritisation, bottlenecks, routing explanation, plus a free-text box mapped to a workflow by keyword.
LangGraph runs `gather_facts → rule_based_analysis → [llm_narrative] → validate_output` when installed; otherwise an equivalent sequential runner is used. Configure a provider in `backend/.env` (`LLM_PROVIDER=anthropic|openai`, `LLM_API_KEY`, `LLM_MODEL`). Every run is stored in `ai_workflow_executions`, including failures. The assistant has **no write tools**; consequential actions go through normal, permission-checked endpoints with human confirmation (e.g. routing *confirm*, then transfer *approve*).
MCP and A2A integration are **not implemented** (optional; `MCP_SERVER_URL` is a reserved placeholder).

## Deployment guidance

* Set `ENVIRONMENT=production` (the app refuses to start without `SECRET_KEY`, and demo seeding is disabled).
* Use PostgreSQL (`DATABASE_URL=postgresql+psycopg://...`); SQLite is for development. Run `alembic upgrade head` on release.
* Terminate TLS in front of both apps; restrict `CORS_ORIGINS` to your real frontend origin(s); serve the API and UI over HTTPS so `wss://` works.
* The JWT is kept in `localStorage` for simplicity; for production consider httpOnly cookies + CSRF protection and a strict CSP.
* Add login rate limiting / lockout (not implemented), centralised logging, backups and monitoring.
* Rotate `SECRET_KEY` deliberately (it invalidates all sessions).

## Production readiness

Using this in a real hospital requires, at minimum: privacy and data-protection assessment (e.g. HIPAA/GDPR as applicable), security review and penetration testing, clinical governance sign-off, access reviews, encrypted backups and tested restores, retention policies for audit logs, incident response, and operational validation. This repository is a starting point, not a certified product.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `RuntimeError: SECRET_KEY must be set` | Set `SECRET_KEY` in `backend/.env` (required when `ENVIRONMENT=production`) |
| Everyone is signed out after restart in dev | No `SECRET_KEY` set; an ephemeral key is generated each start |
| Browser CORS error | Add the frontend origin to `CORS_ORIGINS` |
| `503 database_busy` on SQLite | Write contention; retry. Use PostgreSQL for concurrent use |
| Frontend cannot reach API | Check `VITE_API_URL`; backend must be running on that URL |
| `alembic` can't import `app` | Run it from the `backend/` directory |
| Live updates not appearing | WebSocket blocked by a proxy; the UI still refreshes by polling |
