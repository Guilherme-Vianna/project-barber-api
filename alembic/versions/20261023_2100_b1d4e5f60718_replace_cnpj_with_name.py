from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1d4e5f60718"
down_revision: str | None = "a0c7322906dd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("barbershops", "barbershops_history"):
        op.add_column(table, sa.Column("name", sa.String(length=150), nullable=True))
        op.execute(f"UPDATE {table} SET name = first_name || ' ' || last_name")
        op.alter_column(table, "name", nullable=False)
    op.drop_constraint(op.f("uq_barbershops_cnpj"), "barbershops", type_="unique")
    op.drop_column("barbershops", "cnpj")
    op.drop_column("barbershops_history", "cnpj")


def downgrade() -> None:
    op.add_column("barbershops_history", sa.Column("cnpj", sa.String(length=14), nullable=True))
    op.add_column("barbershops", sa.Column("cnpj", sa.String(length=14), nullable=True))
    for table in ("barbershops", "barbershops_history"):
        op.execute(
            f"UPDATE {table} "
            "SET cnpj = lpad((abs(hashtext(id::text)) % 100000000000000)::text, 14, '0')"
        )
        op.alter_column(table, "cnpj", nullable=False)
    op.create_unique_constraint(op.f("uq_barbershops_cnpj"), "barbershops", ["cnpj"])
    op.drop_column("barbershops", "name")
    op.drop_column("barbershops_history", "name")
