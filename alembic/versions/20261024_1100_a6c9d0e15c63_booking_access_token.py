from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6c9d0e15c63"
down_revision: str | None = "f5b8c9d04b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("appointments", "appointments_history"):
        op.add_column(table, sa.Column("access_token_hash", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        op.f("uq_appointments_access_token_hash"), "appointments", ["access_token_hash"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_appointments_access_token_hash"), "appointments", type_="unique")
    for table in ("appointments", "appointments_history"):
        op.drop_column(table, "access_token_hash")
