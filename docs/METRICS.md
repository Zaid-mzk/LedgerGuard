# Measured metrics

No project performance metrics are pre-claimed. Run the test suite and offline model script, then paste actual outputs with date, commands and environment here.

- Test pass rate: 5/5 included tests passed in the available environment on 2026-10-24; run command `PYTHONPATH=. DATABASE_URL=sqlite:///./temporary-test.db JWT_SECRET=this-is-a-long-test-secret-at-least-thirty-two-bytes pytest -q` from `backend/`. This is a small smoke/API suite, not the complete acceptance suite.
- Coverage: not measured in this delivery environment.
- PostgreSQL concurrency/atomicity: not yet verified.
- Idempotency experiment: automated API tests are included; repeat benchmark not yet run.
- Synthetic ML precision/recall/F1: not yet generated. Run `python scripts/train_risk_model.py` from `backend/`.
- API p50/p95: not measured.
