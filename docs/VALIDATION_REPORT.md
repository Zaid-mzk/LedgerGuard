# Validation report

## Initial delivery validation report

Date: 2026-10-24

This section preserves the original source-package validation snapshot.

### Checks performed
- Python `compileall` for `app`, `scripts`, and `tests`: passed in the available Python 3.13.5 runtime.
- Backend pytest smoke/API suite: 5 passed using isolated in-memory SQLite; selected health/auth/transfer/idempotency/validation paths only.
- ZIP archive integrity: passed with `unzip -t` after packaging.

### Checks not completed at initial delivery
- `npm install` timed out because the environment could not resolve the npm registry; frontend build and ESLint had not been verified then.
- A clean installation of the pinned Python requirements was not performed in that environment.
- PostgreSQL was unavailable there; migration execution, PostgreSQL integration, rollback/failure injection, and concurrent overspending tests were unverified then.
- Hosting account configuration, billing state, and live deployment had not been checked. Deployment had not been attempted.

These were limitations of the initial delivery environment, not passing checks.

## Subsequent local validation

Date: 2026-10-26

### Checks passed
- Ruff: `python -m ruff check .\backend\app .\backend\tests .\backend\scripts` â€” all checks passed after formatting and safe lint fixes in the scripts.
- Ruff formatting: `python -m ruff format --check .\backend\app .\backend\tests` â€” 23 files already formatted.
- Backend tests: `python -m pytest .\backend\tests -v` â€” **17 passed, 1 skipped**.
- PostgreSQL concurrency test: separately enabled and run against local PostgreSQL â€” **1 passed**. It is skipped in the regular suite unless explicitly enabled.
- Frontend ESLint: `npm run lint` â€” passed.
- Frontend production build: `npm run build` â€” passed.
- Alembic migration applied successfully to local PostgreSQL.
- Demo seed script executed successfully against the local development database.
- `git check-ignore -v backend/.env frontend/.env` confirmed both local `.env` files are ignored.

### Warnings and limitations
- Python 3.13.7 prints `Could not find platform independent libraries <prefix>` in this local environment. The checks above still completed; the warning has not been diagnosed here.
- The regular pytest run reports a Starlette/AnyIO `BlockingPortal` deprecation warning.
- The concurrency test passed, but comprehensive rollback/failure-injection coverage is not confirmed as complete.
- Dedicated reversal/concurrent-reversal tests, broader reconciliation scenario coverage, frontend interaction/state review, and additional metric documentation remain outstanding.
- GitHub Actions has not been verified on GitHub because the repository has not yet been pushed.
- No live deployment has been performed or verified.

## Interpretation
These results support that the listed local development checks pass. They do not establish production readiness, real-world fraud-detection performance, or suitability for processing real financial transactions. LedgerGuard remains a synthetic-data educational portfolio project.
