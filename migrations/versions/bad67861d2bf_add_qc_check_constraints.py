"""add qc check constraints

Revision ID: bad67861d2bf
Revises: 8c9d2f11b7de
Create Date: 2026-02-19 15:58:11.491324

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bad67861d2bf'
down_revision = '8c9d2f11b7de'
branch_labels = None
depends_on = None


CHECK_CONSTRAINTS = [
    (
        "lotsqc",
        "ck_lotsqc_size_sum_100",
        "lessthan30 + between3032 + between3234 + between3436 + morethan36 = 100",
    ),
    (
        "samplesqc",
        "ck_samplesqc_size_sum_100",
        "lessthan30 + between3032 + between3234 + between3436 + morethan36 = 100",
    ),
]


def _existing_checks(bind, table_name):
    inspector = sa.inspect(bind)
    checks = inspector.get_check_constraints(table_name)
    return {check["name"] for check in checks if check.get("name")}


def upgrade():
    bind = op.get_bind()
    for table_name, constraint_name, condition in CHECK_CONSTRAINTS:
        if constraint_name in _existing_checks(bind, table_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_check_constraint(constraint_name, condition)


def downgrade():
    bind = op.get_bind()
    for table_name, constraint_name, _condition in CHECK_CONSTRAINTS:
        if constraint_name not in _existing_checks(bind, table_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="check")
