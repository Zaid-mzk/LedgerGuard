# Architecture decisions

- **React/Vite + FastAPI:** follows the project specification; no framework substitution.
- **PostgreSQL for intended runtime:** production/local primary database is PostgreSQL. Test suite uses isolated in-memory SQLite for speed; PostgreSQL integration tests remain a required gap.
- **Decimal money:** avoids binary floating-point rounding errors.
- **Synchronous transfers:** suitable for this request/response demo; no Redis/Celery/background workers.
- **Rules first, offline ML separate:** risk rules are understandable and serverless-friendly; model training is reproducible and does not affect financial state.
- **Deployment deferred:** local correctness and provider plan verification must precede deployment.
- **Initial delivery scope note:** this is a substantial first implementation, not proof that every acceptance criterion in the full guide has passed. See `PROGRESS_CHECKLIST.md` and validate/fix gaps before public deployment.
