import hashlib
import json
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import Account, Transfer, LedgerEntry
from app.services.audit import audit


def transfer_payload_hash(data):
    canonical = {
        "sender_account_id": data.sender_account_id,
        "receiver_account_id": data.receiver_account_id,
        "amount": str(data.amount.quantize(Decimal("0.01"))),
        "currency": data.currency,
        "description": data.description or "",
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def create_transfer(db: Session, user, data, key: str):
    if not key or not 8 <= len(key) <= 128 or not all(c.isalnum() or c in "-_.:" for c in key):
        raise HTTPException(
            422,
            detail={
                "code": "INVALID_IDEMPOTENCY_KEY",
                "message": "Idempotency-Key must be 8–128 safe characters",
            },
        )
    digest = transfer_payload_hash(data)
    existing = db.scalar(
        select(Transfer).where(
            Transfer.created_by_user_id == user.id, Transfer.idempotency_key == key
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
        audit(db, user.id, "idempotency.replay", "transfer", existing.id, {"key_reused": True})
        db.commit()
        return existing, True
    sender = db.scalar(
        select(Account).where(Account.id == data.sender_account_id).with_for_update()
    )
    receiver = db.scalar(
        select(Account).where(Account.id == data.receiver_account_id).with_for_update()
    )
    # A concurrent identical request may have committed while this request waited for the account lock.
    existing = db.scalar(
        select(Transfer).where(
            Transfer.created_by_user_id == user.id, Transfer.idempotency_key == key
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
        audit(db, user.id, "idempotency.replay", "transfer", existing.id, {"key_reused": True})
        db.commit()
        return existing, True
    if not sender or not receiver:
        raise HTTPException(
            404,
            detail={
                "code": "ACCOUNT_NOT_FOUND",
                "message": "Sender or receiver account was not found",
            },
        )
    if sender.owner_user_id != user.id and user.role not in ("admin", "analyst"):
        raise HTTPException(
            403,
            detail={"code": "ACCOUNT_FORBIDDEN", "message": "You cannot use this sender account"},
        )
    if sender.id == receiver.id:
        raise HTTPException(
            422, detail={"code": "SAME_ACCOUNT", "message": "Sender and receiver must differ"}
        )
    if sender.status != "active" or receiver.status != "active":
        raise HTTPException(
            409, detail={"code": "ACCOUNT_INACTIVE", "message": "Both accounts must be active"}
        )
    amount = data.amount.quantize(Decimal("0.01"))
    if sender.balance < amount:
        audit(
            db,
            user.id,
            "transfer.insufficient_funds",
            "account",
            sender.id,
            {"requested_amount": str(amount)},
        )
        db.commit()
        raise HTTPException(
            422,
            detail={
                "code": "INSUFFICIENT_FUNDS",
                "message": "The sender account has insufficient funds",
            },
        )
    try:
        transfer = Transfer(
            sender_account_id=sender.id,
            receiver_account_id=receiver.id,
            amount=amount,
            currency="INR",
            status="completed",
            idempotency_key=key,
            request_hash=digest,
            description=data.description,
            created_by_user_id=user.id,
        )
        db.add(transfer)
        db.flush()
        sender.balance -= amount
        receiver.balance += amount
        db.add_all(
            [
                LedgerEntry(
                    transfer_id=transfer.id,
                    account_id=sender.id,
                    amount=-amount,
                    entry_type="debit",
                ),
                LedgerEntry(
                    transfer_id=transfer.id,
                    account_id=receiver.id,
                    amount=amount,
                    entry_type="credit",
                ),
            ]
        )
        audit(
            db,
            user.id,
            "transfer.completed",
            "transfer",
            transfer.id,
            {"amount": str(amount), "currency": "INR"},
        )
        db.commit()
        db.refresh(transfer)
        return transfer, False
    except Exception:
        db.rollback()
        raise
