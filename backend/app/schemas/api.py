from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


class LoginIn(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)


class TransferIn(BaseModel):
    sender_account_id: str
    receiver_account_id: str
    amount: Decimal
    currency: str = "INR"
    description: str | None = Field(default=None, max_length=240)

    @field_validator("amount")
    @classmethod
    def valid_amount(cls, v):
        if not v.is_finite() or v <= 0 or v.as_tuple().exponent < -2:
            raise ValueError("Amount must be positive with at most two decimal places")
        if v > Decimal("9999999999.99"):
            raise ValueError("Amount is too large")
        return v

    @field_validator("currency")
    @classmethod
    def inr_only(cls, v):
        if v != "INR":
            raise ValueError("Only INR is supported")
        return v


class ReviewIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_allowed(cls, v):
        if v not in {"reviewed", "resolved", "dismissed"}:
            raise ValueError("Unsupported review status")
        return v
