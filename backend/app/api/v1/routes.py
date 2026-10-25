from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import (
    User,
    Account,
    Transfer,
    LedgerEntry,
    AuditEvent,
    ProviderRecord,
    ReconciliationRun,
    ReconciliationDiscrepancy,
    RiskFlag,
)
from app.schemas.api import LoginIn, TransferIn, ReviewIn
from app.core.security import verify_password, create_token
from app.core.deps import current_user, roles
from app.services.transfers import create_transfer
from app.services.audit import audit
import os
from fastapi import Response
from app.core.config import settings

router = APIRouter(prefix="/api/v1")


def iso(x):
    return x.isoformat() if x else None


def transfer_out(t):
    return {
        "id": t.id,
        "sender_account_id": t.sender_account_id,
        "receiver_account_id": t.receiver_account_id,
        "amount": str(t.amount),
        "currency": t.currency,
        "status": t.status,
        "description": t.description,
        "created_at": iso(t.created_at),
    }


def account_out(a):
    return {
        "id": a.id,
        "account_number": "••••" + a.account_number[-4:],
        "display_name": a.display_name,
        "currency": a.currency,
        "status": a.status,
        "balance": str(a.balance),
    }


@router.post("/auth/login")
def login(
    data: LoginIn,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == data.email.strip().lower()))

    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        audit(
            db,
            user.id if user else None,
            "auth.login_failed",
            "user",
            user.id if user else None,
        )
        db.commit()
        raise HTTPException(
            401,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Email or password is incorrect",
            },
        )

    token = create_token(user.id)
    audit(db, user.id, "auth.login_success", "user", user.id)
    db.commit()

    response.set_cookie(
        key="lg_access_token",
        value=token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=settings.jwt_access_token_minutes * 60,
        path="/",
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
        },
    }


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(
        key="lg_access_token",
        path="/",
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
    )
    return {"message": "Signed out"}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}


@router.get("/metrics/summary")
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role == "customer":
        owned_account_ids = select(Account.id).where(Account.owner_user_id == user.id)
        owned_transfers = select(Transfer).where(
            Transfer.status == "completed",
            (
                Transfer.sender_account_id.in_(owned_account_ids)
                | Transfer.receiver_account_id.in_(owned_account_ids)
            ),
        )

        completed = db.scalar(select(func.count()).select_from(owned_transfers.subquery())) or 0

        total = db.scalar(
            select(func.sum(Transfer.amount)).where(
                Transfer.status == "completed",
                (
                    Transfer.sender_account_id.in_(owned_account_ids)
                    | Transfer.receiver_account_id.in_(owned_account_ids)
                ),
            )
        ) or Decimal("0.00")

        return {
            "completed_transfers": completed,
            "simulated_transfer_value": str(total),
            "open_discrepancies": None,
            "open_risk_flags": None,
        }

    completed = (
        db.scalar(select(func.count(Transfer.id)).where(Transfer.status == "completed")) or 0
    )

    total = db.scalar(
        select(func.sum(Transfer.amount)).where(Transfer.status == "completed")
    ) or Decimal("0.00")

    latest_run_id = db.scalar(
        select(ReconciliationRun.id)
        .where(ReconciliationRun.status == "completed")
        .order_by(
            ReconciliationRun.completed_at.desc(),
            ReconciliationRun.started_at.desc(),
            ReconciliationRun.id.desc(),
        )
        .limit(1)
    )

    discrepancies = 0
    if latest_run_id is not None:
        discrepancies = (
            db.scalar(
                select(func.count(ReconciliationDiscrepancy.id)).where(
                    ReconciliationDiscrepancy.run_id == latest_run_id,
                    ReconciliationDiscrepancy.status == "open",
                )
            )
            or 0
        )

    flags = db.scalar(select(func.count(RiskFlag.id)).where(RiskFlag.status == "open")) or 0

    return {
        "completed_transfers": completed,
        "simulated_transfer_value": str(total),
        "open_discrepancies": discrepancies,
        "open_risk_flags": flags,
    }


@router.get("/accounts")
def accounts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Account)
    if user.role == "customer":
        q = q.where(Account.owner_user_id == user.id)
    return [account_out(a) for a in db.scalars(q.order_by(Account.created_at.desc())).all()]


@router.get("/accounts/{account_id}/ledger")
def account_ledger(
    account_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Account not found"})
    if user.role == "customer" and account.owner_user_id != user.id:
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Account access denied"})
    rows = db.scalars(
        select(LedgerEntry)
        .where(LedgerEntry.account_id == account_id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(200)
    ).all()
    return [
        {
            "id": x.id,
            "transfer_id": x.transfer_id,
            "account_id": x.account_id,
            "amount": str(x.amount),
            "entry_type": x.entry_type,
            "created_at": iso(x.created_at),
        }
        for x in rows
    ]


@router.post("/transfers")
def post_transfer(
    data: TransferIn,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    transfer, replayed = create_transfer(db, user, data, idempotency_key)
    return {**transfer_out(transfer), "idempotency_replay": replayed}


@router.get("/transfers")
def transfers(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    limit = max(1, min(limit, 100))
    q = select(Transfer).order_by(Transfer.created_at.desc()).offset(max(0, offset)).limit(limit)
    if user.role == "customer":
        ids = select(Account.id).where(Account.owner_user_id == user.id)
        q = q.where((Transfer.sender_account_id.in_(ids)) | (Transfer.receiver_account_id.in_(ids)))
    return [transfer_out(t) for t in db.scalars(q).all()]


@router.get("/transfers/{transfer_id}")
def transfer_detail(
    transfer_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    t = db.get(Transfer, transfer_id)
    if not t:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Transfer not found"})
    if user.role == "customer":
        owned = set(db.scalars(select(Account.id).where(Account.owner_user_id == user.id)).all())
        if t.sender_account_id not in owned and t.receiver_account_id not in owned:
            raise HTTPException(
                403, detail={"code": "FORBIDDEN", "message": "Transfer access denied"}
            )
    entries = db.scalars(select(LedgerEntry).where(LedgerEntry.transfer_id == t.id)).all()
    return {
        **transfer_out(t),
        "ledger_entries": [
            {"account_id": e.account_id, "entry_type": e.entry_type, "amount": str(e.amount)}
            for e in entries
        ],
        "ledger_sum": str(sum((e.amount for e in entries), Decimal("0.00"))),
    }


@router.post("/transfers/{transfer_id}/reverse")
def reverse_transfer(
    transfer_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(roles("admin", "analyst")),
):
    if not 8 <= len(idempotency_key) <= 128 or not all(
        c.isalnum() or c in "-_.:" for c in idempotency_key
    ):
        raise HTTPException(
            422,
            detail={
                "code": "INVALID_IDEMPOTENCY_KEY",
                "message": "Idempotency-Key must be 8–128 safe characters",
            },
        )
    original = db.scalar(select(Transfer).where(Transfer.id == transfer_id).with_for_update())
    if not original:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Transfer not found"})
    digest = hashlib.sha256(f"reverse:{original.id}".encode()).hexdigest()
    existing = db.scalar(
        select(Transfer).where(
            Transfer.created_by_user_id == user.id, Transfer.idempotency_key == idempotency_key
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(
                409,
                detail={
                    "code": "IDEMPOTENCY_CONFLICT",
                    "message": "This key was already used with a different request",
                },
            )
        return {**transfer_out(existing), "idempotency_replay": True}
    prior = db.scalar(select(Transfer).where(Transfer.reversal_of_transfer_id == original.id))
    if prior:
        raise HTTPException(
            409,
            detail={
                "code": "ALREADY_REVERSED",
                "message": "This transfer has already been reversed",
            },
        )
    if original.status != "completed":
        raise HTTPException(
            409,
            detail={
                "code": "NOT_REVERSIBLE",
                "message": "Only completed transfers can be reversed",
            },
        )
    sender = db.scalar(
        select(Account).where(Account.id == original.receiver_account_id).with_for_update()
    )
    receiver = db.scalar(
        select(Account).where(Account.id == original.sender_account_id).with_for_update()
    )
    if not sender or not receiver:
        raise HTTPException(
            409,
            detail={"code": "ACCOUNT_UNAVAILABLE", "message": "Transfer accounts are unavailable"},
        )
    amount = original.amount
    if sender.balance < amount:
        raise HTTPException(
            409,
            detail={
                "code": "REVERSAL_FUNDS_UNAVAILABLE",
                "message": "Receiver balance is insufficient for this demo reversal",
            },
        )
    try:
        reversal = Transfer(
            sender_account_id=sender.id,
            receiver_account_id=receiver.id,
            amount=amount,
            currency=original.currency,
            status="completed",
            idempotency_key=idempotency_key,
            request_hash=digest,
            description=f"Reversal of {original.id}",
            created_by_user_id=user.id,
            reversal_of_transfer_id=original.id,
        )
        db.add(reversal)
        db.flush()
        sender.balance -= amount
        receiver.balance += amount
        db.add_all(
            [
                LedgerEntry(
                    transfer_id=reversal.id,
                    account_id=sender.id,
                    amount=-amount,
                    entry_type="debit",
                ),
                LedgerEntry(
                    transfer_id=reversal.id,
                    account_id=receiver.id,
                    amount=amount,
                    entry_type="credit",
                ),
            ]
        )
        audit(
            db,
            user.id,
            "transfer.reversed",
            "transfer",
            reversal.id,
            {"original_transfer_id": original.id, "amount": str(amount)},
        )
        db.commit()
        db.refresh(reversal)
        return {
            **transfer_out(reversal),
            "idempotency_replay": False,
            "reversal_of_transfer_id": original.id,
        }
    except Exception:
        db.rollback()
        raise


@router.get("/ledger")
def ledger(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(LedgerEntry).order_by(LedgerEntry.created_at.desc()).limit(200)
    rows = db.scalars(q).all()
    owned = set(db.scalars(select(Account.id).where(Account.owner_user_id == user.id)).all())
    return [
        {
            "id": e.id,
            "transfer_id": e.transfer_id,
            "account_id": e.account_id,
            "amount": str(e.amount),
            "entry_type": e.entry_type,
            "created_at": iso(e.created_at),
        }
        for e in rows
        if user.role != "customer" or e.account_id in owned
    ]


@router.get("/audit")
def audit_log(db: Session = Depends(get_db), user: User = Depends(roles("admin", "analyst"))):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)).all()
    return [
        {
            "id": x.id,
            "actor_id": x.actor_id,
            "action": x.action,
            "entity_type": x.entity_type,
            "entity_id": x.entity_id,
            "metadata": x.metadata_json,
            "created_at": iso(x.created_at),
        }
        for x in rows
    ]


@router.post("/reconciliation/simulate-provider-batch")
def simulate_batch(
    db: Session = Depends(get_db),
    user: User = Depends(roles("admin")),
):
    transfers = db.scalars(
        select(Transfer)
        .where(Transfer.status == "completed")
        .order_by(Transfer.created_at.desc(), Transfer.id.desc())
        .limit(30)
    ).all()

    created = 0

    for index, transfer in enumerate(transfers):
        reference = f"SYN-{transfer.id}"

        existing = db.scalar(
            select(ProviderRecord).where(ProviderRecord.provider_reference == reference)
        )
        if existing:
            continue

        amount = transfer.amount + Decimal("1.00") if index == 0 else transfer.amount

        db.add(
            ProviderRecord(
                provider_reference=reference,
                transfer_id=transfer.id,
                amount=amount,
                currency="INR",
                status="settled",
                scenario_tag="amount_mismatch" if index == 0 else "clean",
            )
        )
        created += 1

    orphan_reference = "SYN-ORPHAN-DEMO-001"
    existing_orphan = db.scalar(
        select(ProviderRecord).where(ProviderRecord.provider_reference == orphan_reference)
    )

    if not existing_orphan:
        db.add(
            ProviderRecord(
                provider_reference=orphan_reference,
                transfer_id=None,
                amount=Decimal("77.00"),
                currency="INR",
                status="settled",
                scenario_tag="missing_internal",
            )
        )
        created += 1

    audit(
        db,
        user.id,
        "reconciliation.batch_generated",
        "provider_batch",
        None,
        {"records_created": created, "synthetic": True},
    )
    db.commit()

    return {"created": created, "synthetic": True}


@router.post("/reconciliation/run")
def run_reconciliation(
    db: Session = Depends(get_db),
    user: User = Depends(roles("admin", "analyst")),
):
    transfers = db.scalars(select(Transfer).where(Transfer.status == "completed")).all()
    transfers_by_id = {t.id: t for t in transfers}

    providers = db.scalars(select(ProviderRecord)).all()
    by_transfer = {}
    for provider in providers:
        if provider.transfer_id:
            by_transfer.setdefault(provider.transfer_id, []).append(provider)

    findings = []
    matched_transfer_ids = set()

    for provider in providers:
        transfer = transfers_by_id.get(provider.transfer_id)

        if transfer is None:
            findings.append(
                (
                    None,
                    provider,
                    "missing_internal",
                    "high",
                    {"provider_amount": str(provider.amount)},
                )
            )
            continue

        transfer_providers = by_transfer[transfer.id]

        if len(transfer_providers) > 1:
            # One duplicate finding per transfer, not per provider row.
            continue

        issues = []
        if provider.amount != transfer.amount:
            issues.append(
                (
                    "amount_mismatch",
                    "high",
                    {
                        "internal_amount": str(transfer.amount),
                        "provider_amount": str(provider.amount),
                    },
                )
            )

        expected_status = "settled" if transfer.status == "completed" else "failed"
        if provider.status != expected_status:
            issues.append(
                (
                    "status_mismatch",
                    "medium",
                    {
                        "internal_status": transfer.status,
                        "provider_status": provider.status,
                    },
                )
            )

        if issues:
            for kind, severity, details in issues:
                findings.append((transfer, provider, kind, severity, details))
        else:
            matched_transfer_ids.add(transfer.id)

    for transfer_id, transfer in transfers_by_id.items():
        transfer_providers = by_transfer.get(transfer_id, [])

        if not transfer_providers:
            findings.append(
                (
                    transfer,
                    None,
                    "missing_provider",
                    "medium",
                    {"internal_amount": str(transfer.amount)},
                )
            )
        elif len(transfer_providers) > 1:
            findings.append(
                (
                    transfer,
                    None,
                    "duplicate_provider_record",
                    "medium",
                    {"count": len(transfer_providers)},
                )
            )
            matched_transfer_ids.discard(transfer_id)

    summary = {
        "internal_checked": len(transfers_by_id),
        "provider_checked": len(providers),
        "matched": len(matched_transfer_ids),
        "discrepancies": len(findings),
    }

    run = ReconciliationRun(
        started_by_user_id=user.id,
        status="completed",
        summary=summary,
    )
    db.add(run)
    db.flush()

    for transfer, provider, kind, severity, details in findings:
        db.add(
            ReconciliationDiscrepancy(
                run_id=run.id,
                transfer_id=transfer.id if transfer else None,
                provider_record_id=provider.id if provider else None,
                discrepancy_type=kind,
                severity=severity,
                details=details,
                status="open",
            )
        )

    audit(
        db,
        user.id,
        "reconciliation.completed",
        "reconciliation_run",
        run.id,
        summary,
    )
    db.commit()

    return {"id": run.id, **summary}


@router.get("/reconciliation/runs")
def reconciliation_runs(
    db: Session = Depends(get_db), user: User = Depends(roles("admin", "analyst"))
):
    rows = db.scalars(
        select(ReconciliationRun).order_by(ReconciliationRun.started_at.desc()).limit(100)
    ).all()
    return [
        {
            "id": r.id,
            "status": r.status,
            "summary": r.summary,
            "started_at": iso(r.started_at),
            "completed_at": iso(r.completed_at),
        }
        for r in rows
    ]


@router.get("/reconciliation/runs/{run_id}")
def reconciliation_run_detail(
    run_id: str, db: Session = Depends(get_db), user: User = Depends(roles("admin", "analyst"))
):
    r = db.get(ReconciliationRun, run_id)
    if not r:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Reconciliation run not found"}
        )
    return {
        "id": r.id,
        "status": r.status,
        "summary": r.summary,
        "started_at": iso(r.started_at),
        "completed_at": iso(r.completed_at),
    }


@router.get("/reconciliation/discrepancies")
def discrepancies(
    db: Session = Depends(get_db),
    user: User = Depends(roles("admin", "analyst")),
):
    latest_run_id = db.scalar(
        select(ReconciliationRun.id)
        .where(ReconciliationRun.status == "completed")
        .order_by(
            ReconciliationRun.completed_at.desc(),
            ReconciliationRun.started_at.desc(),
            ReconciliationRun.id.desc(),
        )
        .limit(1)
    )

    if latest_run_id is None:
        return []

    rows = db.scalars(
        select(ReconciliationDiscrepancy)
        .where(ReconciliationDiscrepancy.run_id == latest_run_id)
        .order_by(ReconciliationDiscrepancy.created_at.desc())
        .limit(200)
    ).all()

    return [
        {
            "id": d.id,
            "run_id": d.run_id,
            "transfer_id": d.transfer_id,
            "provider_record_id": d.provider_record_id,
            "type": d.discrepancy_type,
            "severity": d.severity,
            "details": d.details,
            "status": d.status,
            "created_at": iso(d.created_at),
        }
        for d in rows
    ]


@router.patch("/reconciliation/discrepancies/{item_id}")
def review_discrepancy(
    item_id: str,
    data: ReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(roles("admin", "analyst")),
):
    d = db.get(ReconciliationDiscrepancy, item_id)
    if not d:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Discrepancy not found"})
    d.status = data.status
    d.reviewed_at = datetime.now(timezone.utc)
    audit(
        db,
        user.id,
        "reconciliation.discrepancy_reviewed",
        "discrepancy",
        d.id,
        {"status": data.status},
    )
    db.commit()
    return {"id": d.id, "status": d.status}


@router.post("/risk/analyze")
def analyze_risk(db: Session = Depends(get_db), user: User = Depends(roles("admin", "analyst"))):
    ts = db.scalars(
        select(Transfer)
        .where(Transfer.status == "completed")
        .order_by(Transfer.created_at.desc())
        .limit(200)
    ).all()
    created = 0
    for t in ts:
        if db.scalar(
            select(RiskFlag.id).where(
                RiskFlag.transfer_id == t.id, RiskFlag.model_version == "rules-v1"
            )
        ):
            continue
        reasons = []
        score = 0.05
        if t.amount >= Decimal("50000.00"):
            reasons.append("HIGH_AMOUNT_VS_BASELINE")
            score += 0.55
        if t.amount >= Decimal("20000.00"):
            reasons.append("HIGH_VELOCITY") if len(reasons) == 0 else None
            score += 0.2
        if t.created_at and t.created_at.hour < 5:
            reasons.append("UNUSUAL_TIMING")
            score += 0.15
        if reasons:
            db.add(
                RiskFlag(
                    transfer_id=t.id,
                    risk_score=min(score, 1.0),
                    model_version="rules-v1",
                    reason_codes=reasons,
                    explanation="Rule-based review suggestion; not a fraud determination.",
                )
            )
            created += 1
    audit(
        db,
        user.id,
        "risk.analysis_completed",
        "risk_analysis",
        None,
        {"flags_created": created, "model_version": "rules-v1"},
    )
    db.commit()
    return {"flags_created": created, "model_version": "rules-v1", "synthetic_only": True}


@router.get("/risk/flags")
def risk_flags(db: Session = Depends(get_db), user: User = Depends(roles("admin", "analyst"))):
    rows = db.scalars(select(RiskFlag).order_by(RiskFlag.created_at.desc()).limit(200)).all()
    return [
        {
            "id": x.id,
            "transfer_id": x.transfer_id,
            "risk_score": float(x.risk_score),
            "model_version": x.model_version,
            "reason_codes": x.reason_codes,
            "explanation": x.explanation,
            "status": x.status,
            "created_at": iso(x.created_at),
        }
        for x in rows
    ]


@router.patch("/risk/flags/{item_id}")
def review_flag(
    item_id: str,
    data: ReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(roles("admin", "analyst")),
):
    if data.status not in {"reviewed", "dismissed"}:
        raise HTTPException(
            422, detail={"code": "INVALID_STATUS", "message": "Use reviewed or dismissed"}
        )
    flag = db.get(RiskFlag, item_id)
    if not flag:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Risk flag not found"})
    flag.status = data.status
    flag.reviewed_at = datetime.now(timezone.utc)
    audit(db, user.id, "risk.flag_reviewed", "risk_flag", flag.id, {"status": data.status})
    db.commit()
    return {"id": flag.id, "status": flag.status}


@router.get("/risk/model-evaluation")
def model_evaluation():
    return {
        "status": "not_evaluated",
        "synthetic_only": True,
        "message": "Run backend/scripts/train_risk_model.py to generate measured offline evaluation metrics. No model metrics are fabricated.",
    }
