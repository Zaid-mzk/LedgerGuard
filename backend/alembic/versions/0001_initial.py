"""Create the initial LedgerGuard relational schema."""
from alembic import op
import sqlalchemy as sa
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"), sa.CheckConstraint("role IN ('admin','analyst','customer')", name="ck_users_role"))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("accounts",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_number", sa.String(24), nullable=False), sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("status", sa.String(12), nullable=False),
        sa.Column("balance", sa.Numeric(12,2), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_number", name="uq_accounts_account_number"), sa.CheckConstraint("currency = 'INR'", name="ck_accounts_currency"),
        sa.CheckConstraint("status IN ('active','frozen')", name="ck_accounts_status"))
    op.create_index("ix_accounts_owner_user_id", "accounts", ["owner_user_id"])
    op.create_table("transfers",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("sender_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("receiver_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False), sa.Column("amount", sa.Numeric(12,2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("description", sa.String(240)), sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reversal_of_transfer_id", sa.String(36), sa.ForeignKey("transfers.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("created_by_user_id", "idempotency_key", name="uq_user_idempotency"),
        sa.UniqueConstraint("reversal_of_transfer_id", name="uq_transfers_reversal_of_transfer_id"),
        sa.CheckConstraint("amount > 0", name="ck_transfer_positive_amount"), sa.CheckConstraint("currency = 'INR'", name="ck_transfers_currency"),
        sa.CheckConstraint("status IN ('pending','completed','failed','reversed')", name="ck_transfers_status"))
    for col in ("sender_account_id", "receiver_account_id", "created_at"):
        op.create_index(f"ix_transfers_{col}", "transfers", [col])
    op.create_table("ledger_entries",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("transfer_id", sa.String(36), sa.ForeignKey("transfers.id"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False), sa.Column("amount", sa.Numeric(12,2), nullable=False),
        sa.Column("entry_type", sa.String(10), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("entry_type IN ('debit','credit')", name="ck_ledger_entry_type"))
    op.create_index("ix_ledger_entries_transfer_id", "ledger_entries", ["transfer_id"])
    op.create_index("ix_ledger_entries_account_id", "ledger_entries", ["account_id"])
    op.create_index("ix_ledger_account_time", "ledger_entries", ["account_id", "created_at"])
    op.create_table("audit_events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(80), nullable=False), sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36)), sa.Column("metadata", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_audit_events_action", "audit_events", ["action"]); op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_table("provider_records",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("provider_reference", sa.String(80), nullable=False),
        sa.Column("transfer_id", sa.String(36), sa.ForeignKey("transfers.id")), sa.Column("amount", sa.Numeric(12,2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("scenario_tag", sa.String(60)), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_reference", name="uq_provider_records_provider_reference"),
        sa.CheckConstraint("status IN ('settled','failed','refunded')", name="ck_provider_records_status"))
    op.create_index("ix_provider_records_transfer_id", "provider_records", ["transfer_id"])
    op.create_table("reconciliation_runs",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("started_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('completed','failed')", name="ck_reconciliation_runs_status"))
    op.create_table("reconciliation_discrepancies",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("run_id", sa.String(36), sa.ForeignKey("reconciliation_runs.id"), nullable=False),
        sa.Column("transfer_id", sa.String(36), sa.ForeignKey("transfers.id")), sa.Column("provider_record_id", sa.String(36), sa.ForeignKey("provider_records.id")),
        sa.Column("discrepancy_type", sa.String(40), nullable=False), sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False), sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("discrepancy_type IN ('missing_internal','missing_provider','amount_mismatch','status_mismatch','duplicate_provider_record')", name="ck_discrepancy_type"),
        sa.CheckConstraint("severity IN ('low','medium','high')", name="ck_discrepancy_severity"),
        sa.CheckConstraint("status IN ('open','reviewed','resolved')", name="ck_discrepancy_status"))
    op.create_index("ix_reconciliation_discrepancies_run_id", "reconciliation_discrepancies", ["run_id"])
    op.create_index("ix_reconciliation_discrepancies_status", "reconciliation_discrepancies", ["status"])
    op.create_index("ix_discrepancy_status_time", "reconciliation_discrepancies", ["status", "created_at"])
    op.create_table("risk_flags",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("transfer_id", sa.String(36), sa.ForeignKey("transfers.id"), nullable=False),
        sa.Column("risk_score", sa.Numeric(4,3), nullable=False), sa.Column("model_version", sa.String(40), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False), sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)), sa.CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="ck_risk_score_range"),
        sa.CheckConstraint("status IN ('open','reviewed','dismissed')", name="ck_risk_status"))
    op.create_index("ix_risk_flags_transfer_id", "risk_flags", ["transfer_id"])
    op.create_index("ix_risk_flags_status", "risk_flags", ["status"])
    op.create_index("ix_risk_status_time", "risk_flags", ["status", "created_at"])

def downgrade():
    op.drop_table("risk_flags")
    op.drop_table("reconciliation_discrepancies")
    op.drop_table("reconciliation_runs")
    op.drop_table("provider_records")
    op.drop_table("audit_events")
    op.drop_table("ledger_entries")
    op.drop_table("transfers")
    op.drop_table("accounts")
    op.drop_table("users")
