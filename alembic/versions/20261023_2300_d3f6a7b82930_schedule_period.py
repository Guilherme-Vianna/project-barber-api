from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3f6a7b82930"
down_revision: str | None = "c2e5f6a71829"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("barbershops", "barbershops_history"):
        op.add_column(table, sa.Column("schedule_starts_on", sa.Date(), nullable=True))
        op.add_column(table, sa.Column("schedule_ends_on", sa.Date(), nullable=True))
    op.create_check_constraint(
        op.f("ck_barbershops_schedule_period"),
        "barbershops",
        "schedule_ends_on >= schedule_starts_on",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_barbershops_schedule_period"), "barbershops", type_="check")
    for table in ("barbershops", "barbershops_history"):
        op.drop_column(table, "schedule_ends_on")
        op.drop_column(table, "schedule_starts_on")
