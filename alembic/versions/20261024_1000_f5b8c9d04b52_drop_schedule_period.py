from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5b8c9d04b52"
down_revision: str | None = "e4a7b8c93a41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_barbershops_schedule_period"), "barbershops", type_="check")
    for table in ("barbershops", "barbershops_history"):
        op.drop_column(table, "schedule_ends_on")
        op.drop_column(table, "schedule_starts_on")


def downgrade() -> None:
    for table in ("barbershops", "barbershops_history"):
        op.add_column(table, sa.Column("schedule_starts_on", sa.Date(), nullable=True))
        op.add_column(table, sa.Column("schedule_ends_on", sa.Date(), nullable=True))
    op.create_check_constraint(
        op.f("ck_barbershops_schedule_period"),
        "barbershops",
        "schedule_ends_on >= schedule_starts_on",
    )
