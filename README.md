# LedgerGuard - Payment Integrity & AI Risk Monitor

> **Synthetic demo only.** Educational portfolio simulation; it does not move real money, connect to banks/payment providers, store real customer financial data, or claim production fraud-detection readiness.

LedgerGuard demonstrates backend integrity patterns beyond basic CRUD: idempotent transfer retries, double-entry ledger entries, transactional balance updates, synthetic provider reconciliation, audit events, explainable rule-based risk flags, and an offline synthetic-data Isolation Forest experiment.

## Features
- React/Vite dashboard with API-backed metrics.
- FastAPI REST API, Pydantic validation, Argon2 password hashing, and JWT authentication.
- PostgreSQL persistence with SQLAlchemy and Alembic migrations.
- Idempotent transfers; same key and payload return the original result, while a changed payload returns a conflict.
- Decimal-safe INR amounts and paired debit/credit ledger entries.
- Role-gated synthetic provider batches, reconciliation discrepancies, and audited reviews.
- Rule-based risk flags, human review, and offline model evaluation.
- Demo seed script, pytest suite, Ruff checks, and GitHub Actions CI workflow.

## Architecture
```mermaid
flowchart LR
  Browser[React + Vite] -->|JSON + JWT| API[FastAPI]
  API --> Services[Transfer / reconciliation / risk services]
  Services --> ORM[SQLAlchemy]
  ORM --> DB[(PostgreSQL)]
  Services --> Audit[Audit events]
  ML[Offline synthetic data + model training] --> Artifacts[Local evaluation JSON / model]
```

## Prerequisites
- Python 3.12 recommended (local checks have also run with Python 3.13.7).
- Node.js 22 and npm.
- Docker Desktop with Compose, or local PostgreSQL 16.
- Git and VS Code recommended.

## Windows quick start (PowerShell)
Run commands from the repository root unless specified.

### 1. Start PostgreSQL
With Docker Desktop running:
```powershell
docker compose up -d postgres
```
This starts the local `ledgerguard` database on port 5432. If using another PostgreSQL server, create a database and update `backend/.env`.

### 2. Set up the backend
```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `backend/.env` and set a strong, unique `JWT_SECRET`. The sample database URL matches the local Compose database. Never commit `.env` files or real secrets.

### 3. Apply migrations and seed synthetic demo accounts
From `backend`:
```powershell
alembic upgrade head
python scripts/seed_demo.py
```
The first seed prints generated admin, analyst, and customer passwords once. Store them securely for local testing; never share them or expose a seeded admin account publicly.

### 4. Start the API
Still in `backend`:
```powershell
uvicorn app.main:app --reload
```
Health: `http://localhost:8000/health` Â· API docs: `http://localhost:8000/docs`

### 5. Start the frontend
Open a second terminal at the repository root:
```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```
Open `http://localhost:5173`. The frontend API URL should be `http://localhost:8000` to match the local origin/auth configuration.

## Tests and quality checks

### Backend
Run from the repository root with the backend virtual environment active:
```powershell
python -m ruff check .\backend\app .\backend\tests .\backend\scripts
python -m ruff format --check .\backend\app .\backend\tests
python -m pytest .\backend\tests -v
```
Latest regular local suite: **17 passed, 1 skipped**. The skipped test is the opt-in PostgreSQL concurrency test, which also passed when run separately against local PostgreSQL. See `docs/VALIDATION_REPORT.md`.

### Frontend
Run from `frontend`:
```powershell
npm run lint
npm run build
```
Both passed in the latest local verification.

### PostgreSQL concurrency test
With local PostgreSQL running, from the repository root:
```powershell
$env:DATABASE_URL = "postgresql+psycopg://ledgerguard:ledgerguard@localhost:5432/ledgerguard"
$env:RUN_POSTGRES_CONCURRENCY = "1"
python -m pytest .\backend\tests\test_postgres_concurrency.py -v -s
Remove-Item Env:DATABASE_URL
Remove-Item Env:RUN_POSTGRES_CONCURRENCY
```
Adjust the database URL for your own local setup. Do not publish secrets.

### Offline synthetic model experiment
Run from `backend`:
```powershell
python scripts/generate_synthetic_transactions.py --rows 5000 --seed 42
python scripts/train_risk_model.py
```
Outputs are written under `backend/artifacts/`. Review generated data/model/evaluation files before intentionally publishing them. Synthetic metrics are not evidence of real-world fraud-detection accuracy.

## API overview
- `POST /api/v1/auth/login`, `GET /api/v1/auth/me`
- `GET /api/v1/metrics/summary`, `GET /api/v1/accounts`, `GET /api/v1/accounts/{id}/ledger`
- `POST /api/v1/transfers` (requires `Idempotency-Key`), `GET /api/v1/transfers`, `GET /api/v1/transfers/{id}`, `POST /api/v1/transfers/{id}/reverse` (admin/analyst)
- `GET /api/v1/ledger`, `GET /api/v1/audit`
- `POST /api/v1/reconciliation/simulate-provider-batch` (admin), `POST /api/v1/reconciliation/run`, `GET /api/v1/reconciliation/discrepancies`, `PATCH /api/v1/reconciliation/discrepancies/{id}`
- `POST /api/v1/risk/analyze`, `GET /api/v1/risk/flags`, `PATCH /api/v1/risk/flags/{id}`, `GET /api/v1/risk/model-evaluation`

## Security notes and limitations
- Synthetic records only; there is no real bank, card, or payment-provider integration.
- Use a strong random JWT secret and exact allowed frontend origin for deployment.
- This is a portfolio project, not production financial software. Broader reversal/concurrent-reversal tests, additional reconciliation scenarios, frontend filtering/pagination and UI-state review, and a formal threat-model review remain outstanding.
- Deployment has not been completed or verified. Recheck hosting terms, quotas, and billing before deployment.

## Deployment
Deployment is deferred until local review and acceptance checks are complete. See `docs/DEPLOYMENT.md` for the planned approach. No live deployment URL is claimed.

## Project documentation
`docs/ARCHITECTURE.md` Â· `docs/API.md` Â· `docs/SECURITY.md` Â· `docs/ML_EVALUATION.md` Â· `docs/METRICS.md` Â· `docs/DEPLOYMENT.md` Â· `docs/DECISIONS.md` Â· `docs/WINDOWS_SETUP.md` Â· `docs/PROGRESS_CHECKLIST.md` Â· `docs/VALIDATION_REPORT.md`

## Interview explanation
â€œI built LedgerGuard to explore backend integrity problems beyond basic CRUD. It simulates transfers where retries should not duplicate a transfer, debit and credit ledger entries should balance, and internal records can be reconciled against synthetic provider records. Transparent rules and an offline anomaly-model experiment surface unusual activity for human review. It focuses on integrity and explainability; it does not process real money.â€
