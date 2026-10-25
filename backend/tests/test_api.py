from sqlalchemy import select
from app.models.entities import Transfer, LedgerEntry
from decimal import Decimal
from app.models.entities import ProviderRecord


def login(c, email="admin@test.local"):
    r = c.post("/api/v1/auth/login", json={"email": email, "password": "Password!123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_health_and_auth(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/v1/accounts").status_code == 401


def test_transfer_and_idempotency(client):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "retry-key-0001"}
    accounts = client.get("/api/v1/accounts", headers=headers).json()
    sender = next(a for a in accounts if a["display_name"] == "Admin")
    receiver = next(a for a in accounts if a["display_name"] == "Customer")
    body = {
        "sender_account_id": sender["id"],
        "receiver_account_id": receiver["id"],
        "amount": "125.50",
        "currency": "INR",
        "description": "test transfer",
    }
    r1 = client.post("/api/v1/transfers", headers=headers, json=body)
    assert r1.status_code == 200, r1.text
    r2 = client.post("/api/v1/transfers", headers=headers, json=body)
    assert (
        r2.status_code == 200
        and r2.json()["id"] == r1.json()["id"]
        and r2.json()["idempotency_replay"] is True
    )
    detail = client.get(
        "/api/v1/transfers/" + r1.json()["id"], headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert len(detail["ledger_entries"]) == 2 and detail["ledger_sum"] == "0.00"


def test_same_key_different_payload_conflicts(client):
    token = login(client)
    h = {"Authorization": f"Bearer {token}", "Idempotency-Key": "retry-key-0002"}
    accounts = client.get("/api/v1/accounts", headers=h).json()
    a, b = accounts[0], accounts[1]
    body = {"sender_account_id": a["id"], "receiver_account_id": b["id"], "amount": "10.00"}
    assert client.post("/api/v1/transfers", headers=h, json=body).status_code == 200
    body["amount"] = "11.00"
    assert client.post("/api/v1/transfers", headers=h, json=body).status_code == 409


def test_invalid_amount_rejected(client):
    token = login(client)
    h = {"Authorization": f"Bearer {token}", "Idempotency-Key": "retry-key-0003"}
    accounts = client.get("/api/v1/accounts", headers=h).json()
    r = client.post(
        "/api/v1/transfers",
        headers=h,
        json={
            "sender_account_id": accounts[0]["id"],
            "receiver_account_id": accounts[1]["id"],
            "amount": "-1",
        },
    )
    assert r.status_code == 422


def test_provider_batch_is_idempotent(client):
    from app.models.entities import ProviderRecord

    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/v1/reconciliation/simulate-provider-batch",
        headers=headers,
    )
    assert first.status_code == 200, first.text

    TestingSession = client.app.state.TestingSession
    with TestingSession() as db:
        count_after_first = len(db.scalars(select(ProviderRecord)).all())

    second = client.post(
        "/api/v1/reconciliation/simulate-provider-batch",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["created"] == 0

    with TestingSession() as db:
        count_after_second = len(db.scalars(select(ProviderRecord)).all())

    assert count_after_second == count_after_first


def test_duplicate_provider_records_create_one_finding(client):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    accounts = client.get("/api/v1/accounts", headers=headers).json()
    sender = next(a for a in accounts if a["display_name"] == "Admin")
    receiver = next(a for a in accounts if a["display_name"] == "Customer")

    transfer_response = client.post(
        "/api/v1/transfers",
        headers={
            **headers,
            "Idempotency-Key": "duplicate-provider-test",
        },
        json={
            "sender_account_id": sender["id"],
            "receiver_account_id": receiver["id"],
            "amount": "25.00",
            "currency": "INR",
            "description": "Duplicate provider regression test",
        },
    )
    assert transfer_response.status_code == 200, transfer_response.text
    transfer_id = transfer_response.json()["id"]

    TestingSession = client.app.state.TestingSession
    with TestingSession() as db:
        db.add_all(
            [
                ProviderRecord(
                    provider_reference="TEST-PROVIDER-A",
                    transfer_id=transfer_id,
                    amount=Decimal("25.00"),
                    currency="INR",
                    status="settled",
                ),
                ProviderRecord(
                    provider_reference="TEST-PROVIDER-B",
                    transfer_id=transfer_id,
                    amount=Decimal("25.00"),
                    currency="INR",
                    status="settled",
                ),
            ]
        )
        db.commit()

    response = client.post(
        "/api/v1/reconciliation/run",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["matched"] == 0

    with TestingSession() as db:
        from app.models.entities import ReconciliationDiscrepancy

        findings = db.scalars(
            select(ReconciliationDiscrepancy).where(
                ReconciliationDiscrepancy.run_id == response.json()["id"],
                ReconciliationDiscrepancy.transfer_id == transfer_id,
                ReconciliationDiscrepancy.discrepancy_type == "duplicate_provider_record",
            )
        ).all()

    assert len(findings) == 1


def test_dashboard_discrepancies_use_latest_reconciliation_run(client):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/v1/reconciliation/run",
        headers=headers,
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/v1/reconciliation/run",
        headers=headers,
    )
    assert second.status_code == 200, second.text

    summary = client.get(
        "/api/v1/metrics/summary",
        headers=headers,
    )
    assert summary.status_code == 200, summary.text

    assert summary.json()["open_discrepancies"] == second.json()["discrepancies"]


def test_customer_metrics_do_not_expose_global_operations(client):
    token = login(client, email="customer@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/v1/metrics/summary",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert "completed_transfers" in data
    assert "simulated_transfer_value" in data
    assert data["open_discrepancies"] is None
    assert data["open_risk_flags"] is None


def test_insufficient_funds_does_not_change_balances_or_ledger(client):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    accounts = client.get("/api/v1/accounts", headers=headers).json()
    sender = next(a for a in accounts if a["display_name"] == "Admin")
    receiver = next(a for a in accounts if a["display_name"] == "Customer")

    before = {a["id"]: a["balance"] for a in accounts}

    db_factory = client.app.state.TestingSession
    with db_factory() as db:
        before_ledger_count = len(db.scalars(select(LedgerEntry)).all())

    response = client.post(
        "/api/v1/transfers",
        headers={
            **headers,
            "Idempotency-Key": "insufficient-funds-test",
        },
        json={
            "sender_account_id": sender["id"],
            "receiver_account_id": receiver["id"],
            "amount": "999999.00",
            "currency": "INR",
            "description": "Insufficient funds regression test",
        },
    )
    assert response.status_code == 422
    assert "INSUFFICIENT_FUNDS" in response.text

    after_accounts = client.get("/api/v1/accounts", headers=headers).json()
    after = {a["id"]: a["balance"] for a in after_accounts}
    assert after == before

    with db_factory() as db:
        after_ledger_count = len(db.scalars(select(LedgerEntry)).all())

    assert after_ledger_count == before_ledger_count


def test_clean_provider_record_counts_as_matched(client):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    accounts = client.get("/api/v1/accounts", headers=headers).json()
    sender = next(a for a in accounts if a["display_name"] == "Admin")
    receiver = next(a for a in accounts if a["display_name"] == "Customer")

    transfer_response = client.post(
        "/api/v1/transfers",
        headers={
            **headers,
            "Idempotency-Key": "clean-reconciliation-test",
        },
        json={
            "sender_account_id": sender["id"],
            "receiver_account_id": receiver["id"],
            "amount": "25.00",
            "currency": "INR",
            "description": "Clean reconciliation regression test",
        },
    )
    assert transfer_response.status_code == 200, transfer_response.text
    transfer_id = transfer_response.json()["id"]

    TestingSession = client.app.state.TestingSession
    with TestingSession() as db:
        db.add(
            ProviderRecord(
                provider_reference="TEST-CLEAN-" + transfer_id,
                transfer_id=transfer_id,
                amount=Decimal("25.00"),
                currency="INR",
                status="settled",
                scenario_tag="clean",
            )
        )
        db.commit()

    response = client.post(
        "/api/v1/reconciliation/run",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["matched"] == 1


def test_amount_mismatch_is_not_counted_as_matched(client):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    accounts = client.get("/api/v1/accounts", headers=headers).json()
    sender = next(a for a in accounts if a["display_name"] == "Admin")
    receiver = next(a for a in accounts if a["display_name"] == "Customer")

    transfer_response = client.post(
        "/api/v1/transfers",
        headers={
            **headers,
            "Idempotency-Key": "amount-mismatch-test",
        },
        json={
            "sender_account_id": sender["id"],
            "receiver_account_id": receiver["id"],
            "amount": "25.00",
            "currency": "INR",
            "description": "Amount mismatch regression test",
        },
    )
    assert transfer_response.status_code == 200, transfer_response.text
    transfer_id = transfer_response.json()["id"]

    TestingSession = client.app.state.TestingSession
    with TestingSession() as db:
        db.add(
            ProviderRecord(
                provider_reference="TEST-MISMATCH-" + transfer_id,
                transfer_id=transfer_id,
                amount=Decimal("26.00"),
                currency="INR",
                status="settled",
                scenario_tag="amount_mismatch",
            )
        )
        db.commit()

    response = client.post(
        "/api/v1/reconciliation/run",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["matched"] == 0

    with TestingSession() as db:
        from app.models.entities import ReconciliationDiscrepancy

        findings = db.scalars(
            select(ReconciliationDiscrepancy).where(
                ReconciliationDiscrepancy.run_id == response.json()["id"],
                ReconciliationDiscrepancy.transfer_id == transfer_id,
                ReconciliationDiscrepancy.discrepancy_type == "amount_mismatch",
            )
        ).all()

    assert len(findings) == 1


def test_transfer_commit_failure_rolls_back(client, monkeypatch):
    from unittest.mock import patch

    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    accounts = client.get("/api/v1/accounts", headers=headers).json()
    sender = next(a for a in accounts if a["display_name"] == "Admin")
    receiver = next(a for a in accounts if a["display_name"] == "Customer")

    before_balances = {account["id"]: account["balance"] for account in accounts}

    TestingSession = client.app.state.TestingSession
    with TestingSession() as db:
        before_transfers = len(db.scalars(select(Transfer)).all())
        before_ledger = len(db.scalars(select(LedgerEntry)).all())

    from app.services import transfers as transfer_service

    original_audit = transfer_service.audit

    def fail_on_completed_transfer(db, user_id, action, *args, **kwargs):
        if action == "transfer.completed":
            raise RuntimeError("Injected failure for rollback test")
        return original_audit(db, user_id, action, *args, **kwargs)

    with patch.object(transfer_service, "audit", side_effect=fail_on_completed_transfer):
        response = client.post(
            "/api/v1/transfers",
            headers={
                **headers,
                "Idempotency-Key": "rollback-failure-test",
            },
            json={
                "sender_account_id": sender["id"],
                "receiver_account_id": receiver["id"],
                "amount": "25.00",
                "currency": "INR",
                "description": "Rollback regression test",
            },
        )

    assert response.status_code == 500

    after_accounts = client.get("/api/v1/accounts", headers=headers).json()
    after_balances = {account["id"]: account["balance"] for account in after_accounts}
    assert after_balances == before_balances

    with TestingSession() as db:
        after_transfers = len(db.scalars(select(Transfer)).all())
        after_ledger = len(db.scalars(select(LedgerEntry)).all())

    assert after_transfers == before_transfers
    assert after_ledger == before_ledger


def test_transfer_reversal_restores_balances_and_rejects_second_reversal(client):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    accounts = client.get("/api/v1/accounts", headers=headers).json()
    sender = next(a for a in accounts if a["display_name"] == "Admin")
    receiver = next(a for a in accounts if a["display_name"] == "Customer")

    original_balances = {a["id"]: Decimal(a["balance"]) for a in accounts}

    # Create an original transfer.
    transfer_response = client.post(
        "/api/v1/transfers",
        headers={**headers, "Idempotency-Key": "reversal-original-001"},
        json={
            "sender_account_id": sender["id"],
            "receiver_account_id": receiver["id"],
            "amount": "25.00",
            "currency": "INR",
            "description": "Reversal regression test",
        },
    )
    assert transfer_response.status_code == 200, transfer_response.text
    original_id = transfer_response.json()["id"]

    # Reverse the original transfer.
    reversal_response = client.post(
        f"/api/v1/transfers/{original_id}/reverse",
        headers={**headers, "Idempotency-Key": "reversal-request-001"},
    )
    assert reversal_response.status_code == 200, reversal_response.text
    reversal_id = reversal_response.json()["id"]
    assert reversal_response.json()["reversal_of_transfer_id"] == original_id

    # Replaying the same request must return the same reversal.
    replay_response = client.post(
        f"/api/v1/transfers/{original_id}/reverse",
        headers={**headers, "Idempotency-Key": "reversal-request-001"},
    )
    assert replay_response.status_code == 200, replay_response.text
    assert replay_response.json()["id"] == reversal_id
    assert replay_response.json()["idempotency_replay"] is True

    # A different key must not allow the same original to be reversed again.
    second_reversal = client.post(
        f"/api/v1/transfers/{original_id}/reverse",
        headers={**headers, "Idempotency-Key": "reversal-request-002"},
    )
    assert second_reversal.status_code == 409, second_reversal.text
    assert "ALREADY_REVERSED" in second_reversal.text

    # Balances must be restored to their original values.
    final_accounts = client.get("/api/v1/accounts", headers=headers).json()
    final_balances = {a["id"]: Decimal(a["balance"]) for a in final_accounts}
    assert final_balances == original_balances

    # Both the original transfer and its reversal must have balanced entries.
    db_factory = client.app.state.TestingSession
    with db_factory() as db:
        for transfer_id in (original_id, reversal_id):
            entries = db.scalars(
                select(LedgerEntry).where(LedgerEntry.transfer_id == transfer_id)
            ).all()
            assert len(entries) == 2
            assert sum(
                (entry.amount for entry in entries),
                Decimal("0.00"),
            ) == Decimal("0.00")


def test_customer_cannot_access_admin_operations_or_other_accounts(client):
    token = login(client, email="customer@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    # Customer should only see accounts they own.
    accounts_response = client.get("/api/v1/accounts", headers=headers)
    assert accounts_response.status_code == 200
    accounts = accounts_response.json()
    assert accounts
    assert all(a["display_name"] == "Customer" for a in accounts)

    # Admin-only provider batch generation must be denied.
    batch_response = client.post(
        "/api/v1/reconciliation/simulate-provider-batch",
        headers=headers,
    )
    assert batch_response.status_code == 403

    # Operational audit logs are restricted to admin/analyst.
    audit_response = client.get("/api/v1/audit", headers=headers)
    assert audit_response.status_code == 403


def test_transfer_is_recorded_in_audit_log(client):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    accounts = client.get("/api/v1/accounts", headers=headers).json()
    sender = next(a for a in accounts if a["display_name"] == "Admin")
    receiver = next(a for a in accounts if a["display_name"] == "Customer")

    transfer_response = client.post(
        "/api/v1/transfers",
        headers={
            **headers,
            "Idempotency-Key": "audit-transfer-test-001",
        },
        json={
            "sender_account_id": sender["id"],
            "receiver_account_id": receiver["id"],
            "amount": "12.00",
            "currency": "INR",
            "description": "Audit logging regression test",
        },
    )
    assert transfer_response.status_code == 200, transfer_response.text
    transfer_id = transfer_response.json()["id"]

    audit_response = client.get("/api/v1/audit", headers=headers)
    assert audit_response.status_code == 200, audit_response.text

    events = audit_response.json()
    assert any(
        event["action"] == "transfer.completed" and event["entity_id"] == transfer_id
        for event in events
    )


def test_discrepancy_review_is_audited(client):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Generate deterministic synthetic provider records and reconciliation findings.
    batch = client.post(
        "/api/v1/reconciliation/simulate-provider-batch",
        headers=headers,
    )
    assert batch.status_code == 200, batch.text

    run = client.post("/api/v1/reconciliation/run", headers=headers)
    assert run.status_code == 200, run.text

    response = client.get(
        "/api/v1/reconciliation/discrepancies",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    discrepancies = response.json()
    assert discrepancies, "Expected synthetic reconciliation findings"

    item = discrepancies[0]
    review = client.patch(
        f"/api/v1/reconciliation/discrepancies/{item['id']}",
        headers=headers,
        json={"status": "reviewed"},
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "reviewed"

    audit_response = client.get("/api/v1/audit", headers=headers)
    assert audit_response.status_code == 200, audit_response.text
    assert any(
        event["action"] == "reconciliation.discrepancy_reviewed"
        and event["entity_id"] == item["id"]
        for event in audit_response.json()
    )
