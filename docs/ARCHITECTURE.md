# Architecture

The React/Vite SPA calls a FastAPI JSON API using bearer JWTs. FastAPI validates requests with Pydantic and delegates transaction creation to a service. SQLAlchemy persists users, accounts, transfers, ledger entries, audit events, provider records, reconciliation runs/discrepancies and risk flags in PostgreSQL.

Money is represented as `Decimal` in Python and `NUMERIC(12,2)` in PostgreSQL. Completed transfers are intended to create two ledger entries whose signed amounts sum to zero. Cached account balances are updated in the same transaction. Reconciliation and risk analysis are separate workflows and never mutate balances.

The ML experiment is offline and uses generated synthetic data. The live API currently uses transparent deterministic rules for risk flags; offline model inference is not wired into transfer processing and cannot alter financial state.
