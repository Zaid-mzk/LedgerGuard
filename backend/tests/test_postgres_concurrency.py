import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Import the application using the backend package path.
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


from app.core.config import settings  # noqa: E402
from app.models.entities import (  # noqa: E402
    Account,
    AuditEvent,
    LedgerEntry,
    Transfer,
    User,
)
from app.core.security import hash_password  # noqa: E402
from app.services.transfers import create_transfer  # noqa: E402
from app.schemas.api import TransferIn  # noqa: E402


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_CONCURRENCY") != "1",
    reason="Set RUN_POSTGRES_CONCURRENCY=1 to run this PostgreSQL integration test",
)
def test_concurrent_transfers_cannot_overspend():
    url = settings.database_url

    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("This test requires PostgreSQL with the psycopg driver.")

    engine = create_engine(url, pool_pre_ping=True)
    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    # Verify the target schema exists. Never create/drop tables here.
    if not engine.dialect.name == "postgresql":
        engine.dispose()
        pytest.fail("Refusing to run: the database is not PostgreSQL.")

    suffix = threading.get_ident()
    test_email = f"concurrency-{suffix}@test.invalid"
    test_user_id = None
    account_ids = []
    ready = threading.Barrier(2)

    try:
        with Session.begin() as db:
            user = User(
                email=test_email,
                password_hash=hash_password("Test-only-Password!123"),
                role="admin",
            )
            db.add(user)
            db.flush()
            test_user_id = user.id

            sender = Account(
                owner_user_id=user.id,
                account_number=f"LGTEST{suffix % 10**10:010d}",
                display_name="Temporary Concurrency Sender",
                balance=100,
            )
            receiver1 = Account(
                owner_user_id=user.id,
                account_number=f"LGTEST{(suffix + 1) % 10**10:010d}",
                display_name="Temporary Concurrency Receiver 1",
                balance=0,
            )
            receiver2 = Account(
                owner_user_id=user.id,
                account_number=f"LGTEST{(suffix + 2) % 10**10:010d}",
                display_name="Temporary Concurrency Receiver 2",
                balance=0,
            )
            db.add_all([sender, receiver1, receiver2])
            db.flush()
            account_ids = [sender.id, receiver1.id, receiver2.id]
            sender_id, receiver1_id, receiver2_id = account_ids

        # Ensure both workers are ready before either attempts the transfer.
        def attempt(receiver_id, key):
            with Session() as db:
                user = db.get(User, test_user_id)
                request = TransferIn(
                    sender_account_id=sender_id,
                    receiver_account_id=receiver_id,
                    amount="80.00",
                    currency="INR",
                    description="Temporary PostgreSQL concurrency test",
                )
                ready.wait(timeout=10)
                try:
                    transfer, replayed = create_transfer(db, user, request, key)
                    return ("success", transfer.id)
                except Exception as exc:
                    db.rollback()
                    from fastapi import HTTPException

                    if (
                        isinstance(exc, HTTPException)
                        and exc.status_code == 422
                        and isinstance(exc.detail, dict)
                        and exc.detail.get("code") == "INSUFFICIENT_FUNDS"
                    ):
                        return ("insufficient_funds", None)
                    return ("error", repr(exc))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    attempt,
                    receiver1_id,
                    f"concurrency-test-{suffix}-A",
                ),
                pool.submit(
                    attempt,
                    receiver2_id,
                    f"concurrency-test-{suffix}-B",
                ),
            ]
            results = [future.result(timeout=30) for future in futures]

        errors = [result for result in results if result[0] == "error"]
        assert not errors, f"Unexpected worker error(s): {errors}"
        assert sum(result[0] == "success" for result in results) == 1, results
        assert sum(result[0] == "insufficient_funds" for result in results) == 1, results

        with Session() as db:
            db.expire_all()
            sender = db.get(Account, sender_id)
            receiver_balances = [
                db.get(Account, receiver_id).balance for receiver_id in (receiver1_id, receiver2_id)
            ]
            transfers = db.scalars(
                select(Transfer).where(Transfer.sender_account_id == sender_id)
            ).all()
            entries = db.scalars(
                select(LedgerEntry).where(
                    LedgerEntry.transfer_id.in_([transfer.id for transfer in transfers])
                )
            ).all()

            assert sender.balance == 20
            assert sum(receiver_balances) == 80
            assert len(transfers) == 1
            assert len(entries) == 2
            assert sum((entry.amount for entry in entries), start=0) == 0

        print("PASS: one transfer succeeded; the other was rejected.")
        print("PASS: sender balance is 20.00; total receiver balance is 80.00.")
        print("PASS: exactly two balanced ledger entries were created.")

    finally:
        # Delete only records belonging to the temporary test accounts/user.
        if test_user_id:
            with Session.begin() as db:
                ids = list(
                    db.scalars(
                        select(Transfer.id).where(Transfer.created_by_user_id == test_user_id)
                    ).all()
                )
                if ids:
                    db.query(LedgerEntry).filter(LedgerEntry.transfer_id.in_(ids)).delete(
                        synchronize_session=False
                    )
                    db.query(Transfer).filter(Transfer.id.in_(ids)).delete(
                        synchronize_session=False
                    )

                db.query(AuditEvent).filter(AuditEvent.actor_id == test_user_id).delete(
                    synchronize_session=False
                )
                db.query(Account).filter(Account.owner_user_id == test_user_id).delete(
                    synchronize_session=False
                )
                db.query(User).filter(User.id == test_user_id).delete(synchronize_session=False)

        engine.dispose()
