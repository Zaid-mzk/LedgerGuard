# API notes

Interactive OpenAPI documentation is available at `/docs` when the API is running.

Authentication: `POST /api/v1/auth/login` returns a short-lived bearer token; send `Authorization: Bearer <token>` for protected routes. Operational reconciliation and risk routes require `admin` or `analyst`; provider-batch generation requires `admin`.

Transfer creation: `POST /api/v1/transfers` requires an `Idempotency-Key` header (8–128 safe characters) and JSON body with sender/receiver account IDs, positive INR amount and optional description. Same key + canonical same payload returns the original transfer; changed payload returns 409. Amount must have at most two decimal places.

The API currently provides health, login/me, summary metrics, accounts, account ledger, transfers, ledger, audit log, reconciliation batch/run/discrepancies/review, risk analyze/flags/review and model-evaluation status. Check route definitions for exact schemas and role guards.
