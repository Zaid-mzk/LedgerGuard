
"""Allow recruiter role for read-only demo."""

from alembic import op

revision = "0002_recruiter_role"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "ck_users_role",
        "users",
        type_="check",
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('admin','analyst','customer','recruiter')",
    )


def downgrade():
    op.execute("DELETE FROM users WHERE role = 'recruiter'")

    op.drop_constraint(
        "ck_users_role",
        "users",
        type_="check",
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('admin','analyst','customer')",
    )
