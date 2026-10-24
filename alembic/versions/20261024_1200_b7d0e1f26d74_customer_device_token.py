from collections.abc import Sequence

from alembic import op

revision: str = "b7d0e1f26d74"
down_revision: str | None = "f41d5a0c6dec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("uq_appointments_access_token_hash"), "appointments", type_="unique")
    for table in ("appointments", "appointments_history"):
        op.alter_column(table, "access_token_hash", new_column_name="customer_token_hash")
    op.create_index(
        op.f("ix_appointments_customer_token_hash"),
        "appointments",
        ["customer_token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_appointments_customer_token_hash"), table_name="appointments")
    for table in ("appointments", "appointments_history"):
        op.alter_column(table, "customer_token_hash", new_column_name="access_token_hash")
    op.create_unique_constraint(
        op.f("uq_appointments_access_token_hash"), "appointments", ["access_token_hash"]
    )
