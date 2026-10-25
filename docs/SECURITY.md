# Security decisions

- Passwords use a maintained Argon2 password hashing implementation.
- JWTs are signed with a configured secret and expire after a short interval.
- Frontend holds the token in memory rather than persistent browser storage.
- CORS is limited to configured local/deployed frontend origins.
- Pydantic validates request payloads; SQLAlchemy uses parameterized queries.
- Role checks protect reconciliation, risk review and audit routes.
- Synthetic data only; credentials and `.env` files must not be committed. Demo seed passwords are generated randomly and displayed only once by the local seed command.

Before any public deployment: remove seeded public credentials from the UI, use a private/demo-safe auth strategy, rotate secrets, disable public seed execution, add rate limits, review request logging and IDs, verify database row-lock/concurrency behavior on PostgreSQL, review CORS and Vercel routing, define token/session/recovery policy, and conduct a threat model/security review. This is not production financial software.
