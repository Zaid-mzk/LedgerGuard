# Build and validation checklist

Status updated 2026-10-26. See `VALIDATION_REPORT.md` for historical initial-delivery results and subsequent local checks.

## Implemented and checked
- [x] React/Vite app and responsive navigation for primary sections.
- [x] FastAPI health/docs and core demo API routes.
- [x] SQLAlchemy entities for users, accounts, transfers, ledger, audit, provider records, reconciliation, and risk flags.
- [x] Alembic migration applied successfully to local PostgreSQL.
- [x] Password hashing, JWT authentication, role guards, and CORS allowlist.
- [x] Decimal amount validation, idempotency payload hashing, transfer service, and paired ledger entries.
- [x] Synthetic provider batch and discrepancy review workflow.
- [x] Rule-based risk flags and human review.
- [x] Offline synthetic-data/model training and evaluation scripts.
- [x] PostgreSQL Compose configuration, seed script, env examples, CI workflow, and docs.
- [x] Regular backend test suite: 17 passed, 1 skipped.
- [x] Ruff check passed for `backend/app`, `backend/tests`, and `backend/scripts`.
- [x] Ruff format check passed for `backend/app` and `backend/tests` (23 files already formatted).
- [x] Frontend ESLint and Vite production build passed.
- [x] Separate opt-in PostgreSQL concurrency test passed against local PostgreSQL.
- [x] Local demo seed script executed successfully.

## Remaining work
- [ ] Add dedicated reversal tests, including concurrent reversal attempts and expected conflict handling.
- [ ] Expand reconciliation tests for discrepancy types, clean batches, duplicate/status/missing-provider scenarios, and rerun behavior.
- [ ] Review frontend filtering/pagination, confirmation dialogs, and loading/error/empty states.
- [ ] Review model evaluation metadata/API integration and document synthetic-metric limitations.
- [ ] Measure and document coverage and relevant idempotency, reconciliation, model, and latency metrics.
- [ ] Review generated artifacts and repository contents before the first Git commit.
- [ ] Run GitHub Actions after pushing; it has not yet been verified on GitHub.
- [ ] Verify deployment configuration and provider terms, then deploy only after local acceptance and security review.
