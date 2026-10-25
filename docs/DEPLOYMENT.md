# Free-only deployment plan (not yet deployed)

Target architecture: Vercel Hobby for the React/Vite frontend and FastAPI Python functions; Neon Free PostgreSQL for persistent data. This is a plan only. No account, plan, billing status, or live deployment has been verified.

Official policy pages to re-check on the day of deployment:
- Vercel Hobby: https://vercel.com/docs/plans/hobby
- FastAPI on Vercel: https://vercel.com/docs/frameworks/backend/fastapi
- Neon plans: https://neon.com/pricing
- GitHub Actions billing: https://docs.github.com/en/actions/concepts/billing-and-usage

Checklist:
- [ ] Confirm Vercel Hobby eligibility and current terms; do not activate Pro trial.
- [ ] Confirm Neon Free quotas/retention and no paid trial; no billing details without user approval.
- [ ] Create a dedicated Neon database and verify TLS connection string compatibility with psycopg.
- [ ] Configure production `DATABASE_URL`, random `JWT_SECRET`, `FRONTEND_ORIGIN`, `APP_ENV=production`, and seed settings.
- [ ] Configure correct Vercel project roots/builds and serverless API routing; verify FastAPI app entrypoint.
- [ ] Apply Alembic migrations once, not on every cold start.
- [ ] Provision demo credentials privately; never publish admin password in source/UI.
- [ ] Smoke-test health, login, accounts, transfer retry, ledger, reconciliation and risk review.
- [ ] Verify database persistence across cold starts/redeploys and CORS rejection for unknown origins.
- [ ] Record plan names, quotas, verification date and live URLs only after checking dashboards.

No live URL is provided because deployment has not been performed or verified. Free-tier policies can change; stop and reassess if the requirements cannot be met without a paid plan or card.
