# Windows setup quick reference

See the root README for the full clean-clone walkthrough. Required local ports: PostgreSQL 5432, FastAPI 8000, Vite 5173.

PowerShell execution policy may block virtual environment activation. If so, for the current terminal only run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, or use `.venv\Scriptsctivate.bat` in Command Prompt.

Common fixes:
- `could not connect to server`: start Docker Desktop and run `docker compose up -d postgres`; check port 5432.
- `password authentication failed`: compare `DATABASE_URL` with Docker Compose credentials and recreate local DB only if you understand data loss.
- `alembic` not found: activate `.venv` and install `requirements.txt`.
- CORS error: ensure `FRONTEND_ORIGIN=http://localhost:5173` and restart API after `.env` changes.
- API unreachable: start backend and confirm `/health` returns `{"status":"ok"}`.
- npm command fails: install Node.js 22, reopen terminal and run `npm install` in `frontend/`.
