"""Add integrity constraints for fumigation, QC, and lot weights.

Revision ID: 8c9d2f11b7de
Revises: 6f7f0e3e6a42
Create Date: 2026-02-19 18:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8c9d2f11b7de"
down_revision = "6f7f0e3e6a42"
branch_labels = None
depends_on = None


CHECK_CONSTRAINTS = [
    ("lots", "ck_lots_fumigation_status_valid", "fumigation_status IN ('1', '2', '3', '4')"),
    ("fulltruckweights", "ck_fulltruckweights_loaded_positive", "loaded_truck_weight > 0"),
    ("fulltruckweights", "ck_fulltruckweights_empty_non_negative", "empty_truck_weight >= 0"),
    (
        "lotsqc",
        "ck_lotsqc_units_breakdown",
        "units = lessthan30 + between3032 + between3234 + between3436 + morethan36",
    ),
    ("lotsqc", "ck_lotsqc_inshell_positive", "inshell_weight > 0"),
    (
        "samplesqc",
        "ck_samplesqc_units_breakdown",
        "units = lessthan30 + between3032 + between3234 + between3436 + morethan36",
    ),
    ("samplesqc", "ck_samplesqc_inshell_positive", "inshell_weight > 0"),
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
